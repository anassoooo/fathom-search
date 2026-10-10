import { NextRequest, NextResponse } from 'next/server'

import { backendErrorResponse } from '@/lib/api-errors'
import { backend, toProduct } from '@/lib/backend'
import type { ProductsResponse } from '@/lib/types'

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams
  const page = Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1)
  const limit = Math.min(100, Math.max(1, Number.parseInt(params.get('limit') || '24', 10) || 24))
  try {
    const res = await backend.browse({ category: params.get('category'), limit, page })
    const body: ProductsResponse = {
      items: res.items.map(toProduct),
      page: res.page,
      limit: res.limit,
      total: res.total,
      hasMore: res.has_more,
    }
    return NextResponse.json(body)
  } catch (error) {
    return backendErrorResponse(error, 'products')
  }
}
