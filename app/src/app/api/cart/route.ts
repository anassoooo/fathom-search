import { NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { getProductById } from '@/lib/qdrant'

export async function GET() {
  try {
    const session = await getSession()
    if (!session) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      )
    }

    const cartItems = await prisma.cartItem.findMany({
      where: { userId: session.userId },
      orderBy: { createdAt: 'desc' }
    })

    // Fetch product details from Qdrant
    const itemsWithProducts = await Promise.all(
      cartItems.map(async (item) => {
        const point = await getProductById(item.productId)
        return {
          id: item.id,
          productId: item.productId,
          quantity: item.quantity,
          product: point
            ? {
              id: String(point.id),
              product_id: point.payload.product_id || String(point.id),
              name: point.payload.name || 'Unknown Product',
              category: point.payload.category || 'Uncategorized',
              price: point.payload.price || 0,
              rating: point.payload.rating || 0,
              image_url: point.payload.image_url,
            }
            : null,
        }
      })
    )

    return NextResponse.json({ items: itemsWithProducts })
  } catch (error) {
    console.error('Error fetching cart:', error)
    return NextResponse.json(
      { error: 'Failed to fetch cart' },
      { status: 500 }
    )
  }
}
