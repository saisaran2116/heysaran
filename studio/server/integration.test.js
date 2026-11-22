import test from 'node:test'
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { once } from 'node:events'
import { WebSocket } from 'ws'

test('real stores, account isolation, REST statuses, and SSR', { skip: !process.env.TEST_STUDIO_URL }, async () => {
  const base = process.env.TEST_STUDIO_URL
  const req = (path, { body, cookie, method } = {}) => fetch(base + path, { method,
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(cookie ? { Cookie: cookie } : {}) },
    body: body && JSON.stringify(body) })
  assert.match(await (await req('/library')).text(), /Loading workspace/)
  assert.equal((await req('/api/health')).status, 200)
  assert.equal((await req('/api/library')).status, 401)
  assert.equal((await req('/api/auth/register', { method: 'POST', body: { email: 'bad' } })).status, 400)
  async function register() {
    const response = await req('/api/auth/register', { method: 'POST',
      body: { email: randomUUID() + '@example.test', password: 'test-password-123' } })
    assert.equal(response.status, 201)
    return response.headers.get('set-cookie').split(';')[0]
  }
  const cookie = await register()
  const other = await register()
  const socket = new WebSocket(base.replace(/^http/, 'ws') + '/events', {
    origin: new URL(base).origin, headers: { Cookie: cookie },
  })
  try {
    await once(socket, 'open', { signal: AbortSignal.timeout(3000) })
    const message = once(socket, 'message', { signal: AbortSignal.timeout(3000) })
    const form = new FormData()
    form.set('file', new Blob(['A saved note.'], { type: 'text/plain' }), 'note.txt')
    const uploaded = await fetch(base + '/api/library/upload', {
      method: 'POST', headers: { Cookie: cookie }, body: form,
    })
    assert.equal(uploaded.status, 201)
    assert.deepEqual(JSON.parse((await message)[0].toString()), { type: 'library.changed' })
    const uploadId = (await uploaded.json()).id
    assert.equal((await req('/api/library/' + uploadId, { method: 'DELETE', cookie })).status, 204)
  } finally {
    socket.terminate()
  }
  const record = { kind: 'preset', title: 'Calculator', body: 'open calculator' }
  const created = await req('/api/library', { method: 'POST', cookie, body: record })
  assert.equal(created.status, 201)
  const { id } = await created.json()
  assert.equal((await req('/api/library/' + id, { cookie: other })).status, 404)
  assert.equal((await req('/api/library/' + id, { method: 'PUT', cookie, body: { ...record, title: 'Updated' } })).status, 204)
  assert.equal((await (await req('/api/library/' + id, { cookie })).json()).title, 'Updated')
  assert.deepEqual(await (await req('/api/library/summary', { cookie })).json(), [{ _id: 'preset', count: 1 }])
  assert.equal((await (await req('/api/usage', { cookie })).json()).plan, 'Free')
  assert.equal((await req('/api/admin/accounts', { cookie })).status, 403)
  assert.equal((await req('/api/library/' + id, { method: 'DELETE', cookie })).status, 204)
  assert.equal((await req('/api/library/' + id, { cookie })).status, 404)
})
