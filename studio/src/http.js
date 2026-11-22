export async function api(path, { body, method, signal } = {}) {
  const form = body instanceof FormData
  const response = await fetch('/api' + path, { method, signal,
    headers: body && !form ? { 'Content-Type': 'application/json' } : undefined,
    body: form ? body : body && JSON.stringify(body) })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw Object.assign(new Error(data.error || 'Request failed'), { status: response.status })
  }
  if (response.status === 204) return
  if (response.headers.get('content-type')?.startsWith('text/event-stream')) return response
  return response.json()
}
export async function readEvents(response, receive) {
  let buffer = ''
  for await (const chunk of response.body.pipeThrough(new TextDecoderStream())) {
    buffer += chunk
    let end
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const [event, data] = buffer.slice(0, end).split('\n')
      buffer = buffer.slice(end + 2)
      receive(event.slice(7), JSON.parse(data.slice(6)))
    }
  }
}
