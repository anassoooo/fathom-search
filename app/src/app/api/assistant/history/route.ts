import { NextResponse } from 'next/server'
import { getSession } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

export async function GET() {
  try {
    const session = await getSession()
    if (!session) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      )
    }

    const history = await prisma.assistantHistory.findMany({
      where: { userId: session.userId },
      orderBy: { createdAt: 'desc' },
      take: 20
    })

    const formattedHistory = history.map((item) => ({
      id: item.id,
      prompt: item.prompt,
      returnedProductIds: JSON.parse(item.returnedProductIds || '[]'),
      createdAt: item.createdAt,
    }))

    return NextResponse.json({ history: formattedHistory })
  } catch (error) {
    console.error('Error fetching assistant history:', error)
    return NextResponse.json(
      { error: 'Failed to fetch history' },
      { status: 500 }
    )
  }
}
