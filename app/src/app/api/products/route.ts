import { NextRequest, NextResponse } from 'next/server'
import { scrollProducts } from '@/lib/qdrant'
import type { Product } from '@/lib/types'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const page = Math.max(1, parseInt(searchParams.get('page') || '1'))
    const limit = Math.min(100, Math.max(1, parseInt(searchParams.get('limit') || '24')))
    const category = searchParams.get('category')

    // Build filter if category is specified
    let filter: Record<string, unknown> | undefined
    if (category) {
      filter = {
        must: [
          {
            key: 'category',
            match: { value: category },
          },
        ],
      }
    }

    const { points, nextOffset, totalFiltered } = await scrollProducts(limit, null, filter, page)

    const items: Product[] = points.map((point) => ({
      id: String(point.id),
      name: (point.payload.name as string) || 'Unknown Product',
      category: (point.payload.category as string) || 'Uncategorized',
      subcategory: (point.payload.subcategory as string) || (point.payload.subCategory as string),
      price: (point.payload.price as number) || 0,
      price_bucket: point.payload.price_bucket as string,
      rating: (point.payload.rating as number) || 0,
      total_ratings: point.payload.total_ratings as number,
      bayes_rating: point.payload.bayes_rating as number,
      value_score: point.payload.value_score as number,
      image_url: point.payload.image_url as string,
    }))

    const total = totalFiltered; // Declare total variable

    return NextResponse.json({
      items,
      page,
      limit,
      total,
      hasMore: !!nextOffset,
    })
  } catch (error) {
    console.error('Error fetching products:', error)
    return NextResponse.json(
      { error: 'Failed to fetch products' },
      { status: 500 }
    )
  }
}
