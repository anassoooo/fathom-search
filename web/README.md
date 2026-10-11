# Fathom web app

Next.js 16 front end for [Fathom](../README.md): catalog, product pages, the AI
assistant (text and photo search), cart, accounts, and the metrics dashboard.

- All search goes through the Python backend: `src/app/api/*` route handlers are thin,
  typed proxies (`src/lib/backend.ts`, types generated from `backend/openapi.json` with
  `npm run gen:api`).
- Accounts, carts, and events live in Postgres via Prisma (`prisma/`); passwords use bcrypt,
  and sessions are 256-bit random tokens.
- Deployed on Vercel (`vercel.json` runs `prisma migrate deploy` before `next build`).

```bash
cp .env.example .env      # DATABASE_URL / DIRECT_URL / BACKEND_URL / AUTH_SECRET / ADMIN_EMAILS
npm ci
npx prisma migrate deploy
npm run dev               # http://localhost:3000
```
