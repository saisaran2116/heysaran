# Hey Baby Studio

Studio is the web companion to the local Hey Baby desktop assistant. Save
notes and reusable command presets, ask for a structured answer, look up
weather, and review account usage. To use a suggested command or saved
preset, copy it into the desktop assistant and review it there.

React and daisyUI render the browser interface. Express serves REST, SSE,
WebSockets and the server-rendered route shell. PostgreSQL owns accounts,
plans, memberships and usage. MongoDB owns the library and stores embeddings
inside note documents while referencing the owning PostgreSQL account by UUID.
Redis caches usage and weather. The browser makes same-origin requests.
Hey Baby desktop operates independently and keeps microphone input local.

## Run locally

```sh
cd studio
cp .env.example .env
node -e 'console.log(require("crypto").randomBytes(32).toString("hex"))'
```

Paste the generated secret into `JWT_SECRET`. Run `docker compose up -d --build`
and visit http://localhost:3000. Use `docker compose down` to stop the stack.
For development with stores supplied separately, use `npm ci`, `npm run build`
and `npm start`. The compose defaults are for local use.

## Provider setup

- Set `OPENAI_API_KEY` for Assistant and new note embeddings. Enable **Include
  relevant saved notes** to send retrieved snippets with a question. Enable
  preset lookup to let the model make one read-only tool call followed by a
  structured answer. Re-save older notes to generate missing embeddings.
- Set `INPUT_USD_PER_MILLION` and `OUTPUT_USD_PER_MILLION` for the configured
  generation model. The usage report covers generation calls, including the
  tool step. Embedding costs are excluded.
- Set Google OAuth credentials and register `PUBLIC_URL/api/auth/google/callback`.
- For Stripe, start with test credentials and a one-time Price. Configure
  `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, and `STRIPE_WEBHOOK_SECRET`. Forward
  signed events to `/api/billing/webhook`. A verified paid checkout updates the
  PostgreSQL membership transactionally. The return URL alone grants nothing.
- Set an account's role to `admin` in PostgreSQL to enable Accounts. Public
  registration creates members.

## Deploy

Build the Dockerfile and deploy the image behind an HTTPS reverse proxy that
forwards WebSocket upgrades and does not buffer SSE. Set `PUBLIC_URL` to the
public origin, `HOST=0.0.0.0`, and the runtime service URLs and secrets through
the host secret manager. Set `TRUST_PROXY=1` only when there is exactly one
trusted proxy in front of the app. Keep the DB services on private networks.
Deploy a single instance for in-process WebSocket notifications and cron.
GET `/api/health` checks all three stores. Client assets and SSR run in the
same image as the API, so both deployments share a version.

## Verify and contribute

Run `npm test` for unit checks. With a **disposable stack** running, run
`TEST_STUDIO_URL=http://localhost:3000 npm test` to include real API and DB
checks. The integration test creates disposable accounts in that database.
Run `npm run eval` with a provider key for live model checks.
The workflow runs the build and integration tests on pushes and PRs.

From a Git checkout, work on a branch, run the checks, stage the changed files,
commit and open a PR. The workspace can be added to an existing repo or initialized
with `git init`. Do not commit `.env`, dependency directories, models or build output.
