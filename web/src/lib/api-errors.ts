import { NextResponse } from 'next/server'

import { BackendError } from '@/lib/backend'

/** Map a failed backend call to a response the UI can act on. */
export function backendErrorResponse(error: unknown, what: string): NextResponse {
  if (error instanceof BackendError) {
    if (error.status === 404) return NextResponse.json({ error: `${what} not found` }, { status: 404 })
    if (error.status === 400 || error.status === 422)
      return NextResponse.json({ error: error.message }, { status: 400 })
    if (error.status === 503)
      return NextResponse.json({ error: 'Search is temporarily unavailable' }, { status: 503 })
  }
  console.error(`[api] ${what} failed:`, error)
  const unreachable = error instanceof TypeError // fetch() could not reach the backend
  return NextResponse.json(
    { error: unreachable ? 'Search backend is unreachable' : `Failed to load ${what}` },
    { status: unreachable ? 503 : 502 },
  )
}
