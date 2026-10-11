# Deployment

Single source of truth for every hosted resource: names, regions, and which setting
goes where. **Secrets never go in git or chat.** They go in the hosting dashboards,
in your password manager, and (for local scripts only) in gitignored `.env*` files.

## Architecture (free tiers + Azure for Students credit)

```
Browser ─▶ Vercel  (web/, Next.js)  ── server-side ──▶ Azure Container Apps (backend/, FastAPI, Docker)
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

## 3. Azure Container Apps: backend API

Hugging Face moved Docker Spaces to paid plans (mid-2026), so the backend runs on
Azure for Students ($100 credit, no card) using Container Apps' monthly free grant
(180K vCPU-s, 360K GiB-s, 2M requests). The app scales to zero when idle.

| Setting | Value |
|---|---|
| Subscription | Azure for Students. Allowed regions: `germanywestcentral`, `polandcentral`, `austriaeast`, `spaincentral`, `denmarkeast` |
| Resource group | `vio-rg` (`germanywestcentral`, Frankfurt) |
| Container Apps environment | `vio-env` (Consumption, no Log Analytics: log storage is billed per GB) |
| Container app | `vio-search-api`: 1 vCPU / 2 GiB, min 0 / max 1 replicas, ingress external on port 8000 |
| URL | https://vio-search-api.icyrock-a72fa589.germanywestcentral.azurecontainerapps.io |
| Image | `ghcr.io/anassoooo/fathom-api:<git sha>` (public GitHub package) |
| Deploy identity | Entra app `vio-github-deploy`, role **Contributor on `vio-rg` only**. Federated credential subject: `repo:anassoooo@186969238/fathom-search@1414515321:ref:refs/heads/main`. Repos created since 2026 present GitHub's **immutable-ID** subject format (owner and repo IDs included), so the plain `repo:owner/name:…` form doesn't match. |

**Container app secrets** (set from `backend/.env.cloud`, never from chat):
`qdrant-url`, `qdrant-api-key`, `llm-api-key`, exposed as `QDRANT_URL`,
`QDRANT_API_KEY`, `LLM_API_KEY` via `secretref:`.

**Environment variables:** `QDRANT_COLLECTION=vio_products_v2`,
`LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL_QUERY=openai/gpt-oss-20b`,
`LLM_REASONING_EFFORT=low`, `ONNX_DEVICE=cpu`, `ONNX_THREADS=1`,
`CORS_ORIGINS=["https://vio-web-coral.vercel.app"]`.

Rotate a secret:

```bash
az containerapp secret set -n vio-search-api -g vio-rg --secrets llm-api-key=<new value>
az containerapp revision restart -n vio-search-api -g vio-rg \
  --revision $(az containerapp show -n vio-search-api -g vio-rg --query properties.latestRevisionName -o tsv)
```

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
| Project name | `vio-web` → `https://vio-web-coral.vercel.app` (`vio-web.vercel.app` was taken) |
| Import | GitHub repo `anassoooo/fathom-search`, branch `main` |
| Root directory | `web` |
| Framework preset | Next.js |
| Build command | `npx prisma migrate deploy && next build` |

**Project → Settings → Environment Variables** (Production):

| Name | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** string |
| `DIRECT_URL` | Neon **direct** string |
| `BACKEND_URL` | `https://vio-search-api.icyrock-a72fa589.germanywestcentral.azurecontainerapps.io` |
| `AUTH_SECRET` | a new random value: `openssl rand -hex 32` (not the local one) |
| `ADMIN_EMAILS` | `admin@vio.test` (or your real email) |

## 6. GitHub: repository and CI

| Setting | Value |
|---|---|
| Repo | `anassoooo/fathom-search` (public) |
| Default branch | `main` |
| Actions secrets | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (identifiers for the OIDC login, not passwords) |
| Package access | `fathom-api` package → *Manage Actions access* → add this repo with **Write**, so the workflow's `GITHUB_TOKEN` can push images |

`.github/workflows/deploy-backend.yml`: on changes to `backend/` on `main`, it builds and
pushes the image, rolls `vio-search-api` to it, and smoke-tests `/health`.

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

## Naming conventions

| Thing | Name |
|---|---|
| Qdrant cluster / collection | `vio` (AWS `eu-central-1`) / `vio_products_v2` |
| Azure resource group / environment / app | `vio-rg` / `vio-env` / `vio-search-api` |
| Neon project / database / branch | `vio` / `neondb` / `production` |
| Vercel project | `vio-web` |
| Groq keys | laptop key (`backend/.env`), `vio-prod` (Azure, `backend/.env.cloud`) |
| Entra app (deploy identity) | `vio-github-deploy` |
| Local-only env files | `backend/.env`, `backend/.env.cloud`, `web/.env` (all gitignored) |
