import { NextResponse } from 'next/server'

import { backend } from '@/lib/backend'

// Reports which backend host this deployment calls (not a secret) and, on failure, the
// network error, so a misconfigured BACKEND_URL is diagnosable from outside.
function backendTarget(): { configured: boolean; host: string | null } {
  const raw = process.env.BACKEND_URL
  if (!raw) return { configured: false, host: null }
  try {
    return { configured: true, host: new URL(raw.trim()).host }
  } catch {
    return { configured: true, host: `invalid URL (${raw.length} chars)` }
  }
}

export async function GET() {
  const target = backendTarget()
  try {
    const h = await backend.health()
    return NextResponse.json({ ok: h.status === 'ok', backend: h, target })
  } catch (error) {
    const cause = error instanceof Error && error.cause instanceof Error ? error.cause : null
    const detail =
      (cause as (Error & { code?: string }) | null)?.code ?? cause?.message ?? (error as Error)?.message
    return NextResponse.json({ ok: false, backend: null, target, error: detail }, { status: 503 })
  }
}
