'use client'

import { useState } from 'react'
import Image from 'next/image'
import { useRouter, usePathname } from 'next/navigation'
import { Star, ShoppingCart, Package } from 'lucide-react'
import useSWR from 'swr'
import { useAuth } from './auth-provider'
import { ProductCarousel } from './product-carousel'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price)
  }

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Skeleton className="aspect-square rounded-lg" />
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
      <div className="text-center py-12">
        <p className="text-muted-foreground">Product not found</p>
        <Button variant="link" onClick={() => router.push('/')}>
          Go back to products
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-24 pt-4">
      {/* Product Details Section - Smaller and Left Aligned */}
      <div className="max-w-4xl">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Image - Smaller Footprint */}
          <div className="aspect-square relative bg-muted rounded-2xl overflow-hidden shadow-xl border border-border/20 max-w-sm w-full">
            {!imageError && product.image_url ? (
              <Image
                src={product.image_url || "/placeholder.svg"}
                alt={product.name}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 50vw"
                priority
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <Package className="w-24 h-24 text-muted-foreground/40" />
              </div>
            )}
            {product.value_score && product.value_score > 0.8 && (
              <Badge variant="premium" className="absolute top-4 left-4 scale-110">
                Great Value
              </Badge>
            )}
          </div>

          {/* Info */}
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-premium-label">
                {product.category}
                {product.subcategory && ` / ${product.subcategory}`}
              </p>
              <h1 className="text-2xl font-bold tracking-tight text-balance leading-tight">{product.name}</h1>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-3xl font-bold">{formatPrice(product.price)}</span>
              {product.price_bucket && (
                <Badge variant="secondary">{product.price_bucket}</Badge>
              )}
            </div>

            {product.rating > 0 && (
              <div className="flex items-center gap-2">
                <div className="flex items-center">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star
                      key={i}
                      className={`w-5 h-5 ${i < Math.round(product.rating)
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-muted-foreground/30'
                        }`}
                    />
                  ))}
                </div>
                <span className="font-medium">{product.rating.toFixed(1)}</span>
                {product.total_ratings && (
                  <span className="text-muted-foreground">
                    ({product.total_ratings.toLocaleString()} reviews)
                  </span>
                )}
              </div>
            )}

            {product.bayes_rating && (
              <p className="text-sm text-muted-foreground">
                Bayesian Rating: {product.bayes_rating.toFixed(2)}
              </p>
            )}

            <Button
              size="lg"
              variant="glow"
              className="w-full sm:w-80 rounded-2xl h-14 text-md font-semibold transition-all hover:scale-[1.02]"
              onClick={handleAddToCart}
              disabled={isAddingToCart}
            >
              <ShoppingCart className="mr-2 h-5 w-5" />
              {isAddingToCart ? 'Adding to Cart...' : 'Add to Cart'}
            </Button>

            {!user && (
              <p className="text-sm text-muted-foreground">
                Please sign in to add items to your cart.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Similar Products - Horizontal Carousel */}
      <div className="space-y-4">
        {isSimilarLoading ? (
          <div className="space-y-8">
            <h2 className="text-2xl font-bold tracking-[0.05em] uppercase text-muted-foreground/60 px-1">Similar Products</h2>
            <div className="flex gap-4 overflow-hidden mask-fade-right">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex-[0_0_85%] sm:flex-[0_0_45%] md:flex-[0_0_33.333%] lg:flex-[0_0_25%] space-y-3">
                  <Skeleton className="aspect-square w-full rounded-lg" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-6 w-1/3" />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <ProductCarousel
            title="Similar Products"
            products={similarData?.items || []}
            analytics={{ list_type: 'similar', query_type: mode, seed_product_id: productId }}
          />
        )}
      </div>
    </div>
  )
}
