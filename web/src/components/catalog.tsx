'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import useSWR from 'swr'
import { ProductGrid } from './product-grid'
import { PaginationControls } from './pagination-controls'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useSearchParams, useRouter, usePathname } from 'next/navigation'
import type { ProductsResponse } from '@/lib/types'

const fetcher = (url: string) => fetch(url).then((res) => res.json())

export function Catalog() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  const category = searchParams.get('category') || ''
  const [page, setPage] = useState(1)
  const [limit, setLimit] = useState(24)
  const [prevCategory, setPrevCategory] = useState(category)
  const containerRef = useRef<HTMLDivElement>(null)

  // Reset to page 1 whenever the URL category changes
  if (prevCategory !== category) {
    setPrevCategory(category)
    setPage(1)
  }

  const updateUrl = (newCategory: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (newCategory) {
      params.set('category', newCategory)
    } else {
      params.delete('category')
    }
    params.set('page', '1') // Reset page on category change
    router.push(`${pathname}?${params.toString()}`, { scroll: false })
  }

  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  })
  if (category) {
    params.set('category', category)
  }

  const { data, isLoading } = useSWR<ProductsResponse>(
    `/api/products?${params.toString()}`,
    fetcher
  )

  const { data: categoriesData } = useSWR<{ categories: string[] }>(
    '/api/categories',
    fetcher
  )

  // Track impressions when products load
  const trackImpressions = useCallback((products: ProductsResponse['items']) => {
    if (products.length === 0) return

    fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eventType: 'product_impression',
        metadata: {
          productIds: products.map((p) => p.id),
          page,
          category: category || 'all',
        },
      }),
    }).catch(() => { })
  }, [page, category])

  useEffect(() => {
    if (data?.items) {
      trackImpressions(data.items)
    }
  }, [data?.items, trackImpressions])

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    if (containerRef.current) {
      const headerHeight = 100 // Approximate header height for offset
      const elementPosition = containerRef.current.getBoundingClientRect().top + window.scrollY
      window.scrollTo({
        top: elementPosition - headerHeight,
        behavior: 'smooth'
      })
    }
  }

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit)
    setPage(1)
  }

  const handleCategoryChange = (newCategory: string) => {
    const value = newCategory === 'all' ? '' : newCategory
    setPage(1)
    updateUrl(value)
  }

  return (
    <div ref={containerRef} className="space-y-6 scroll-mt-24">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex items-center gap-3 p-1 rounded-2xl bg-muted/30 border border-border/40 w-fit">
          <span className="text-premium-label ml-3">Category:</span>
          {categoriesData?.categories ? (
            <Select value={category || 'all'} onValueChange={handleCategoryChange}>
              <SelectTrigger className="w-48 bg-background border-none shadow-sm h-8 rounded-xl font-medium">
                <SelectValue placeholder="All Categories" />
              </SelectTrigger>
              <SelectContent className="rounded-xl border-border/40">
                <SelectItem value="all">All Categories</SelectItem>
                {categoriesData.categories.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Skeleton className="h-8 w-48 rounded-xl" />
          )}
        </div>
      </div>

      {/* Product Grid */}
      <ProductGrid products={data?.items || []} isLoading={isLoading} />

      {/* Pagination */}
      {data && (
        <PaginationControls
          page={page}
          limit={limit}
          total={data.total}
          hasMore={data.hasMore}
          onPageChange={handlePageChange}
          onLimitChange={handleLimitChange}
        />
      )}
    </div>
  )
}
