import { NextRequest, NextResponse } from 'next/server'

import { backendErrorResponse } from '@/lib/api-errors'
import { getSession } from '@/lib/auth'
import { backend, toProduct } from '@/lib/backend'
import { prisma } from '@/lib/prisma'

// Similarity fuses the product's text and image vectors server-side, so the old
// `mode=text|image` parameter is accepted but no longer needed.
export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const limit = Math.min(20, Math.max(1, Number.parseInt(request.nextUrl.searchParams.get('limit') || '12', 10) || 12))
  try {
    const { results } = await backend.similar(id, limit)
    const items = results.map((hit) => toProduct(hit.product))

    try {
      const session = await getSession()
      await prisma.event.create({
        data: {
          userId: session?.userId ?? null,
          eventType: 'assistant_recommend',
          metadata: JSON.stringify({
            source: 'similar_products',
            seed_product_id: id,
            list_type: 'similar',
            returned_product_ids: items.map((p) => p.id),
            limit,
          }),
        },
      })
    } catch (e) {
      console.error('Failed to log similar-products event:', e)
    }

    return NextResponse.json({ items })
  } catch (error) {
    return backendErrorResponse(error, 'Similar products')
  }
}
