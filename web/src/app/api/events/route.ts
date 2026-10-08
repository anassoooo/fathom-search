import { NextRequest, NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function POST(request: NextRequest) {
  try {
    const session = await getSession()
    const { eventType, metadata } = await request.json()

    const validEventTypes = [
      'product_impression',
      'product_click',
      'add_to_cart',
      'assistant_open',
      'assistant_recommend',
    ] as const

    if (!eventType || !validEventTypes.includes(eventType)) {
      return NextResponse.json({ error: 'Invalid event type' }, { status: 400 })
    }

    const meta: any = metadata ?? {}

    // Normalize common key variants
    if (meta.productId && !meta.product_id) meta.product_id = meta.productId
    if (meta.productName && !meta.product_name) meta.product_name = meta.productName

    meta.list_type ??= 'unknown'
    meta.query_type ??= 'unknown'

    // Require product_id for product-level events
    const productEvents = new Set(['product_impression', 'product_click', 'add_to_cart'])
    if (productEvents.has(eventType) && !meta.product_id) {
      return NextResponse.json({ error: 'metadata.product_id required' }, { status: 400 })
    }

    await prisma.event.create({
      data: {
        userId: session?.userId || null,
        eventType,
        metadata: JSON.stringify(meta),
      },
    })

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error logging event:', error)
    return NextResponse.json({ success: true })
  }
}
