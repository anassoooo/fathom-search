# Deployment

Single source of truth for every hosted resource: names, regions, and which setting
goes where. **Secrets never go in git or chat.** They go in the hosting dashboards,
in your password manager, and (for local scripts only) in gitignored `.env*` files.

## Architecture (all free tiers)

```
Browser ─▶ Vercel  (web/, Next.js)  ── server-side ──▶ Hugging Face Space (backend/, FastAPI, Docker)
                │                                              │            │
                ▼                                              ▼            ▼
           Neon Postgres                               Qdrant Cloud     Groq API
           (users, carts, events)                      (35,736 products) (gpt-oss-20b)
```

Region: put everything in **Europe (Frankfurt, `eu-central-1`)** where a choice exists,
so the web → backend → database hops stay short.

## 1. Qdrant Cloud: vector database

| Setting | Value |
|---|---|
| Account | https://cloud.qdrant.io (sign in with GitHub) |
| Cluster name | `vio` |
| Tier | Free (1 GB): enough for ~35.7K products × (384 + 512 dims) + BM25 |
| Cloud / region | AWS, `eu-central-1` (Frankfurt) |
| API key name | `vio-backend` (cluster access, read **and** write: ingest needs write) |
| Collection | `vio_products_v2`. **Do not create it by hand.** `vio ingest` creates it with the right schema and indexes. |

Copy the **cluster URL** (`https://<id>.eu-central-1-0.aws.cloud.qdrant.io:6333`) and the
**API key** (shown once) into your password manager.

## 2. Groq: LLM API (already set up)

| Setting | Value |
|---|---|
| Account | https://console.groq.com (free plan) |
| Production key name | `vio-prod`. Create a **second** key for the hosted backend, so the local key can be revoked independently. |
| Models | `openai/gpt-oss-20b` (live query understanding), `openai/gpt-oss-120b` (offline eval only) |

Free-plan quotas are **per organization and per model**: 200K tokens/day and 8K
tokens/minute each. Live search uses gpt-oss-20b; the daily eval job uses gpt-oss-120b,
so they don't compete. If the quota runs out, search still works (`degraded: ["llm"]`).

## 3. Hugging Face Spaces: backend API

| Setting | Value |
|---|---|
| Account | https://huggingface.co (username: `<hf-username>`) |
| Space name | `vio-search-api` → `https://<hf-username>-vio-search-api.hf.space` |
| SDK | **Docker** (blank template) |
| Hardware | CPU basic (free: 2 vCPU, 16 GB RAM). It sleeps after ~48 h idle; the first request wakes it in ~1–2 min. |
| Visibility | Public (the API holds no secrets in code; keys are Space secrets) |
| Access token for CI | Settings → Access Tokens → name `vio-github-deploy`, role **Write**. Stored as the GitHub repo secret `HF_TOKEN`. |

**Space → Settings → Variables and secrets:**

| Kind | Name | Value |
|---|---|---|
| Secret | `QDRANT_URL` | Qdrant cluster URL (step 1) |
| Secret | `QDRANT_API_KEY` | Qdrant `vio-backend` key |
| Secret | `LLM_API_KEY` | Groq `vio-prod` key |
| Variable | `QDRANT_COLLECTION` | `vio_products_v2` |
| Variable | `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| Variable | `LLM_MODEL_QUERY` | `openai/gpt-oss-20b` |
| Variable | `LLM_REASONING_EFFORT` | `low` |
| Variable | `ONNX_DEVICE` | `cpu` |
| Variable | `ONNX_THREADS` | `2` (the free Space has 2 vCPUs) |
| Variable | `CORS_ORIGINS` | `["https://vio-web.vercel.app"]` |

## 4. Neon: Postgres for the web app

| Setting | Value |
|---|---|
| Account | https://neon.tech (sign in with GitHub) |
| Project name | `vio` (project id `icy-rain-24708274`) |
| Region | AWS `eu-central-1` (Frankfurt) |
| Database name | `neondb` (Neon's default) |
| Role | `neondb_owner` (default owner) |
| Branch | `production` (default) |

From **Connect**, copy two strings. Remove `&channel_binding=require` and keep only
`?sslmode=require`: Prisma's engine doesn't reliably support channel binding, and SSL is
still enforced.
- **Pooled** (host contains `-pooler`): for the running app → `DATABASE_URL`
- **Direct** (no `-pooler`): for migrations → `DIRECT_URL`

## 5. Vercel: web app

| Setting | Value |
|---|---|
| Account | https://vercel.com (sign in with GitHub) |
| Project name | `vio-web` → `https://vio-web.vercel.app` (if taken, tell me the actual URL) |
| Import | GitHub repo `anassoooo/vio-shop-organized`, branch `main` |
| Root directory | `web` |
| Framework preset | Next.js |
| Build command | `npx prisma migrate deploy && next build` |

**Project → Settings → Environment Variables** (Production):

| Name | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** string |
| `DIRECT_URL` | Neon **direct** string |
| `BACKEND_URL` | `https://<hf-username>-vio-search-api.hf.space` |
| `AUTH_SECRET` | a new random value: `openssl rand -hex 32` (not the local one) |
| `ADMIN_EMAILS` | `admin@vio.test` (or your real email) |

## 6. GitHub: repository and CI

| Setting | Value |
|---|---|
| Repo | `anassoooo/vio-shop-organized` (public) |
| Default branch | `main` |
| Actions secret | `HF_TOKEN` = Hugging Face `vio-github-deploy` token (step 3) |

## Loading the catalog into Qdrant Cloud

Done once from your laptop (GPU, ~15 min, images already cached). Create
`backend/.env.cloud` (gitignored; never commit it):

```
QDRANT_URL=<Qdrant cluster URL>
QDRANT_API_KEY=<Qdrant vio-backend key>
```

Then:

```bash
cd backend
set -a && source .env.cloud && set +a
ONNX_DEVICE=cuda uv run vio ingest --csv ../data/processed/vio_EDA.csv --image-dir ../data/images
```

## What to tell Claude (no secrets)

1. Your Hugging Face username
2. The Qdrant cluster URL's region part (e.g. `eu-central-1-0.aws`), only to confirm the region
3. The final Vercel URL, if it isn't `vio-web.vercel.app`
4. "Done" once `backend/.env.cloud` exists and the dashboard secrets are filled in

## Naming conventions

| Thing | Name |
|---|---|
| Qdrant cluster / collection | `vio` / `vio_products_v2` |
| HF Space | `vio-search-api` |
| Neon project / database / branch | `vio` / `neondb` / `production` |
| Vercel project | `vio-web` |
| Groq keys | `vio-local` (laptop), `vio-prod` (Space) |
| HF token | `vio-github-deploy` |
| Local-only env files | `backend/.env`, `backend/.env.cloud`, `web/.env` (all gitignored) |
