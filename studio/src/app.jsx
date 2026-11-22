import React, { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { api, readEvents } from './http.js'

function useData(path, version = 0) {
  const [state, set] = useState({ loading: true })
  useEffect(() => {
    const controller = new AbortController()
    set({ loading: true })
    api(path, { signal: controller.signal }).then(data => set({ data }))
      .catch(error => { if (!controller.signal.aborted) set({ error }) })
    return () => controller.abort()
  }, [path, version])
  return state
}

function ErrorText({ error }) {
  return error && <p role="alert" className="alert alert-error my-3">{error.message}</p>
}

function Login({ done }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState()
  const [busy, setBusy] = useState(false)
  const { data } = useData('/auth/options')
  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(undefined)
    try {
      await api('/auth/' + event.nativeEvent.submitter.value, { method: 'POST', body: { email, password } })
      done()
    } catch (error) { setError(error) }
    finally { setBusy(false) }
  }
  return <section className="max-w-md">
    <h2 className="text-2xl font-bold mb-4">Sign in to Studio</h2>
    <form onSubmit={submit} className="space-y-3">
      <label className="block">Email<input className="input w-full mt-1" required type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label className="block">Password<input className="input w-full mt-1" required minLength={10} maxLength={128} type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} /></label>
      <div className="flex flex-wrap gap-2"><button className="btn btn-primary" disabled={busy} value="login">Sign in</button><button className="btn" disabled={busy} value="register">Create account</button></div>
    </form>
    {data?.google && <a className="link inline-block mt-3" href="/api/auth/google">Continue with Google</a>}
    <ErrorText error={error} />
  </section>
}

function Library() {
  const [version, refresh] = useState(0)
  const { data, loading, error } = useData('/library', version)
  const summary = useData('/library/summary', version)
  const empty = { title: '', body: '', kind: 'note' }
  const [draft, set] = useState(empty)
  const [failure, fail] = useState()
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const socket = new WebSocket(location.origin.replace(/^http/, 'ws') + '/events')
    socket.onmessage = event => {
      if (JSON.parse(event.data).type === 'library.changed') refresh(n => n + 1)
    }
    socket.onopen = () => refresh(n => n + 1)
    return () => socket.close()
  }, [])
  async function change(path, method, body) {
    setBusy(true)
    fail(undefined)
    try { await api(path, { method, body }); refresh(n => n + 1); return true }
    catch (error) { fail(error); return false }
    finally { setBusy(false) }
  }
  return <section>
    <h2 className="text-2xl font-bold mb-2">Library</h2>
    <p className="mb-4">{summary.data?.map(item => item.count + ' ' + item._id + (item.count === 1 ? '' : 's')).join(' · ')}</p>
    <ErrorText error={failure || error || summary.error} />
    <div className="grid gap-6 md:grid-cols-2">
      <form className="space-y-3" onSubmit={async e => {
        e.preventDefault()
        const { _id, ...body } = draft
        if (await change(_id ? '/library/' + _id : '/library', _id ? 'PUT' : 'POST', body)) set(empty)
      }}>
        <label className="block">Type<select className="select w-full mt-1" value={draft.kind} onChange={e => set({ ...draft, kind: e.target.value })}><option value="note">Note</option><option value="preset">Command preset</option></select></label>
        <label className="block">Title<input className="input w-full mt-1" required maxLength={100} value={draft.title} onChange={e => set({ ...draft, title: e.target.value })} /></label>
        <label className="block">Text<textarea className="textarea w-full mt-1 min-h-32" required maxLength={12000} value={draft.body} onChange={e => set({ ...draft, body: e.target.value })} /></label>
        <button className="btn btn-primary" disabled={busy}>{draft._id ? 'Save changes' : 'Add entry'}</button>
        {draft._id && <button type="button" className="btn ml-2" onClick={() => set(empty)}>Cancel edit</button>}
      </form>
      <div className="space-y-3">
        <form className="flex flex-wrap gap-2" onSubmit={async e => {
          e.preventDefault()
          const form = e.currentTarget
          if (await change('/library/upload', 'POST', new FormData(form))) form.reset()
        }}>
          <input aria-label="Upload a text note" className="file-input max-w-full" required type="file" name="file" accept=".txt,.md" />
          <button className="btn" disabled={busy}>Upload note</button>
        </form>
        {loading && <p role="status">Loading library…</p>}
        {data?.length === 0 && <p>Add a note or a reusable command.</p>}
        {data?.map(item => <article key={item._id} className="card bg-base-200 p-4">
          <h3 className="font-semibold break-words">{item.title}</h3><p className="line-clamp-2 break-words">{item.body}</p>
          <div className="flex gap-2 mt-2"><button className="btn btn-sm" disabled={busy} onClick={async () => {
            try { const { _id, title, kind, body } = await api('/library/' + item._id); set({ _id, title, kind, body }) }
            catch (error) { fail(error) }
          }}>Edit</button><button className="btn btn-sm" disabled={busy} onClick={() => change('/library/' + item._id, 'DELETE')}>Delete</button></div>
        </article>)}
      </div>
    </div>
  </section>
}

function Assistant({ available }) {
  const [query, setQuery] = useState('')
  const [useNotes, setNotes] = useState(false)
  const [usePresets, setPresets] = useState(false)
  const [response, setResponse] = useState()
  const [status, setStatus] = useState()
  const [bytes, setBytes] = useState(0)
  const [error, setError] = useState()
  const [busy, setBusy] = useState(false)
  return <section className="max-w-2xl">
    <h2 className="text-2xl font-bold mb-4">Assistant</h2>
    {!available && <p className="alert mb-4">The server needs an OpenAI API key to answer.</p>}
    <form className="space-y-3" onSubmit={async e => {
      e.preventDefault()
      setBusy(true); setResponse(undefined); setStatus(undefined); setError(undefined); setBytes(0)
      try {
        const stream = await api('/assistant', { method: 'POST', body: { query, useNotes, usePresets } })
        await readEvents(stream, (event, payload) => {
          if (event === 'status') setStatus(payload)
          if (event === 'delta') setBytes(n => n + payload.length)
          if (event === 'result') setResponse(payload)
          if (event === 'error') throw new Error(payload.error)
        })
      } catch (error) { setError(error) }
      finally { setBusy(false) }
    }}>
      <label className="block">Request<textarea required maxLength={2000} className="textarea w-full mt-1 min-h-28" value={query} onChange={e => setQuery(e.target.value)} /></label>
      <label className="flex items-center gap-2"><input type="checkbox" className="checkbox" checked={useNotes} onChange={e => setNotes(e.target.checked)} /> Include relevant saved notes</label>
      <label className="flex items-center gap-2"><input type="checkbox" className="checkbox" checked={usePresets} onChange={e => setPresets(e.target.checked)} /> Let Assistant look up saved presets</label>
      <button className="btn btn-primary" disabled={!available || busy}>Ask</button>
    </form>
    {busy && <p role="status" className="mt-4">{status?.stage || 'Preparing request'}… {bytes > 0 && bytes + ' characters received'}</p>}
    <ErrorText error={error} />
    {response && <article className="card bg-base-200 p-4 mt-4"><p className="whitespace-pre-wrap">{response.summary}</p>
      {response.command && <p className="mt-2">Suggested desktop command <kbd className="kbd">{response.command}</kbd></p>}
      {status?.references?.length > 0 && <p className="mt-2 text-sm">Notes consulted · {status.references.map(note => note.title).join(', ')}</p>}
    </article>}
  </section>
}

function Usage({ billing }) {
  const { data, error, loading } = useData('/usage')
  const [failure, fail] = useState()
  const [busy, setBusy] = useState(false)
  return <section className="max-w-xl">
    <h2 className="text-2xl font-bold mb-4">Usage and billing</h2>
    {loading && <p role="status">Loading usage…</p>}
    <ErrorText error={error || failure} />
    {data && <dl className="space-y-2 mb-6">
      <div><dt className="font-semibold">Plan</dt><dd>{data.plan}</dd></div>
      <div><dt className="font-semibold">Requests in 30 days</dt><dd>{data.requests}</dd></div>
      <div><dt className="font-semibold">Tokens in 30 days</dt><dd>{data.tokens}</dd></div>
      <div><dt className="font-semibold">Estimated cost in 30 days</dt><dd>{data.estimated_usd == null ? 'Unavailable' : '$' + Number(data.estimated_usd).toFixed(4)}</dd></div>
    </dl>}
    {billing && data?.plan !== 'Supporter' && <button className="btn btn-primary" disabled={busy} onClick={async () => {
      setBusy(true)
      try { location.assign((await api('/billing/checkout', { method: 'POST' })).url) }
      catch (error) { fail(error); setBusy(false) }
    }}>Open Stripe Checkout</button>}
  </section>
}

function Weather() {
  const [city, setCity] = useState('')
  const [result, setResult] = useState()
  const [error, setError] = useState()
  const [busy, setBusy] = useState(false)
  return <section className="max-w-lg">
    <h2 className="text-2xl font-bold mb-4">Weather</h2>
    <form className="space-y-3" onSubmit={async e => {
      e.preventDefault()
      setBusy(true); setError(undefined); setResult(undefined)
      try { setResult(await api('/places/weather?' + new URLSearchParams({ city }))) }
      catch (error) { setError(error) }
      finally { setBusy(false) }
    }}>
      <label className="block">City<input className="input w-full mt-1" required minLength={2} maxLength={80} value={city} onChange={e => setCity(e.target.value)} /></label>
      <button className="btn" disabled={busy}>{busy ? 'Looking up…' : 'Get weather'}</button>
    </form>
    <ErrorText error={error} />
    {result && <p className="mt-4">{result.city} · {result.celsius} °C</p>}
  </section>
}

function Admin() {
  const { data, error, loading } = useData('/admin/accounts')
  return <section><h2 className="text-2xl font-bold mb-4">Accounts</h2>
    {loading && <p role="status">Loading accounts…</p>}
    <ErrorText error={error} />
    {data && <ul>{data.map(account => <li key={account.id}>{account.email} · {account.role}</li>)}</ul>}
  </section>
}

export function App() {
  const [version, refresh] = useState(0)
  const [logoutError, setLogoutError] = useState()
  const account = useData('/me', version)
  return <div className="min-h-screen bg-base-100 text-base-content">
    <header className="border-b border-base-300"><div className="mx-auto max-w-5xl px-5 py-4 flex flex-wrap gap-3 justify-between items-center">
      <h1 className="text-xl font-bold">Hey Baby Studio</h1>
      {account.data && <button className="btn btn-sm" onClick={async () => {
        try { await api('/auth/logout', { method: 'POST' }); setLogoutError(undefined); refresh(n => n + 1) }
        catch (error) { setLogoutError(error) }
      }}>Sign out</button>}
    </div></header>
    <main className="mx-auto max-w-5xl px-5 py-8">
      <ErrorText error={logoutError} />
      {account.loading ? <p role="status">Loading workspace…</p> : account.error?.status === 401 ?
        <Login done={() => refresh(n => n + 1)} /> : account.error ? <ErrorText error={account.error} /> :
        <>
          <nav aria-label="Workspace" className="flex flex-wrap gap-3 mb-7">
            {[['/', 'Assistant'], ['/library', 'Library'], ['/weather', 'Weather'], ['/billing', 'Usage'], ...(account.data?.role === 'admin' ? [['/admin', 'Accounts']] : [])]
              .map(([path, label]) => <NavLink end key={path} to={path} className={({ isActive }) => isActive ? 'btn btn-sm btn-primary' : 'btn btn-sm'}>{label}</NavLink>)}
          </nav>
          <Routes><Route path="/" element={<Assistant available={account.data?.ai} />} />
            <Route path="/library" element={<Library />} /><Route path="/weather" element={<Weather />} />
            <Route path="/billing" element={<Usage billing={account.data?.billing} />} />
            <Route path="/admin" element={<Admin />} /><Route path="*" element={<p>Page not found.</p>} /></Routes>
        </>}
    </main>
  </div>
}
