import { getTextEmbedding, getImageEmbedding, getBlendedEmbeddings } from './clip'
import {
  searchByText,
  searchByImage,
  blendedSearch,
  searchProductsByKeywords
} from './qdrant'
import type { ProductPayload } from './qdrant'

export interface RecommendationResult {
  id: string | number
  score: number
  payload: ProductPayload
}

/**
 * Recommend products by text using CLIP text embedding + Qdrant vector search
 */
export async function recommendByText(
  text: string,
  limit: number = 12,
  filter?: Record<string, unknown>
): Promise<RecommendationResult[]> {
  try {
    const textVector = await getTextEmbedding(text)
    const results = await searchByText(textVector, limit, filter)

    if (results.length > 0) {
      return results
    }

    console.log('[embeddings] No vector results, falling back to keyword search')
    return searchProductsByKeywords(text, limit, filter)
  } catch (error) {
    console.error('[embeddings] CLIP text embedding failed:', error)
    return searchProductsByKeywords(text, limit, filter)
  }
}

/**
 * Recommend products by image using CLIP image embedding + Qdrant vector search
 */
export async function recommendByImage(
  imageBase64: string,
  limit: number = 12,
  filter?: Record<string, unknown>
): Promise<RecommendationResult[]> {
  try {
    const imageVector = await getImageEmbedding(imageBase64)
    return searchByImage(imageVector, limit, filter)
  } catch (error) {
    console.error('[embeddings] CLIP image embedding failed:', error)
    return []
  }
}

/**
 * Recommend products using blended text + image search
 */
export async function recommendBlended(
  text: string | null,
  imageBase64: string | null,
  limit: number = 12,
  filter?: Record<string, unknown>
): Promise<RecommendationResult[]> {
  const TEXT_WEIGHT = 0.6

  try {
    const { textVector, imageVector } = await getBlendedEmbeddings(text, imageBase64)

    if (textVector && imageVector) {
      const results = await blendedSearch(textVector, imageVector, limit, TEXT_WEIGHT, filter)
      if (results.length > 0) {
        return results
      }
    }

    if (textVector) {
      const results = await searchByText(textVector, limit, filter)
      if (results.length > 0) {
        return results
      }
    }

    if (imageVector) {
      const results = await searchByImage(imageVector, limit, filter)
      if (results.length > 0) {
        return results
      }
    }

    if (text) {
      console.log('[embeddings] No vector results, falling back to keyword search')
      const keywordResults = await searchProductsByKeywords(text, limit, filter)
      if (keywordResults.length > 0) {
        return keywordResults
      }

      // Final broad fallback: try without filters if we still have no results
      if (filter) {
        console.log('[embeddings] No results with filters, trying broad search...')
        return searchProductsByKeywords(text, limit)
      }
    }

    return []
  } catch (error) {
    console.error('[embeddings] Blended search failed:', error)
    if (text) {
      return searchProductsByKeywords(text, limit, filter)
    }
    return []
  }
}

// Hash function for image storage reference
export function hashImage(base64: string): string {
  let hash = 0
  for (let i = 0; i < base64.length; i++) {
    const char = base64.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  return Math.abs(hash).toString(16)
}
