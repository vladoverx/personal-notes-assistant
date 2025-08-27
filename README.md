# Personal Notes Assistant

Lightweight, production-ready notes app with a clean FastAPI backend, a static JS frontend, and AI-powered enrichment. It uses Supabase for auth and data, OpenAI for chat and notes enrichment, and a simple production deployment path: backend on AWS EC2 (Docker + Caddy) and frontend on Vercel.

## Tools & architecture (at a glance)
- **Backend (FastAPI + Gunicorn/Uvicorn)**: Typed, fast, and robust REST + SSE server. Structured settings via Pydantic; packaged and installed with `uv` during image build.
- **Data & Auth (Supabase)**: PostgREST with row-level security; per-request bearer ensures user isolation. Admin client for background jobs.
- **AI (OpenAI)**: Chat streaming and note enrichment (tags, embeddings) with the Responses API.
- **Frontend (static JS, Vercel)**: Vanilla JS single-page UI. Runtime `window.__APP_CONFIG__` or Vercel rewrites make the API base configurable.
- **Infra**: Production: backend runs as a Docker container on EC2 behind Caddy; frontend is deployed to Vercel.

## Highlights
- **Notes CRUD + search** with Supabase-backed storage and hybrid search (lexical + embeddings).
- **Streaming chat (SSE)** powered by OpenAI, with tool-use events.
- **Tag enrichment & embeddings** via background workers.
- **Security-first defaults**: CORS allowlist, trusted hosts, CSP/HSTS, and RLS via Supabase.

## Prerequisites
- Install `uv` (Python package/deps manager). See `https://docs.astral.sh/uv/`.
- Install the Supabase CLI: `https://supabase.com/docs/guides/cli`.
- Have a Supabase project (URL, anon key, service_role key).
- Have an OpenAI API key.

## Quickstart
1. Copy backend environment template and fill values:
```bash
cp backend/.env.example backend/.env
```
2. Create a Supabase project in the dashboard.
3. Get API credentials from Settings → API:
   - Project URL
   - anon public key
   - service_role key (server-side/admin only)
4. Install and authenticate the Supabase CLI:
```bash
supabase login
```
5. Link this repo to your cloud project (replace with your project ref):
```bash
supabase link --project-ref <your-project-ref>
```
6. Push database schema (migrations) to cloud:
```bash
supabase db push
```
   - Applies SQL from `supabase/migrations/` to your linked project.
7. Configure the frontend API base for local dev:
   - Edit `frontend/app-config.js` and set:
```js
window.__APP_CONFIG__ = {
  API_BASE_URL: "http://127.0.0.1:8000/api/v1"
};
```
8. Start the app locally (backend + static frontend):
```bash
chmod +x run.sh
./run.sh
```
   - Backend: `http://localhost:8000`
   - Frontend: `http://localhost:3000`

## Configuration (backend `APP_` variables)
Required in `backend/.env`:
- **APP_SUPABASE_URL**: Supabase project URL
- **APP_SUPABASE_ANON_KEY**: Supabase anon key
- **APP_SUPABASE_SERVICE_ROLE_KEY**: Supabase service role key (server-side/admin only)
- **APP_OPENAI_API_KEY**: OpenAI API key

## API surface (selected)
All endpoints are under `/api/v1`:
- **Auth**: `POST /auth/signup`, `POST /auth/signin`, `POST /auth/refresh`, `POST /auth/signout`, `GET /auth/validate`, `GET /auth/session`
- **Notes**: `POST /notes/`, `GET /notes/`, `GET /notes/{id}`, `PATCH /notes/{id}`, `DELETE /notes/{id}`, `POST /notes/search`
- **Chat**: `POST /chat/stream` (server-sent events)
- **Metadata**: `GET /metadata/note-types`, `GET /metadata/taxonomy`
- **Health**: `GET /health`, `GET /health/ready`

### Project structure
```text
.
├── backend/
│  ├── Dockerfile
│  ├── pyproject.toml
│  ├── uv.lock
│  ├── docker/
│  │  └── start.sh
│  └── app/
│     ├── main.py                  # App factory, middleware, router mount
│     ├── config.py                # Pydantic settings (APP_* env)
│     ├── dependencies.py          # DI: auth, repo/service wiring, rate limit
│     ├── api/
│     │  ├── middleware/security.py# security headers, CSP, HSTS (https)
│     │  └── v1/
│     │     ├── router.py          # API router
│     │     ├── endpoints/
│     │     │  ├── auth.py         # signup/signin/signout/validate/refresh
│     │     │  ├── notes.py        # CRUD + search (auth required)
│     │     │  ├── chat.py         # SSE streaming endpoint
│     │     │  ├── health.py       # health and readiness
│     │     │  └── taxonomy.py     # note types + user tag taxonomy
│     │     └── schemas/
│     ├── core/
│     │  ├── models/               # Pydantic domain models
│     │  ├── repositories/         # Data access interfaces + implementations
│     │  ├── schemas/              # App-layer schemas
│     │  └── services/             # Business logic
│     ├── background/              # Fire-and-forget jobs
│     ├── db/
│     │  └── base.py               # Supabase client (request/admin)
│     └── utils/
├── frontend/
│  ├── index.html
│  ├── styles.css
│  ├── vercel.json                   # rewrite /api/* → your API domain
│  ├── app-config.js
│  └── src/
│     ├── main.js
│     ├── config.js                # API_BASE_URL + auth flags
│     ├── app/ui.js                # shell + routing
│     ├── features/                # auth, notes, chat controller
│     │  ├── auth.js
│     │  ├── notes.js
│     │  └── chat-controller.js
│     ├── services/api.js          # fetch layer + SSE polyfill
│     ├── lib/
│     └── utils/
├── supabase/
│  ├── config.toml                 # Local CLI config; reference for cloud
│  └── migrations/                 # SQL applied via `supabase db push`
├── run.sh                          # Local dev runner (uv + static frontend)
├── Caddyfile
└── docker-compose.yml
```

## Health & readiness
- Liveness: `GET /api/v1/health`
- Readiness: `GET /api/v1/health/ready`

## Security defaults
- **CORS & Trusted Hosts**: Restrict origins and hosts via env.
- **Security headers**: CSP, HSTS (in HTTPS), X-Frame-Options, and no-store caching.
- **RLS enforcement**: Per-request Supabase client uses the caller's bearer for PostgREST.
- **Rate limiting**: In-memory IP rate limits for auth endpoints with `Retry-After` hints.

## Notes
- Backend runs on Python `3.13`; dependencies are managed with `uv` during container builds.
- Frontend reads `API_BASE_URL` from runtime config injected by the container entrypoint.
