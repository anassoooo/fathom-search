import { NextRequest, NextResponse } from 'next/server'

import { backendErrorResponse } from '@/lib/api-errors'
import { backend, toProduct } from '@/lib/backend'

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  try {
    return NextResponse.json(toProduct(await backend.product(id)))
  } catch (error) {
    return backendErrorResponse(error, 'Product')
  }
}
