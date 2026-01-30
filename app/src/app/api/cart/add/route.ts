import { NextRequest, NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function POST(request: NextRequest) {
  try {
    const session = await getSession()
    if (!session) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      )
    }

    const { productId, quantity = 1 } = await request.json()

    if (!productId) {
      return NextResponse.json(
        { error: 'Product ID is required' },
        { status: 400 }
      )
    }

    // Upsert cart item using Prisma
    const cartItem = await prisma.cartItem.upsert({
      where: {
        userId_productId: {
          userId: session.userId,
          productId: String(productId)
        }
      },
      update: {
        quantity: { increment: quantity }
      },
      create: {
        userId: session.userId,
        productId: String(productId),
        quantity: quantity
      }
    })

    return NextResponse.json({ cartItem })
  } catch (error) {
    console.error('Error adding to cart:', error)
    return NextResponse.json(
      { error: 'Failed to add to cart' },
      { status: 500 }
    )
  }
}
