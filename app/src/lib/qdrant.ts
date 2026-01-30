const QDRANT_URL = process.env.QDRANT_URL!
const QDRANT_API_KEY = process.env.QDRANT_API_KEY!
const COLLECTION_NAME = process.env.QDRANT_COLLECTION || 'vio_products'

interface QdrantPoint {
  id: string | number
  payload: ProductPayload
  vector?: Record<string, number[]>
}

export interface ProductPayload {
  name: string
  category: string
  subcategory?: string
  price: number
  price_bucket?: string
  rating: number
  total_ratings?: number
  bayes_rating?: number
  value_score?: number
  image_url?: string
  [key: string]: unknown
}

interface ScrollResponse {
  result: {
    points: QdrantPoint[]
    next_page_offset: string | number | null
  }
}

interface SearchResponse {
  result: Array<{
    id: string | number
    score: number
    payload: ProductPayload
    vector?: Record<string, number[]>
  }>
}

interface PointResponse {
  result: QdrantPoint
}

interface CountResponse {
  result: {
    count: number
  }
}

async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// Helper to apply Qdrant-style filters to a list of points (client-side)
export function applyFilters(points: QdrantPoint[], filter?: Record<string, unknown>): QdrantPoint[] {
  if (!filter) return points

  // Unwrap nested filter if Ollama returned it like { filter: { must: [...] } }
  let actualFilter = filter
  if (!('must' in filter) && 'filter' in filter && typeof filter.filter === 'object' && filter.filter !== null) {
    actualFilter = filter.filter as Record<string, unknown>
  }

  if (!('must' in actualFilter) || !Array.isArray(actualFilter.must)) {
    return points
  }

  let filtered = [...points]
  for (const condition of actualFilter.must) {
    if (!condition || typeof condition !== 'object' || !('key' in condition)) continue

    const key = condition.key as keyof ProductPayload

    // Handle Match (Case-insensitive for strings)
    if ('match' in condition) {
      const matchValue = (condition.match as { value: unknown }).value
      filtered = filtered.filter((p) => {
        const val = p.payload[key]
        if (typeof val === 'string' && typeof matchValue === 'string') {
          return val.toLowerCase() === matchValue.toLowerCase()
        }
        return val === matchValue
      })
    }

    // Handle Range
    if ('range' in condition) {
      const range = condition.range as { gt?: number; gte?: number; lt?: number; lte?: number }
      filtered = filtered.filter((p) => {
        const val = p.payload[key] as number
        if (typeof val !== 'number') return false
        if (range.gt !== undefined && !(val > range.gt)) return false
        if (range.gte !== undefined && !(val >= range.gte)) return false
        if (range.lt !== undefined && !(val < range.lt)) return false
        if (range.lte !== undefined && !(val <= range.lte)) return false
        return true
      })
    }
  }
  return filtered
}

async function qdrantFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  retries: number = 3
): Promise<T> {
  if (!QDRANT_URL) {
    throw new Error('QDRANT_URL environment variable is not set')
  }
  if (!QDRANT_API_KEY) {
    throw new Error('QDRANT_API_KEY environment variable is not set')
  }

  const url = `${QDRANT_URL}${endpoint}`

  for (let attempt = 0; attempt < retries; attempt++) {
    console.log(`[Qdrant] Request: ${options.method || 'GET'} ${url}`)
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'api-key': QDRANT_API_KEY,
        ...options.headers,
      },
    })

    console.log(`[Qdrant] Response: ${response.status} ${response.statusText}`)
    if (response.ok) {
      const data = await response.json()
      return data
    }

    // Handle rate limiting with exponential backoff
    if (response.status === 429 && attempt < retries - 1) {
      const waitTime = Math.pow(2, attempt + 1) * 1000 // 2s, 4s, 8s
      console.log(`[v0] Rate limited, waiting ${waitTime}ms before retry...`)
      await sleep(waitTime)
      continue
    }

    const error = await response.text()
    throw new Error(`Qdrant API error: ${response.status} - ${error}`)
  }

  throw new Error('Qdrant API: Max retries exceeded')
}

export async function getProductsCount(): Promise<number> {
  const data = await qdrantFetch<CountResponse>(
    `/collections/${COLLECTION_NAME}/points/count`,
    {
      method: 'POST',
      body: JSON.stringify({ exact: true }),
    }
  )
  return data.result.count
}

// Cache for all products with client-side filtering
let allProductsCache: QdrantPoint[] | null = null
let cacheTimestamp: number = 0
const CACHE_TTL = 60 * 60 * 1000 // 1 hour - longer cache to avoid rate limiting

async function getAllProducts(): Promise<QdrantPoint[]> {
  // Return cached data if valid
  if (allProductsCache && Date.now() - cacheTimestamp < CACHE_TTL) {
    return allProductsCache
  }

  // If we have stale cache and hit rate limits, return stale cache instead of empty
  const hasStaleCache = allProductsCache && allProductsCache.length > 0

  // Fetch all products from Qdrant
  const allPoints: QdrantPoint[] = []
  let currentOffset: string | number | null = null
  const maxIterations = 100 // Safety limit

  for (let i = 0; i < maxIterations; i++) {
    const body: Record<string, unknown> = {
      limit: 1000,
      with_payload: true,
      with_vector: false,
    }

    if (currentOffset) {
      body.offset = currentOffset
    }

    try {
      const data = await qdrantFetch<ScrollResponse>(
        `/collections/${COLLECTION_NAME}/points/scroll`,
        {
          method: 'POST',
          body: JSON.stringify(body),
        }
      )

      if (!data?.result?.points) {
        console.error('[v0] Unexpected Qdrant response:', JSON.stringify(data))
        // Return stale cache if available
        if (hasStaleCache) {
          console.log('[v0] Returning stale cache due to unexpected response')
          return allProductsCache!
        }
        break
      }

      allPoints.push(...data.result.points)
      currentOffset = data.result.next_page_offset

      if (!currentOffset) break
    } catch (error) {
      console.error('[v0] Error fetching products from Qdrant:', error)
      // Return stale cache if available on error (including rate limits)
      if (hasStaleCache) {
        console.log('[v0] Returning stale cache due to error')
        return allProductsCache!
      }
      break
    }
  }

  // Only cache if we got results
  if (allPoints.length > 0) {
    allProductsCache = allPoints
    cacheTimestamp = Date.now()
  }

  return allPoints
}

export async function scrollProducts(
  limit: number = 24,
  offset?: string | number | null,
  filter?: Record<string, unknown>,
  page: number = 1
): Promise<{ points: QdrantPoint[]; nextOffset: string | number | null; totalFiltered: number }> {
  // Apply client-side filtering if needed
  let allPoints = await getAllProducts()
  allPoints = applyFilters(allPoints, filter)

  const totalFiltered = allPoints.length

  // Calculate pagination
  const startIndex = (page - 1) * limit
  const endIndex = startIndex + limit
  const paginatedPoints = allPoints.slice(startIndex, endIndex)
  const hasMore = endIndex < totalFiltered

  return {
    points: paginatedPoints,
    nextOffset: hasMore ? String(page + 1) : null,
    totalFiltered,
  }
}

export async function getProductById(
  pointId: string | number
): Promise<QdrantPoint | null> {
  // First try to fetch directly by Qdrant point ID
  try {
    const data = await qdrantFetch<PointResponse>(
      `/collections/${COLLECTION_NAME}/points/${pointId}`
    )
    return data.result
  } catch {
    // If direct fetch fails, search in cached products by product_id payload field
    try {
      const allProducts = await getAllProducts()
      const product = allProducts.find(
        (p) => String(p.id) === String(pointId) || p.payload.product_id === String(pointId)
      )
      return product || null
    } catch {
      return null
    }
  }
}

export async function getProductWithVectors(
  pointId: string | number
): Promise<QdrantPoint | null> {
  try {
    const data = await qdrantFetch<{ result: QdrantPoint[] }>(
      `/collections/${COLLECTION_NAME}/points`,
      {
        method: 'POST',
        body: JSON.stringify({
          ids: [pointId],
          with_payload: true,
          with_vector: true,
        }),
      }
    )
    return data.result[0] || null
  } catch (error) {
    console.error('[Qdrant] getProductWithVectors failed:', error)
    return null
  }
}

export async function searchSimilarProducts(
  pointId: string | number,
  vectorName: 'text' | 'image' = 'text',
  limit: number = 12
): Promise<Array<{ id: string | number; score: number; payload: ProductPayload }>> {
  // First get the vector of the source product
  const sourceProduct = await getProductWithVectors(pointId)
  if (!sourceProduct?.vector?.[vectorName]) {
    return []
  }

  const vector = sourceProduct.vector[vectorName]

  const data = await qdrantFetch<SearchResponse>(
    `/collections/${COLLECTION_NAME}/points/search`,
    {
      method: 'POST',
      body: JSON.stringify({
        vector: {
          name: vectorName,
          vector,
        },
        limit: limit + 1, // +1 to exclude self
        with_payload: true,
        filter: {
          must_not: [
            {
              has_id: [pointId],
            },
          ],
        },
      }),
    }
  )

  return data.result.slice(0, limit)
}

export async function getTaxonomy() {
  const [categories, subcategories, priceBuckets] = await Promise.all([
    getCategories(),
    getSubcategories(),
    getPriceBuckets()
  ])
  return { categories, subcategories, priceBuckets }
}

export async function searchByVector(
  vector: number[],
  vectorName: 'text' | 'image' = 'text',
  limit: number = 12,
  filter?: Record<string, unknown>
): Promise<Array<{ id: string | number; score: number; payload: ProductPayload }>> {
  const body: Record<string, unknown> = {
    vector: {
      name: vectorName,
      vector,
    },
    limit,
    with_payload: true,
  }

  if (filter) {
    // Unwrap nested filter if Ollama returned it like { filter: { must: [...] } }
    let actualFilter = filter
    if (!('must' in filter) && !('should' in filter) && 'filter' in filter && typeof filter.filter === 'object' && filter.filter !== null) {
      actualFilter = filter.filter as Record<string, unknown>
    }
    body.filter = actualFilter
  }

  const data = await qdrantFetch<SearchResponse>(
    `/collections/${COLLECTION_NAME}/points/search`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    }
  )

  return data.result
}

export async function searchByText(
  textVector: number[],
  limit: number = 12,
  filter?: Record<string, unknown>
): Promise<Array<{ id: string | number; score: number; payload: ProductPayload }>> {
  return searchByVector(textVector, 'text', limit, filter)
}

export async function searchByImage(
  imageVector: number[],
  limit: number = 12,
  filter?: Record<string, unknown>
): Promise<Array<{ id: string | number; score: number; payload: ProductPayload }>> {
  return searchByVector(imageVector, 'image', limit, filter)
}

export async function blendedSearch(
  textVector: number[] | null,
  imageVector: number[] | null,
  limit: number = 12,
  textWeight: number = 0.6,
  filter?: Record<string, unknown>
): Promise<Array<{ id: string | number; score: number; payload: ProductPayload }>> {
  const results: Map<string, { id: string | number; score: number; payload: ProductPayload }> = new Map()

  if (textVector) {
    const textResults = await searchByText(textVector, limit, filter)
    textResults.forEach((r) => {
      const key = String(r.id)
      results.set(key, {
        ...r,
        score: r.score * textWeight,
      })
    })
  }

  if (imageVector) {
    const imageWeight = 1 - textWeight
    const imageResults = await searchByImage(imageVector, limit, filter)
    imageResults.forEach((r) => {
      const key = String(r.id)
      const existing = results.get(key)
      if (existing) {
        existing.score += r.score * imageWeight
      } else {
        results.set(key, {
          ...r,
          score: r.score * imageWeight,
        })
      }
    })
  }

  return Array.from(results.values())
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
}

// Keyword-based search for the assistant
export async function searchProductsByKeywords(
  query: string,
  limit: number = 12,
  filter?: Record<string, unknown>
): Promise<Array<{ id: string | number; score: number; payload: ProductPayload }>> {
  // Apply filter if provided
  let products = await getAllProducts()
  products = applyFilters(products, filter)

  if (products.length === 0) {
    return []
  }

  // Tokenize and normalize the query
  const queryLower = query.toLowerCase()

  // Check for "top k" or "best k" patterns
  const topKMatch = queryLower.match(/(?:top|best)\s+(\d+)\s+(.+)/i)
  if (topKMatch) {
    const requestedLimit = parseInt(topKMatch[1], 10)
    const searchTerms = topKMatch[2]
    return searchProductsByKeywords(searchTerms, requestedLimit, filter)
  }

  const queryTokens = queryLower.split(/\s+/).filter(t => t.length > 1)
  const queryPhrase = queryLower.trim()

  if (queryTokens.length === 0 && queryPhrase.length < 2) {
    return []
  }

  const scoredProducts = products.map(product => {
    const name = (product.payload.name || '').toLowerCase()
    const category = (product.payload.category || '').toLowerCase()
    const subcategory = (product.payload.subcategory || '').toLowerCase()

    let score = 0
    if (queryPhrase.length > 2) {
      if (name.includes(queryPhrase)) score += 10
      if (category.includes(queryPhrase)) score += 5
      if (subcategory.includes(queryPhrase)) score += 4
    }

    for (const token of queryTokens) {
      if (name.includes(token)) score += 3
      if (category.includes(token)) score += 2.5
      if (subcategory.includes(token)) score += 2
    }

    if (score > 0 && product.payload.rating) {
      score *= (1 + product.payload.rating / 10)
    }

    return { id: product.id, score, payload: product.payload }
  })

  return scoredProducts
    .filter(p => p.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
}

export async function getCategories(): Promise<string[]> {
  const allProducts = await getAllProducts()
  const categories = new Set<string>()
  allProducts.forEach((point) => {
    if (point.payload.category) {
      categories.add(point.payload.category)
    }
  })
  return Array.from(categories).sort()
}

export async function getSubcategories(): Promise<string[]> {
  const allProducts = await getAllProducts()
  const subcategories = new Set<string>()
  allProducts.forEach((point) => {
    if (point.payload.subcategory) {
      subcategories.add(point.payload.subcategory)
    }
  })
  return Array.from(subcategories).sort()
}

export async function getPriceBuckets(): Promise<string[]> {
  const allProducts = await getAllProducts()
  const buckets = new Set<string>()
  allProducts.forEach((point) => {
    if (point.payload.price_bucket) {
      buckets.add(point.payload.price_bucket)
    }
  })
  return Array.from(buckets).sort()
}
