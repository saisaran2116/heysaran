import express from 'express'
import { randomUUID } from 'node:crypto'
import { eq } from 'drizzle-orm'
import { z, ZodError } from 'zod'
import { rateLimit } from 'express-rate-limit'
import multer from 'multer'
import Stripe from 'stripe'
import { OAuth2Client } from 'google-auth-library'
import { hash, matches, sessions } from './auth.js'
import { ownedId, users } from './db.js'
import { assistant } from './assistant.js'

const credentials = z.object({ email: z.email().max(254).transform(s => s.toLowerCase()), password: z.string().min(10).max(128) })
const entry = z.object({
  kind: z.enum(['note', 'preset']), title: z.string().trim().min(1).max(100),
  body: z.string().trim().min(1).max(12000),
})
const idSchema = z.string().regex(/^[a-f0-9]{24}$/i)
const limit = rateLimit({ windowMs: 60_000, limit: 15, standardHeaders: 'draft-8', legacyHeaders: false,
  message: { error: 'Too many requests. Try again in a minute.' } })
const reportSql = `SELECT a.email, COALESCE(p.name,'Free') AS plan, count(u.id)::int AS requests,
  COALESCE(sum(u.input_tokens + u.output_tokens),0)::int AS tokens,
  sum(u.estimated_usd) AS estimated_usd FROM accounts a
  LEFT JOIN memberships m ON m.account_id=a.id LEFT JOIN plans p ON p.id=m.plan_id
  LEFT JOIN usage_events u ON u.account_id=a.id AND u.created_at >= now() - interval '30 days'
  WHERE a.id=$1 GROUP BY a.email,p.name ORDER BY a.email`
function fail(status, message) { throw Object.assign(new Error(message), { status }) }

export function createApi(db, env, broadcast = () => {}) {
  const api = express.Router()
  const session = sessions(env.JWT_SECRET)
  const ai = assistant(env)
  const stripe = env.STRIPE_SECRET_KEY ? new Stripe(env.STRIPE_SECRET_KEY) : null
  const origin = new URL(env.PUBLIC_URL || 'http://localhost:3000').origin
  const cookie = { httpOnly: true, secure: origin.startsWith('https:'), sameSite: 'lax', path: '/' }
  const google = env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET
    ? new OAuth2Client(env.GOOGLE_CLIENT_ID, env.GOOGLE_CLIENT_SECRET, origin + '/api/auth/google/callback') : null

  api.use((req, res, next) => {
    res.set({ 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Request-ID': randomUUID() })
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method) && req.headers.origin && req.headers.origin !== origin) {
      return res.status(403).json({ error: 'Origin not allowed' })
    }
    next()
  })
  api.post('/billing/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
    if (!stripe || !env.STRIPE_WEBHOOK_SECRET || !env.STRIPE_PRICE_ID) fail(503, 'Billing unavailable')
    let event
    try { event = stripe.webhooks.constructEvent(req.body, req.headers['stripe-signature'], env.STRIPE_WEBHOOK_SECRET) }
    catch { fail(400, 'Invalid webhook signature') }
    if (['checkout.session.completed', 'checkout.session.async_payment_succeeded'].includes(event.type)) {
      const checkout = event.data.object
      const id = checkout.client_reference_id
      if (checkout.payment_status === 'paid' && checkout.mode === 'payment' && z.uuid().safeParse(id).success) {
        const items = await stripe.checkout.sessions.listLineItems(checkout.id)
        if (!items.data.some(item => item.price?.id === env.STRIPE_PRICE_ID)) fail(400, 'Unexpected checkout price')
        const conn = await db.pool.connect()
        try {
          await conn.query('BEGIN')
          const inserted = await conn.query('INSERT INTO stripe_events(id) VALUES($1) ON CONFLICT DO NOTHING RETURNING id', [event.id])
          if (inserted.rowCount) await conn.query(`INSERT INTO memberships(account_id,plan_id) VALUES($1,'supporter')
            ON CONFLICT(account_id) DO UPDATE SET plan_id='supporter', updated_at=now()`, [id])
          await conn.query('COMMIT')
        } catch (error) { await conn.query('ROLLBACK'); throw error }
        finally { conn.release() }
      }
    }
    res.sendStatus(204)
  })
  api.use(express.json({ limit: '32kb' }))
  api.get('/health', async (_, res) => {
    await Promise.all([db.pool.query('SELECT 1'), db.redis.ping(), db.library.findOne({}, { projection: { _id: 1 } })])
    res.json({ ok: true })
  })
  async function signedIn(res, account) {
    res.cookie('hb_session', await session.issue(account.id), { ...cookie, maxAge: 8 * 3600_000 })
  }
  api.get('/auth/options', (_, res) => res.json({ google: Boolean(google) }))
  api.post('/auth/register', limit, async (req, res) => {
    const { email, password } = credentials.parse(req.body)
    const [account] = await db.orm.insert(users).values({ email, password: await hash(password) })
      .onConflictDoNothing({ target: users.email }).returning({ id: users.id })
    if (!account) fail(409, 'Email already registered')
    await signedIn(res, account)
    res.status(201).json({ email })
  })
  api.post('/auth/login', limit, async (req, res) => {
    const { email, password } = credentials.parse(req.body)
    const [account] = await db.orm.select().from(users).where(eq(users.email, email))
    if (!await matches(password, account?.password)) fail(401, 'Invalid email or password')
    await signedIn(res, account)
    res.json({ email })
  })
  api.get('/auth/google', limit, (_, res) => {
    if (!google) fail(503, 'Google login unavailable')
    const state = randomUUID()
    res.cookie('hb_oauth', state, { ...cookie, maxAge: 600_000 })
    res.redirect(google.generateAuthUrl({ scope: ['openid', 'email'], state }))
  })
  api.get('/auth/google/callback', limit, async (req, res) => {
    if (!google || !req.query.state || req.query.state !== session.cookie(req, 'hb_oauth')) fail(400, 'Invalid OAuth state')
    const code = z.string().min(1).max(4096).parse(req.query.code)
    res.clearCookie('hb_oauth', cookie)
    const { tokens } = await google.getToken(code)
    const identity = (await google.verifyIdToken({ idToken: tokens.id_token, audience: env.GOOGLE_CLIENT_ID })).getPayload()
    if (!identity.email_verified) fail(403, 'Google email is unverified')
    let [account] = await db.orm.select().from(users).where(eq(users.googleSub, identity.sub))
    if (!account) {
      ;[account] = await db.orm.insert(users).values({ email: identity.email.toLowerCase(), googleSub: identity.sub })
        .onConflictDoNothing().returning()
      if (!account) fail(409, 'This email already has an account. Use password sign-in.')
    }
    await signedIn(res, account)
    res.redirect('/')
  })
  api.post('/auth/logout', (_, res) => res.clearCookie('hb_session', cookie).sendStatus(204))
  api.use(async (req, _, next) => {
    const id = await session.read(req)
    if (id) {
      const [{ password, googleSub, ...account } = {}] = await db.orm.select().from(users).where(eq(users.id, id))
      if (account.id) { req.account = account; return next() }
    }
    fail(401, 'Sign in to continue')
  })
  api.get('/me', (req, res) => res.json({ ...req.account, ai: ai.available, billing: Boolean(stripe && env.STRIPE_PRICE_ID) }))
  async function remember(data, owner) {
    const embedding = ai.available && data.kind === 'note' ? await ai.embed(data.title + '\n' + data.body) : null
    return { ...data, owner, embedding, embeddingModel: embedding ? ai.embeddingModel : null, updatedAt: new Date() }
  }
  async function save(req, res, data) {
    const doc = await remember(data, req.account.id)
    const result = await db.library.insertOne(doc)
    broadcast(req.account.id, { type: 'library.changed' })
    res.status(201).json({ id: result.insertedId })
  }
  api.get('/library', async (req, res) => {
    const kind = z.enum(['note', 'preset']).optional().parse(req.query.kind)
    const filter = kind ? { owner: req.account.id, kind } : { owner: req.account.id }
    res.json(await db.library.find(filter, { projection: { owner: 0, embedding: 0 } }).sort({ updatedAt: -1 }).limit(100).toArray())
  })
  api.get('/library/summary', async (req, res) => {
    res.json(await db.library.aggregate([{ $match: { owner: req.account.id } },
      { $group: { _id: '$kind', count: { $sum: 1 } } }, { $sort: { _id: 1 } }]).toArray())
  })
  api.post('/library', limit, (req, res) => save(req, res, entry.parse(req.body)))
  api.post('/library/upload', limit, multer({ limits: { fileSize: 24000, files: 1, fields: 0 } }).single('file'), async (req, res) => {
    if (!req.file || !/\.(md|txt)$/i.test(req.file.originalname)) fail(400, 'Choose a .txt or .md file')
    let body
    try { body = new TextDecoder('utf8', { fatal: true }).decode(req.file.buffer) }
    catch { fail(400, 'Upload a UTF-8 text file') }
    return save(req, res, entry.parse({ kind: 'note', title: req.file.originalname, body }))
  })
  api.get('/library/:id', async (req, res) => {
    const doc = await db.library.findOne(ownedId(req.account.id, idSchema.parse(req.params.id)), { projection: { owner: 0, embedding: 0 } })
    if (!doc) fail(404, 'Entry not found')
    res.json(doc)
  })
  api.put('/library/:id', limit, async (req, res) => {
    const filter = ownedId(req.account.id, idSchema.parse(req.params.id))
    if (!await db.library.findOne(filter, { projection: { _id: 1 } })) fail(404, 'Entry not found')
    const changed = await db.library.updateOne(filter, { $set: await remember(entry.parse(req.body), req.account.id) })
    if (!changed.matchedCount) fail(404, 'Entry not found')
    broadcast(req.account.id, { type: 'library.changed' })
    res.sendStatus(204)
  })
  api.delete('/library/:id', async (req, res) => {
    const deleted = await db.library.deleteOne(ownedId(req.account.id, idSchema.parse(req.params.id)))
    if (!deleted.deletedCount) fail(404, 'Entry not found')
    broadcast(req.account.id, { type: 'library.changed' })
    res.sendStatus(204)
  })
  api.get('/usage', async (req, res) => {
    const key = 'usage:' + req.account.id
    const cached = await db.redis.get(key)
    if (cached) return res.json(JSON.parse(cached))
    const { rows } = await db.pool.query(reportSql, [req.account.id])
    await db.redis.setEx(key, 60, JSON.stringify(rows[0]))
    res.json(rows[0])
  })
  api.get('/admin/accounts', async (req, res) => {
    if (req.account.role !== 'admin') fail(403, 'Administrator access required')
    const { rows } = await db.pool.query('SELECT id,email,role,created_at FROM accounts ORDER BY created_at DESC LIMIT 100')
    res.json(rows)
  })
  api.get('/places/weather', limit, async (req, res) => {
    const city = z.string().trim().min(2).max(80).parse(req.query.city)
    const key = 'weather:' + city.toLowerCase()
    const cached = await db.redis.get(key)
    if (cached) return res.json(JSON.parse(cached))
    const search = await fetch('https://geocoding-api.open-meteo.com/v1/search?' + new URLSearchParams({ name: city, count: '1' }), { signal: AbortSignal.timeout(6000) })
    if (!search.ok) fail(502, 'Weather search unavailable')
    const [place] = (await search.json()).results || []
    if (!place) fail(404, 'City not found')
    const weather = await fetch('https://api.open-meteo.com/v1/forecast?' + new URLSearchParams({
      latitude: place.latitude, longitude: place.longitude, current: 'temperature_2m'
    }), { signal: AbortSignal.timeout(6000) })
    if (!weather.ok) fail(502, 'Weather unavailable')
    const data = { city: place.name, celsius: (await weather.json()).current.temperature_2m }
    await db.redis.setEx(key, 300, JSON.stringify(data))
    res.json(data)
  })
  api.post('/assistant', limit, async (req, res) => {
    const { query, stream, useNotes, usePresets } = z.object({ query: z.string().trim().min(1).max(2000),
      stream: z.boolean().default(true), useNotes: z.boolean().default(false),
      usePresets: z.boolean().default(false) }).parse(req.body)
    if (!ai.available) fail(503, 'Set OPENAI_API_KEY on the server to enable Assistant')
    const abort = new AbortController()
    res.on('close', () => { if (!res.writableEnded) abort.abort() })
    const send = (event, value) => res.write('event: ' + event + '\ndata: ' + JSON.stringify(value) + '\n\n')
    try {
      const context = useNotes ? await ai.retrieve(query, db.library, req.account.id) : []
      if (stream) {
        res.set({ 'Content-Type': 'text/event-stream', 'X-Accel-Buffering': 'no' })
        res.flushHeaders()
        send('status', { stage: 'Generating', references: context.map(({ id, title }) => ({ id, title })) })
      }
      const { result, usage, model } = await ai.run(query, context, { signal: abort.signal,
        presets: usePresets ? () => db.library.find({ owner: req.account.id, kind: 'preset' },
          { projection: { _id: 0, title: 1, body: 1 } }).sort({ updatedAt: -1 }).limit(8).toArray() : undefined,
        onDelta: stream ? delta => send('delta', delta) : undefined })
      if (usage) {
        const inputPrice = env.INPUT_USD_PER_MILLION === undefined ? NaN : Number(env.INPUT_USD_PER_MILLION)
        const outputPrice = env.OUTPUT_USD_PER_MILLION === undefined ? NaN : Number(env.OUTPUT_USD_PER_MILLION)
        const cost = [inputPrice, outputPrice].every(price => Number.isFinite(price) && price >= 0)
          ? (inputPrice * usage.input_tokens + outputPrice * usage.output_tokens) / 1e6 : null
        await db.pool.query('INSERT INTO usage_events(account_id,model,input_tokens,output_tokens,estimated_usd) VALUES($1,$2,$3,$4,$5)',
          [req.account.id, model, usage.input_tokens, usage.output_tokens, cost])
        await db.redis.del('usage:' + req.account.id)
      }
      if (stream) { send('result', result); res.end() } else res.json(result)
    } catch (error) {
      if (abort.signal.aborted) return
      console.error('Assistant request failed', res.getHeader('X-Request-ID'), error.name)
      if (!res.headersSent) fail(502, 'Assistant request failed')
      send('error', { error: 'Assistant request failed' })
      res.end()
    }
  })
  api.post('/billing/checkout', limit, async (req, res) => {
    if (!stripe || !env.STRIPE_PRICE_ID) fail(503, 'Billing unavailable')
    const checkout = await stripe.checkout.sessions.create({
      mode: 'payment', line_items: [{ price: env.STRIPE_PRICE_ID, quantity: 1 }],
      client_reference_id: req.account.id, customer_email: req.account.email,
      success_url: origin + '/billing?checkout=complete', cancel_url: origin + '/billing',
    })
    res.status(201).json({ url: checkout.url })
  })
  api.use((_, res) => res.status(404).json({ error: 'Endpoint not found' }))
  api.use((error, _, res, next) => {
    if (res.headersSent) return next(error)
    if (error instanceof ZodError) return res.status(400).json({ error: error.issues.map(issue => issue.path.join('.') + ': ' + issue.message).join('. ') })
    const status = error.code === 'LIMIT_FILE_SIZE' ? 413 : error instanceof multer.MulterError ? 400 : error.status || 500
    if (status >= 500) console.error('API error', res.getHeader('X-Request-ID'), error.name)
    res.status(status).json({ error: status === 500 ? 'Unexpected server error' : error.message })
  })
  return { api, session }
}
