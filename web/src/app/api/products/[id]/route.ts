import { NextRequest, NextResponse } from 'next/server'
import { getProductById } from '@/lib/qdrant'
import type { Product } from '@/lib/types'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    const point = await getProductById(id)
    console.log(`[API] Fetch result for ${id}:`, point ? 'found' : 'not found')

    if (!point) {
      return NextResponse.json(
        { error: 'Product not found' },
        { status: 404 }
      )
    }

    const product: Product = {
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
    }

    return NextResponse.json(product)
  } catch (error) {
    console.error(`[API] Error fetching product ${id}:`, error)
    return NextResponse.json(
      { error: 'Failed to fetch product', details: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    )
  }
}
