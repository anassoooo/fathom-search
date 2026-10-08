import { NextRequest, NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { recommendBlended } from '@/lib/embeddings'
import { getTaxonomy } from '@/lib/qdrant'
import { processQuery } from '@/lib/ollama'
import type { Product } from '@/lib/types'

export async function POST(request: NextRequest) {
  try {
    const session = await getSession()
    if (!session) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      )
    }

    const { prompt, image } = await request.json()

    if (!prompt && !image) {
      return NextResponse.json(
        { error: 'Please provide a text prompt or image' },
        { status: 400 }
      )
    }

    let finalQuery = prompt || null
    let searchFilters = undefined
    let searchLimit = 12

    // Dynamic limit extraction (top/best K)
    if (prompt) {
      const topKMatch = prompt.toLowerCase().match(/(?:top|best|give me|show me)\s+(\d+)/i)
      if (topKMatch) {
        const requestedLimit = parseInt(topKMatch[1], 10)
        if (requestedLimit > 0 && requestedLimit <= 100) {
          searchLimit = requestedLimit
        }
      }
    }

    console.log('[API] New recommendation request:', { prompt, hasImage: !!image, searchLimit })

    // Semantic preprocessing if prompt exists
    if (prompt) {
      try {
        const taxonomy = await getTaxonomy()
        const aiResult = await processQuery(prompt, taxonomy)
        finalQuery = aiResult.semantic_expansion
        searchFilters = aiResult.filter
        console.log('[AI Search] Expanded:', finalQuery)
        console.log('[AI Search] Filters:', JSON.stringify(searchFilters, null, 2))
      } catch (e) {
        console.error('[AI Search] Preprocessing failed:', e)
      }
    }

    // Get recommendations from Qdrant with filters
    const results = await recommendBlended(
      finalQuery,
      image || null,
      searchLimit,
      searchFilters
    )

    console.log('[API] Qdrant results count:', results.length)

    // Transform results to products
    const products: Product[] = results.map((r) => ({
      id: String(r.id),
      name: r.payload.name || 'Unknown Product',
      category: r.payload.category || 'Uncategorized',
      subcategory: r.payload.subcategory,
      price: r.payload.price || 0,
      price_bucket: r.payload.price_bucket,
      rating: r.payload.rating || 0,
      total_ratings: r.payload.total_ratings,
      bayes_rating: r.payload.bayes_rating,
      value_score: r.payload.value_score,
      image_url: r.payload.image_url,
    }))

    const productIds = products.map((p) => p.id)

    // Save to recommendation_interactions
    try {
      await prisma.assistantHistory.create({
        data: {
          userId: session.userId,
          prompt: prompt || null,
          imageHash: image ? 'image_hash_placeholder' : null,
          returnedProductIds: JSON.stringify(productIds),
          // Store AI metadata in metadata field if available (future proofing)
        }
      })
    } catch (e) {
      console.error('Failed to log history', e)
    }

    // Log event
    try {
      await prisma.event.create({
        data: {
          userId: session.userId,
          eventType: 'assistant_recommend',
          metadata: JSON.stringify({
            hasPrompt: !!prompt,
            hasImage: !!image,
            resultsCount: products.length,
          })
        }
      })
    } catch (e) {
      console.error('Failed to log event', e)
    }

    return NextResponse.json({ products })
  } catch (error) {
    console.error('Error getting recommendations:', error)
    return NextResponse.json(
      { error: 'Failed to get recommendations' },
      { status: 500 }
    )
  }
}
