import { createHash } from 'node:crypto'

import { NextRequest, NextResponse } from 'next/server'

import { backendErrorResponse } from '@/lib/api-errors'
import { getSession } from '@/lib/auth'
import { backend, toProduct } from '@/lib/backend'
import { prisma } from '@/lib/prisma'

const MAX_PROMPT = 500
// The relevance gate labels up to the reranked top-30 (ADR-0008). Without it (photo-only
// search, reranker down) the first UNGATED_SHOWN results are shown and the rest are related.
const GATED_K = 30
const UNGATED_SHOWN = 12
const NEAREST_SHOWN = 3

export async function POST(request: NextRequest) {
  const session = await getSession()
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  let body: { prompt?: unknown; image?: unknown }
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
  }
  const prompt = typeof body.prompt === 'string' ? body.prompt.trim().slice(0, MAX_PROMPT) : ''
  const image = typeof body.image === 'string' && body.image ? body.image : null
  if (!prompt && !image) {
    return NextResponse.json({ error: 'Please provide a text prompt or image' }, { status: 400 })
  }

  try {
    // `full` = LLM query understanding + hybrid retrieval + reranking (see PLAN.md §7.4).
    const res = await backend.search({
      query: prompt || null,
      image_b64: image,
      k: GATED_K,
      variant: 'full',
      gate: true,
    })
    const answer = res.answer ?? null
    const all = res.results.map((hit) => toProduct(hit.product))
    const shown =
      answer === 'matches'
        ? res.results.filter((hit) => hit.tier === 'match').length
        : answer === 'no_close_match'
          ? NEAREST_SHOWN
          : UNGATED_SHOWN
    const products = all.slice(0, shown)
    const related = all.slice(shown)
    const productIds = products.map((p) => p.id)

    // History and analytics must never break the response.
    await Promise.allSettled([
      prisma.assistantHistory.create({
        data: {
          userId: session.userId,
          prompt: prompt || null,
          imageHash: image ? createHash('sha256').update(image).digest('hex').slice(0, 16) : null,
          returnedProductIds: JSON.stringify(productIds),
        },
      }),
      prisma.event.create({
        data: {
          userId: session.userId,
          eventType: 'assistant_recommend',
          metadata: JSON.stringify({
            variant: res.variant,
            trace_id: res.trace_id,
            query_type: image ? (prompt ? 'text+image' : 'image') : 'text',
            list_type: 'assistant',
            returned_product_ids: productIds,
            related_count: related.length,
            answer,
            degraded: res.degraded,
          }),
        },
      }),
    ])

    return NextResponse.json({
      products,
      related,
      answer,
      variant: res.variant,
      traceId: res.trace_id,
      understood: res.parsed_query ?? null,
      boostedCategory: res.boosted_category ?? null,
      appliedFilters: res.applied_filters,
      degraded: res.degraded ?? [],
      timings: res.timings_ms ?? {},
    })
  } catch (error) {
    return backendErrorResponse(error, 'Recommendations')
  }
}
