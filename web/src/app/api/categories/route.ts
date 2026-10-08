import { NextResponse } from 'next/server'
import { getCategories } from '@/lib/qdrant'

// Cache categories for 5 minutes
let categoriesCache: { data: string[]; timestamp: number } | null = null
const CACHE_TTL = 5 * 60 * 1000

export async function GET() {
  try {
    // Check cache
    if (categoriesCache && Date.now() - categoriesCache.timestamp < CACHE_TTL) {
      return NextResponse.json({ categories: categoriesCache.data })
    }

    const categories = await getCategories()
    
    // Update cache only if we got results
    if (categories.length > 0) {
      categoriesCache = { data: categories, timestamp: Date.now() }
    }

    return NextResponse.json({ categories })
  } catch (error) {
    console.error('Error fetching categories:', error)
    return NextResponse.json(
      { error: 'Failed to fetch categories' },
      { status: 500 }
    )
  }
}
