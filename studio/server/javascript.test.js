import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs'

test('event loop orders synchronous code, promise microtasks, and timer callbacks', async () => {
  const order = []
  const timer = new Promise(resolve => setTimeout(() => { order.push('timer'); resolve() }, 0))
  const microtask = Promise.resolve().then(() => order.push('promise'))
  order.push('sync')
  await Promise.all([timer, microtask])
  assert.deepEqual(order, ['sync', 'promise', 'timer'])
})

test('callbacks and promises consume the same asynchronous API', async () => {
  const path = new URL('../package.json', import.meta.url)
  const callback = readFile
  const content = await new Promise((resolve, reject) => {
    callback(path, 'utf8', (error, data) => error ? reject(error) : resolve(data))
  })
  assert.equal(JSON.parse(content).name, 'hey-baby-studio')
})

test('functions are hoisted and closures keep independent state', () => {
  const first = counter()
  const second = counter()
  assert.deepEqual([first(), first(), second()], [1, 2, 1])

  function counter() {
    let count = 0
    return () => ++count
  }
})
