import express from 'express'
import { WebSocketServer } from 'ws'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import cron from 'node-cron'
import { createApi } from './api.js'
import { connect } from './db.js'

const env = process.env
for (const name of ['DATABASE_URL', 'MONGO_URL', 'REDIS_URL', 'JWT_SECRET', 'PUBLIC_URL']) {
  if (!env[name]) throw new Error(name + ' is required')
}
if (env.JWT_SECRET.length < 32) throw new Error('JWT_SECRET must be at least 32 characters')
const [template, { render }] = await Promise.all([
  readFile(new URL('../dist/index.html', import.meta.url), 'utf8'),
  import('../dist/server/ssr.js'),
])
const db = await connect(env)
const app = express()
app.disable('x-powered-by')
if (env.TRUST_PROXY === '1') app.set('trust proxy', 1)
const server = createServer(app)
const wss = new WebSocketServer({ noServer: true, maxPayload: 1024 })
const { api, session } = createApi(db, env, (owner, event) => {
  for (const socket of wss.clients) if (socket.owner === owner && socket.readyState === 1) socket.send(JSON.stringify(event))
})
app.use('/api', api)
app.use(express.static(new URL('../dist', import.meta.url).pathname, { index: false, redirect: false }))
app.get(/.*/, (req, res) => {
  if (!['/', '/library', '/weather', '/billing', '/admin'].includes(req.path)) res.status(404)
  res.set('Cache-Control', 'no-store').send(template.replace('<div id="root"></div>', () => '<div id="root">' + render(req.originalUrl) + '</div>'))
})
server.on('upgrade', async (req, socket, head) => {
  const discard = () => socket.destroy()
  socket.on('error', discard)
  if (req.url !== '/events' || req.headers.origin !== new URL(env.PUBLIC_URL).origin) return discard()
  const owner = await session.read(req)
  if (!owner || socket.destroyed) return discard()
  socket.removeListener('error', discard)
  wss.handleUpgrade(req, socket, head, ws => {
    ws.owner = owner
    const timeout = setTimeout(() => ws.close(1000), 15 * 60_000)
    ws.on('close', () => clearTimeout(timeout))
  })
})
const task = cron.schedule('15 3 * * *', async () => {
  try { await db.pool.query("DELETE FROM usage_events WHERE created_at < now() - interval '90 days'") }
  catch (error) { console.error('Usage retention job', error.name) }
}, { timezone: 'UTC', noOverlap: true })
server.listen(Number(env.PORT || 3000), env.HOST || '127.0.0.1', () => console.log('Studio ready at ' + env.PUBLIC_URL))
for (const signal of ['SIGTERM', 'SIGINT']) process.once(signal, () => {
  task.stop()
  for (const socket of wss.clients) socket.terminate()
  server.close(async () => { await db.close() })
})
