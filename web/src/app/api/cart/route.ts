import { NextResponse } from 'next/server'

import { getSession } from '@/lib/auth'
import { BackendError, backend, toProduct } from '@/lib/backend'
import { prisma } from '@/lib/prisma'
import type { Product } from '@/lib/types'

async function productOrNull(id: string): Promise<Product | null> {
  try {
    return toProduct(await backend.product(id))
  } catch (error) {
    if (error instanceof BackendError && error.status === 404) return null // removed from catalog
    throw error
  }
}

export async function GET() {
  const session = await getSession()
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  try {
    const cartItems = await prisma.cartItem.findMany({
      where: { userId: session.userId },
      orderBy: { createdAt: 'desc' },
    })
    const items = await Promise.all(
      cartItems.map(async (item) => ({
        id: item.id,
        productId: item.productId,
        quantity: item.quantity,
        product: await productOrNull(item.productId),
      })),
    )
    return NextResponse.json({ items })
  } catch (error) {
    console.error('Error fetching cart:', error)
    return NextResponse.json({ error: 'Failed to fetch cart' }, { status: 500 })
  }
}
