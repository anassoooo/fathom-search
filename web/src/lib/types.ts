export interface Product {
  id: string
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
}

export interface ProductsResponse {
  items: Product[]
  page: number
  limit: number
  total?: number
  hasMore: boolean
}

export interface CartItem {
  id: string
  productId: string
  quantity: number
  product?: Product
}

export interface User {
  id: string
  email: string
  name: string | null
  createdAt: Date
}

export interface AssistantHistoryItem {
  id: string
  prompt: string | null
  imageHash: string | null
  returnedProductIds: string[]
  createdAt: Date
}

export interface EventData {
  eventType: 'product_impression' | 'product_click' | 'add_to_cart' | 'assistant_open' | 'assistant_recommend'
  metadata: Record<string, unknown>
}
