'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { Package, Star } from 'lucide-react'
import type { Product } from '@/lib/types'

type AnalyticsContext = { list_type: string; query_type: string; seed_product_id?: string }

interface ProductCardProps {
  product: Product
  rank?: number
  analytics?: AnalyticsContext
  /** Show the rank as a chart sounding (search results, where order is the point). */
  showRank?: boolean
  /** Lets a page open the product in place (e.g. a dialog) instead of navigating. */
  onSelect?: (e: React.MouseEvent<HTMLAnchorElement>) => void
  /** Set false when the page logs its own impressions and clicks (the search page does). */
  track?: boolean
}

export function ProductCard({ product, rank, analytics, showRank, onSelect, track = true }: ProductCardProps) {
  const [imageError, setImageError] = useState(false)
  const [impressed, setImpressed] = useState(false)
  const linkRef = useRef<HTMLAnchorElement | null>(null)

  useEffect(() => {
    if (!track || !linkRef.current || impressed) return

    const el = linkRef.current
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !impressed) {
          setImpressed(true)
          fetch('/api/events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              eventType: 'product_impression',
              metadata: {
                product_id: product.id,
                product_name: product.name,
                rank,
                list_type: analytics?.list_type,
                query_type: analytics?.query_type,
                seed_product_id: analytics?.seed_product_id,
              },
            }),
          }).catch(() => { })
        }
      },
      { threshold: 0.25 }
    )

    obs.observe(el)
    return () => obs.disconnect()
  }, [track, impressed, product.id, product.name, rank, analytics])

  const handleClick = () => {
    fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eventType: 'product_click',
        metadata: {
          product_id: product.id,
          product_name: product.name,
          rank,
          list_type: analytics?.list_type,
          query_type: analytics?.query_type,
          seed_product_id: analytics?.seed_product_id,
        },
      }),
    }).catch(() => { })
  }

  return (
    <Link
      ref={linkRef}
      href={`/product/${product.id}`}
      onClick={(e) => {
        if (track) handleClick()
        onSelect?.(e)
      }}
      className="group block h-full rounded-lg"
    >
      <article className="flex h-full flex-col">
        <div className="relative aspect-square overflow-hidden rounded-lg border border-rule bg-white">
          {!imageError && product.image_url ? (
            <Image
              src={product.image_url}
              alt={product.name}
              fill
              className="object-contain p-3 transition-transform duration-500 group-hover:scale-[1.03]"
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-shoal/50">
              <Package className="size-10 text-ink-soft/40" aria-hidden />
            </div>
          )}
          {rank !== undefined && showRank && (
            <span
              className="absolute left-2 top-1.5 font-serif text-lg italic text-contour"
              aria-label={`Rank ${rank}`}
            >
              {rank}
            </span>
          )}
        </div>
        <div className="flex flex-1 flex-col gap-1 pt-3">
          <h3 className="line-clamp-2 text-[0.9375rem] font-medium leading-snug text-ink group-hover:underline group-hover:decoration-rule group-hover:underline-offset-4">
            {product.name}
          </h3>
          <p className="text-[0.8125rem] text-ink-soft">{product.category}</p>
          <div className="mt-auto flex items-baseline justify-between gap-2 pt-1.5">
            <span className="numerals text-base font-semibold">{formatPrice(product.price)}</span>
            {product.rating > 0 && (
              <span className="numerals flex items-center gap-1 text-[0.8125rem] text-ink-soft">
                <Star className="size-3.5 fill-ink-soft/70 text-ink-soft/70" aria-hidden />
                {product.rating.toFixed(1)}
                {product.total_ratings ? (
                  <span className="sr-only sm:not-sr-only">({compact(product.total_ratings)})</span>
                ) : null}
              </span>
            )}
          </div>
        </div>
      </article>
    </Link>
  )
}

export function formatPrice(price: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price)
}

function compact(n: number) {
  return new Intl.NumberFormat('en-US', { notation: 'compact' }).format(n)
}
