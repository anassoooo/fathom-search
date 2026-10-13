'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import useSWR from 'swr'
import { ProductGrid } from './product-grid'
import { PaginationControls } from './pagination-controls'
import { Skeleton } from '@/components/ui/skeleton'
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
    <div ref={containerRef} className="space-y-8 scroll-mt-24">
      <div
        role="group"
        aria-label="Filter by category"
        className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0 lg:flex-wrap"
      >
        {categoriesData?.categories ? (
          ['all', ...categoriesData.categories].map((cat) => {
            const active = (category || 'all') === cat
            return (
              <button
                key={cat}
                type="button"
                aria-pressed={active}
                onClick={() => handleCategoryChange(cat)}
                className={
                  'shrink-0 rounded-full border px-3.5 py-1.5 text-sm transition-colors ' +
                  (active
                    ? 'border-ink bg-ink text-paper'
                    : 'border-rule bg-surface text-ink-soft hover:border-contour hover:text-ink')
                }
              >
                {cat === 'all' ? 'All categories' : cat}
              </button>
            )
          })
        ) : (
          Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-8 w-28 shrink-0 rounded-full" />)
        )}
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
