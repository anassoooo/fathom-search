import { NextResponse } from 'next/server'

import { backend } from '@/lib/backend'

export async function GET() {
  try {
    const h = await backend.health()
    return NextResponse.json({ ok: h.status === 'ok', backend: h })
  } catch {
    return NextResponse.json({ ok: false, backend: null }, { status: 503 })
  }
}
