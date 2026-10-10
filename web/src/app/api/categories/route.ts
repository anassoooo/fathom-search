import { NextResponse } from 'next/server'

import { backendErrorResponse } from '@/lib/api-errors'
import { backend } from '@/lib/backend'

// The taxonomy changes only on re-ingest: cache it for 5 minutes.
let cache: { data: string[]; at: number } | null = null
const TTL_MS = 5 * 60 * 1000

export async function GET() {
  if (cache && Date.now() - cache.at < TTL_MS) {
    return NextResponse.json({ categories: cache.data })
  }
  try {
    const { categories } = await backend.taxonomy()
    cache = { data: categories, at: Date.now() }
    return NextResponse.json({ categories })
  } catch (error) {
    return backendErrorResponse(error, 'categories')
  }
}
