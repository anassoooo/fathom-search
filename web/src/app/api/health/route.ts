import { NextResponse } from 'next/server'

import { backend } from '@/lib/backend'
import { prisma } from '@/lib/prisma'

// Reports, without secrets, whether this deployment can reach its two dependencies:
// the search backend (configured host + network error) and the database (Prisma error
// code, e.g. P1000 bad credentials, P1001 unreachable, P2021 missing table).
function backendTarget(): { configured: boolean; host: string | null } {
  const raw = process.env.BACKEND_URL
  if (!raw) return { configured: false, host: null }
  try {
    return { configured: true, host: new URL(raw.trim()).host }
  } catch {
    return { configured: true, host: `invalid URL (${raw.length} chars)` }
  }
}

function databaseTarget(): { configured: boolean; host: string | null } {
  const raw = process.env.DATABASE_URL
  if (!raw) return { configured: false, host: null }
  try {
    return { configured: true, host: new URL(raw.trim()).hostname }
  } catch {
    return { configured: true, host: 'invalid URL' }
  }
}

async function checkDatabase() {
  try {
    const users = await prisma.user.count()
    return { ok: true, users }
  } catch (error) {
    const e = error as { code?: string; errorCode?: string; message?: string; name?: string }
    return { ok: false, error: e.code ?? e.errorCode ?? e.name ?? 'unknown' }
  }
}

async function checkBackend() {
  try {
    const h = await backend.health()
    return { ok: h.status === 'ok', ...h }
  } catch (error) {
    const cause = error instanceof Error && error.cause instanceof Error ? error.cause : null
    const detail =
      (cause as (Error & { code?: string }) | null)?.code ?? cause?.message ?? (error as Error)?.message
    return { ok: false, error: detail }
  }
}

export async function GET() {
  const [search, database] = await Promise.all([checkBackend(), checkDatabase()])
  const ok = search.ok && database.ok
  return NextResponse.json(
    {
      ok,
      backend: { target: backendTarget(), ...search },
      database: { target: databaseTarget(), ...database },
    },
    { status: ok ? 200 : 503 },
  )
}
