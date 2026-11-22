import test from 'node:test'
import assert from 'node:assert/strict'
import { hash, matches, sessions } from './auth.js'
import { answer } from './assistant.js'
import { readEvents } from '../src/http.js'

test('passwords are salted and checked; tampered JWT is rejected', async () => {
  const digest = await hash('password-for-testing')
  assert.notEqual(digest, await hash('password-for-testing'))
  assert.equal(await matches('password-for-testing', digest), true)
  assert.equal(await matches('wrong password', digest), false)
  const codec = sessions('a test secret that is at least 32 chars')
  const token = await codec.issue('test-user')
  assert.equal(await codec.read({ headers: { cookie: 'hb_session=' + token } }), 'test-user')
  assert.equal(await codec.read({ headers: { cookie: 'hb_session=' + token + 'x' } }), undefined)
})

test('schema rejects commands outside the desktop allowlist', () => {
  assert.equal(answer.safeParse({ summary: 'Done', kind: 'command', command: 'run arbitrary command' }).success, false)
  assert.equal(answer.safeParse({ summary: 'Open Calculator', kind: 'command', command: 'open calculator' }).success, true)
})

test('SSE handles records divided across chunks', async () => {
  const encoder = new TextEncoder()
  const body = new ReadableStream({ start(controller) {
    for (const piece of ['event: delta\ndata: "hel', 'lo"\n\nevent: result\ndata: ', '{"summary":"hello"}\n\n']) controller.enqueue(encoder.encode(piece))
    controller.close()
  } })
  const events = []
  await readEvents(new Response(body), (...event) => events.push(event))
  assert.deepEqual(events, [['delta', 'hello'], ['result', { summary: 'hello' }]])
})
