'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { Star } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { Product } from '@/lib/types'

type AnalyticsContext = { list_type: string; query_type: string; seed_product_id?: string }

interface ProductCardProps {
  product: Product
  rank?: number
  analytics?: AnalyticsContext
}

export function ProductCard({ product, rank, analytics }: ProductCardProps) {
  const [imageError, setImageError] = useState(false)
  const [impressed, setImpressed] = useState(false)
  const linkRef = useRef<HTMLAnchorElement | null>(null)

  useEffect(() => {
    if (!linkRef.current || impressed) return

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
  }, [impressed, product.id, product.name, rank, analytics])

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

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price)
  }

  const renderRating = (rating: number) => {
    return (
      <div className="flex items-center gap-1">
        <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
        <span className="text-sm font-medium">{rating.toFixed(1)}</span>
        {product.total_ratings && (
          <span className="text-xs text-muted-foreground">
            ({product.total_ratings.toLocaleString()})
          </span>
        )}
      </div>
    )
  }

  return (
    <Link
      ref={linkRef}
      href={`/product/${product.id}`}
      onClick={handleClick}
      className="block group h-full"
    >
      <Card className="overflow-hidden border-border/10 group card-hover bg-background/50 backdrop-blur-sm h-full flex flex-col">
        <div className="aspect-square relative bg-muted">
          {!imageError && product.image_url ? (
            <Image
              src={product.image_url || "/placeholder.svg"}
              alt={product.name}
              fill
              className="object-cover transition-transform group-hover:scale-105"
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 25vw"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-muted">
              <svg
                className="w-16 h-16 text-muted-foreground/40"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </div>
          )}
          {product.value_score && product.value_score > 0.8 && (
            <Badge variant="premium" className="absolute top-2 left-2">
              Great Value
            </Badge>
          )}
        </div>
        <CardContent className="p-5">
          <div className="space-y-3">
            <p className="text-premium-label">
              {product.category}
            </p>
            <h3 className="text-premium-title line-clamp-2 group-hover:text-primary transition-colors min-h-[2.7rem]">
              {product.name}
            </h3>
            <div className="flex items-center justify-between pt-1">
              <span className="text-lg font-bold tracking-tight">{formatPrice(product.price)}</span>
              {product.rating > 0 && renderRating(product.rating)}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
