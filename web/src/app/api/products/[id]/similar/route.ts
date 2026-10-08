import { NextRequest, NextResponse } from 'next/server'
import { searchSimilarProducts } from '@/lib/qdrant'
import { getSession } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import type { Product } from '@/lib/types'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const searchParams = request.nextUrl.searchParams
    const limit = Math.min(20, Math.max(1, parseInt(searchParams.get('limit') || '12')))
    const mode = (searchParams.get('mode') || 'text') as 'text' | 'image'

    const results = await searchSimilarProducts(id, mode, limit)

    // Log the recommendation event (server knows what it returned)
    try {
      const session = await getSession()
      await prisma.event.create({
        data: {
          userId: session?.userId || null,
          eventType: 'assistant_recommend',
          metadata: JSON.stringify({
            source: 'similar_products',
            seed_product_id: String(id),
            query_type: mode,
            list_type: 'similar',
            returned_product_ids: results.map((r) => String(r.id)),
            limit,
          }),
        },
      })
    } catch (e) {
      console.error('Failed to log assistant_recommend:', e)
    }

    const items: Product[] = results.map((result) => ({
      id: String(result.id),
      name: (result.payload.name as string) || 'Unknown Product',
      category: (result.payload.category as string) || 'Uncategorized',
      subcategory: (result.payload.subcategory as string) || (result.payload.subCategory as string),
      price: (result.payload.price as number) || 0,
      price_bucket: result.payload.price_bucket as string,
      rating: (result.payload.rating as number) || 0,
      total_ratings: result.payload.total_ratings as number,
      bayes_rating: result.payload.bayes_rating as number,
      value_score: result.payload.value_score as number,
      image_url: result.payload.image_url as string,
    }))

    return NextResponse.json({ items })
  } catch (error) {
    console.error('Error fetching similar products:', error)
    return NextResponse.json(
      { error: 'Failed to fetch similar products' },
      { status: 500 }
    )
  }
}
