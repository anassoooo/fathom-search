'use client'

import { useState } from 'react'
import Image from 'next/image'
import { useRouter, usePathname } from 'next/navigation'
import { Star, ShoppingCart, Package } from 'lucide-react'
import useSWR from 'swr'
import { useAuth } from './auth-provider'
import { ProductCarousel } from './product-carousel'
import { Button } from '@/components/ui/button'
import { formatPrice } from './product-card'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from 'sonner'
import type { Product } from '@/lib/types'

const fetcher = (url: string) => fetch(url).then((res) => res.json())

interface ProductDetailProps {
  productId: string
}

export function ProductDetail({ productId }: ProductDetailProps) {
  const [imageError, setImageError] = useState(false)
  const [isAddingToCart, setIsAddingToCart] = useState(false)
  const { user } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  const { data: product, isLoading } = useSWR<Product>(
    `/api/products/${productId}`,
    fetcher
  )

  const mode = 'text' // Using text embeddings for similar products

  const { data: similarData, isLoading: isSimilarLoading } = useSWR<{ items: Product[] }>(
    `/api/products/${productId}/similar?limit=8&mode=${mode}`,
    fetcher
  )

  const handleAddToCart = async () => {
    if (!user) {
      const params = new URLSearchParams({
        next: pathname,
        action: 'add_to_cart',
        payload: productId,
      })
      router.push(`/login?${params.toString()}`)
      return
    }

    setIsAddingToCart(true)
    try {
      const res = await fetch('/api/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productId, quantity: 1 }),
      })

      if (!res.ok) {
        throw new Error('Failed to add to cart')
      }

      // Track event
      fetch('/api/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          eventType: 'add_to_cart',
          metadata: { productId, productName: product?.name },
        }),
      }).catch(() => { })

      toast.success('Added to cart', {
        description: `${product?.name} has been added to your cart.`,
      })
    } catch {
      toast.error('Failed to add to cart', {
        description: 'Please try again later.',
      })
    } finally {
      setIsAddingToCart(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="grid gap-8 md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <Skeleton className="aspect-square rounded-xl" />
          <div className="space-y-4">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-12 w-40" />
          </div>
        </div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-soft">This product is not in the catalog any more.</p>
        <Button variant="link" onClick={() => router.push('/#catalog')}>
          Browse the catalog
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-16">
      <div className="grid items-start gap-8 md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-14">
        <div className="relative aspect-square w-full overflow-hidden rounded-xl border border-rule bg-white">
          {!imageError && product.image_url ? (
            <Image
              src={product.image_url}
              alt={product.name}
              fill
              className="object-contain p-6"
              sizes="(max-width: 768px) 100vw, 45vw"
              priority
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-shoal/50">
              <Package className="size-16 text-ink-soft/40" aria-hidden />
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            <p className="text-sm text-ink-soft">
              {product.category}
              {product.subcategory && <span> / {product.subcategory}</span>}
            </p>
            <h1 className="text-[1.5rem] font-semibold leading-snug text-balance sm:text-[1.75rem]">{product.name}</h1>
          </div>

          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
            <span className="numerals text-[2rem] font-semibold">{formatPrice(product.price)}</span>
            {product.price_bucket && (
              <span className="rounded-md bg-shoal px-2 py-0.5 text-sm text-ink">{priceLabel(product.price_bucket)}</span>
            )}
          </div>

          {product.rating > 0 && (
            <div className="numerals flex flex-wrap items-center gap-2 text-sm">
              <span className="flex" aria-hidden>
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star
                    key={i}
                    className={`size-4 ${i < Math.round(product.rating) ? 'fill-ink text-ink' : 'text-rule'}`}
                  />
                ))}
              </span>
              <span className="font-medium">{product.rating.toFixed(1)} out of 5</span>
              {product.total_ratings ? (
                <span className="text-ink-soft">from {product.total_ratings.toLocaleString()} ratings</span>
              ) : null}
            </div>
          )}

          {product.bayes_rating ? (
            <p className="text-sm leading-relaxed text-ink-soft">
              Adjusted rating {product.bayes_rating.toFixed(2)}: the rating pulled toward its
              category&apos;s average when there are few ratings, so two five-star reviews count for
              less than two thousand.
            </p>
          ) : null}

          <div className="space-y-2 pt-2">
            <Button size="lg" className="w-full sm:w-auto sm:min-w-64" onClick={handleAddToCart} disabled={isAddingToCart}>
              <ShoppingCart className="size-4" />
              {isAddingToCart ? 'Adding to cart' : 'Add to cart'}
            </Button>
            {!user && <p className="text-sm text-ink-soft">You will be asked to sign in first.</p>}
          </div>
        </div>
      </div>

      <div>
        {isSimilarLoading ? (
          <div className="space-y-6">
            <h2 className="display text-[1.75rem]">Similar products</h2>
            <div className="flex gap-4 overflow-hidden">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex-[0_0_62%] space-y-3 sm:flex-[0_0_40%] md:flex-[0_0_28%] lg:flex-[0_0_20%]">
                  <Skeleton className="aspect-square w-full rounded-lg" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-5 w-1/3" />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <ProductCarousel
            title="Similar products"
            products={similarData?.items || []}
            analytics={{ list_type: 'similar', query_type: mode, seed_product_id: productId }}
          />
        )}
      </div>
    </div>
  )
}

function priceLabel(bucket: string) {
  const labels: Record<string, string> = { cheap: 'Budget', mid: 'Mid-range', premium: 'Premium' }
  return labels[bucket] ?? bucket.charAt(0).toUpperCase() + bucket.slice(1)
}
