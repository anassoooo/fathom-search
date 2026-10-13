'use client'

import { ProductCard } from './product-card'
import { Skeleton } from '@/components/ui/skeleton'
import type { Product } from '@/lib/types'

interface ProductGridProps {
  products: Product[]
  isLoading?: boolean
  analytics?: { list_type: string; query_type: string; seed_product_id?: string }
}

export function ProductGrid({ products, isLoading, analytics }: ProductGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 lg:grid-cols-4 lg:gap-x-6">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="space-y-3">
            <Skeleton className="aspect-square w-full rounded-lg" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-5 w-1/3" />
          </div>
        ))}
      </div>
    )
  }

  if (products.length === 0) {
    return (
      <p className="py-16 text-center text-ink-soft">No products in this category yet. Pick another one above.</p>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3 lg:grid-cols-4 lg:gap-x-6">
      {products.map((product, idx) => (
        <ProductCard
          key={product.id}
          product={product}
          rank={idx + 1}
          analytics={analytics}
        />
      ))}
    </div>
  )
}
