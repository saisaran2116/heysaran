# Assessment checklist

Paths below are relative to Studio unless noted. Hosting and external provider
verification depend on the target account and its credentials.

| # | Concept | Evidence |
|---|---|---|
| 1 | React composition | `src/app.jsx` composes routed screens and shared error state |
| 2 | useState | Controlled forms, assistant state, and refresh versions |
| 3 | useEffect | Abortable requests and WebSocket lifecycle |
| 4 | API fetching | `src/http.js` |
| 5 | Loading and errors | Workspace, library, weather, and assistant states |
| 6 | Controlled forms | Sign-in, library editor, assistant request |
| 7 | Form validation | Native constraints plus server Zod schemas |
| 8 | Routing | React Router in client and SSR entries |
| 9 | Responsive styling | daisyUI and responsive library grid |
| 10 | Frontend deployment | Production Vite assets served by the Docker image · local deployment; public target needed |
| 11 | Problem modeling | Accounts, plans, usage, notes, presets, command suggestions |
| 12 | System integration | Architecture in `README.md`; Compose runs the full stack |
| 13 | REST | `server/api.js` library collection and item routes |
| 14 | HTTP status codes | API integration checks for 201, 204, 400, 401, 403, 404 |
| 15 | Request validation | Credentials, resource IDs, library and assistant Zod schemas |
| 16 | Server error handling | Express error middleware and SSE terminal error |
| 17 | Middleware | Identity, JSON/raw parsing, origin checks and rate limits |
| 18 | File uploads | UTF-8 Markdown and text through Multer |
| 19 | Backend deployment | Production container and health endpoint · local deployment; public target needed |
| 20 | Mongo schema | Notes and presets in `server/api.js` and `server/db.js` |
| 21 | Mongo CRUD | Library POST, GET, PUT and DELETE |
| 22 | Embed/reference | Embedding inside note; owner UUID references PostgreSQL |
| 23 | Mongo aggregation | Library counts grouped by kind |
| 24 | Mongo indexing | Compound index on owner, kind, update time |
| 25 | SQL PK/FK | `server/schema.sql` account, plan, membership, usage |
| 26 | SQL joins | Usage report joins accounts, memberships, plans, events |
| 27 | SQL index | Usage events indexed by account and date |
| 28 | SQL filter/order/group | 30-day usage report; ordered admin list |
| 29 | Normalization | Plan metadata, membership and usage stored separately |
| 30 | ORM | Drizzle account queries |
| 31 | Transactions | Stripe event deduplication and membership update |
| 32 | Password hashing | Salted scrypt |
| 33 | JWT | JOSE issuance and verification with signed HttpOnly cookie |
| 34 | Role checks | Backend admin route enforcement |
| 35 | OAuth | Google authorization flow, state and verified ID token |
| 36 | Injection awareness | SQL parameters, typed input, React text rendering |
| 37 | Rate limiting | Auth, assistant, uploads and provider routes |
| 38 | LLM API | OpenAI Responses API |
| 39 | Prompt design | Trusted instructions separated from query and retrieved notes |
| 40 | Structured output | Strict JSON schema and server parse |
| 41 | Streaming | SSE status, deltas and final answer |
| 42 | Function calling | Read-only preset lookup with owner-scoped query |
| 43 | RAG | Embeddings, cosine retrieval over up to 100 owned notes, opt-in context |
| 44 | LLM eval | `npm run eval` with provider configuration |
| 45 | Prompt injection | Treat notes as data, validate suggestions, no OS execution from web |
| 46 | Usage and cost | Generation usage persisted in PostgreSQL; configurable price estimate |
| 47 | Multi-step agent | Optional model decision → read-only tool → final answer |
| 48 | Git workflow | Branch/PR instructions and GitHub Actions workflow at project root |
| 49 | Secrets | Ignored .env, example variables, runtime-only provider credentials |
| 50 | Unit tests | Auth, schema, SSE and JavaScript behavior |
| 51 | Docker | Multi-stage Dockerfile and Compose |
| 52 | Automated API tests | `server/integration.test.js` with real stores |
| 53 | Redis cache | Usage and weather with expiration |
| 54 | Real time | Authenticated, owner-scoped Library WebSocket events |
| 55 | Cron | Scheduled usage retention |
| 56 | SSR | Express uses Vite-built React server renderer |
| 57 | Payments | Stripe Checkout plus verified webhook, configured in test mode first |
| 58 | Third-party APIs | Open-Meteo, Google, OpenAI and Stripe |
| 59 | JS event loop | Synchronous, microtask and timer ordering test |
| 60 | Promises and callbacks | File operation adapter test and callback-driven WebSocket |
| 61 | async/await | Network, stream reading and storage flows |
| 62 | Closures | Session codec, UI request effect, and independent counters test |
| 63 | Hoisting | Function declaration called before its definition in the JS test |
