import 'server-only'

import type { components } from '@/lib/api-types'
import type { Product } from '@/lib/types'

// Server-side client for the Python search backend (ADR-0001). Route handlers under
// /api/* proxy through here, so the browser never needs the backend URL or CORS.

type BackendProduct = components['schemas']['Product']
export type SearchRequest = components['schemas']['SearchRequest']
export type SearchResponse = components['schemas']['SearchResponse']
export type Filters = components['schemas']['Filters']
export type Taxonomy = components['schemas']['TaxonomyOut']

const BASE_URL = (process.env.BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export class BackendError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    cache: 'no-store',
  })
  if (!res.ok) {
    let message = `backend ${res.status}`
    try {
      const body = (await res.json()) as { error?: string }
      if (body.error) message = body.error
    } catch {
      // non-JSON error body: keep the status message
    }
    throw new BackendError(message, res.status)
  }
  return (await res.json()) as T
}

/** Map the backend's product to the shape the UI components already use. */
export function toProduct(p: BackendProduct): Product {
  return {
    id: p.product_id,
    name: p.name,
    category: p.category,
    subcategory: p.subcategory ?? undefined,
    price: p.price ?? 0,
    price_bucket: p.price_bucket ?? undefined,
    rating: p.rating ?? 0,
    total_ratings: p.total_ratings ?? undefined,
    bayes_rating: p.bayes_rating ?? undefined,
    value_score: p.value_score ?? undefined,
    image_url: p.image_url ?? undefined,
  }
}

function query(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const backend = {
  health: () => call<components['schemas']['HealthOut']>('/health'),
  taxonomy: () => call<Taxonomy>('/v1/taxonomy'),
  search: (body: SearchRequest) =>
    call<SearchResponse>('/v1/search', { method: 'POST', body: JSON.stringify(body) }),
  product: (id: string) => call<BackendProduct>(`/v1/products/${encodeURIComponent(id)}`),
  similar: (id: string, k: number) =>
    call<components['schemas']['SimilarOut']>(
      `/v1/products/${encodeURIComponent(id)}/similar${query({ k })}`,
    ),
  browse: (params: { category?: string | null; limit: number; cursor?: string | null }) =>
    call<components['schemas']['ProductPage']>(`/v1/products${query(params)}`),
}
