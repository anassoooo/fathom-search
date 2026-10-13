'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import useSWR from 'swr'
import { Trash2, Minus, Plus, ShoppingBag, ArrowLeft, Package } from 'lucide-react'
import { useAuth } from '@/components/auth-provider'
import { Header } from '@/components/header'
import { SiteFooter } from '@/components/site-footer'
import { formatPrice } from '@/components/product-card'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { toast } from 'sonner'

interface CartItemData {
  id: string
  productId: string
  quantity: number
  product: {
    id: string
    product_id: string
    name: string
    category: string
    price: number
    rating: number
    image_url?: string
  } | null
}

const fetcher = (url: string) => fetch(url).then((res) => res.json())

function CartContent() {
  const { user, isLoading: isAuthLoading } = useAuth()
  const router = useRouter()
  const [updatingItems, setUpdatingItems] = useState<Set<string>>(new Set())

  const { data, isLoading, mutate } = useSWR<{ items: CartItemData[] }>(
    user ? '/api/cart' : null,
    fetcher
  )

  useEffect(() => {
    if (!isAuthLoading && !user) {
      router.push('/login?next=/cart')
    }
  }, [user, isAuthLoading, router])

  const updateQuantity = async (itemId: string, newQuantity: number) => {
    setUpdatingItems((prev) => new Set(prev).add(itemId))
    try {
      const res = await fetch(`/api/cart/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quantity: newQuantity }),
      })

      if (!res.ok) throw new Error('Failed to update')
      await mutate()
    } catch {
      toast.error('Could not change the quantity. Try again.')
    } finally {
      setUpdatingItems((prev) => {
        const next = new Set(prev)
        next.delete(itemId)
        return next
      })
    }
  }

  const removeItem = async (itemId: string) => {
    setUpdatingItems((prev) => new Set(prev).add(itemId))
    try {
      const res = await fetch(`/api/cart/${itemId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to remove')
      await mutate()
      toast.success('Removed from cart')
    } catch {
      toast.error('Could not remove the item. Try again.')
    } finally {
      setUpdatingItems((prev) => {
        const next = new Set(prev)
        next.delete(itemId)
        return next
      })
    }
  }

  const clearCart = async () => {
    try {
      const res = await fetch('/api/cart/clear', { method: 'POST' })
      if (!res.ok) throw new Error('Failed to clear')
      await mutate()
      toast.success('Cart emptied')
    } catch {
      toast.error('Could not empty the cart. Try again.')
    }
  }

  if (isAuthLoading || !user) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <div className="flex gap-4">
                <Skeleton className="w-24 h-24 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-5 w-3/4" />
                  <Skeleton className="h-4 w-1/4" />
                  <Skeleton className="h-8 w-32" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const items = data?.items || []
  const total = items.reduce(
    (sum, item) => sum + (item.product?.price || 0) * item.quantity,
    0
  )

  if (items.length === 0) {
    return (
      <div className="text-center py-12">
        <ShoppingBag className="mx-auto mb-4 size-12 text-ink-soft/50" aria-hidden />
        <h1 className="display mb-2 text-[2rem]">Your cart is empty</h1>
        <p className="mb-6 text-ink-soft">Products you add from a search or the catalog show up here.</p>
        <Button asChild>
          <Link href="/#catalog">
            <ArrowLeft className="size-4" />
            Browse the catalog
          </Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="display text-[2.25rem]">
          Cart <span className="numerals font-sans text-lg not-italic text-ink-soft">{items.length} {items.length === 1 ? 'item' : 'items'}</span>
        </h1>
        <Button variant="outline" size="sm" onClick={clearCart}>
          Empty cart
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Cart Items */}
        <div className="lg:col-span-2 space-y-4">
          {items.map((item) => (
            <Card key={item.id}>
              <CardContent className="p-4">
                <div className="flex gap-4">
                  {/* Image */}
                  <Link href={`/product/${item.productId}`} className="shrink-0">
                    <div className="relative size-24 overflow-hidden rounded-lg border border-rule bg-white">
                      {item.product?.image_url ? (
                        <Image
                          src={item.product.image_url || "/placeholder.svg"}
                          alt={item.product.name}
                          fill
                          className="object-contain p-1.5"
                          sizes="96px"
                        />
                      ) : (
                        <div className="absolute inset-0 flex items-center justify-center">
                          <Package className="w-8 h-8 text-muted-foreground/40" />
                        </div>
                      )}
                    </div>
                  </Link>

                  {/* Details */}
                  <div className="flex-1 min-w-0">
                    <Link
                      href={`/product/${item.productId}`}
                      className="font-medium hover:underline line-clamp-2"
                    >
                      {item.product?.name || 'Unknown Product'}
                    </Link>
                    <p className="text-sm text-muted-foreground">
                      {item.product?.category}
                    </p>
                    <p className="font-semibold mt-1">
                      {formatPrice(item.product?.price || 0)}
                    </p>
                  </div>

                  {/* Quantity Controls */}
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="icon"
                        className="h-8 w-8 bg-transparent"
                        onClick={() => updateQuantity(item.id, item.quantity - 1)}
                        disabled={item.quantity <= 1 || updatingItems.has(item.id)}
                      >
                        <Minus className="h-4 w-4" />
                      </Button>
                      <span className="w-8 text-center font-medium">
                        {updatingItems.has(item.id) ? (
                          <Spinner className="w-4 h-4 mx-auto" />
                        ) : (
                          item.quantity
                        )}
                      </span>
                      <Button
                        variant="outline"
                        size="icon"
                        className="h-8 w-8 bg-transparent"
                        onClick={() => updateQuantity(item.id, item.quantity + 1)}
                        disabled={updatingItems.has(item.id)}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => removeItem(item.id)}
                      disabled={updatingItems.has(item.id)}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Remove
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Order Summary */}
        <div className="lg:col-span-1">
          <Card>
            <CardContent className="p-6 space-y-4">
              <h2 className="font-serif text-xl italic">Summary</h2>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Subtotal</span>
                  <span>{formatPrice(total)}</span>
                </div>
                <div className="border-t pt-2 flex justify-between font-semibold">
                  <span>Total</span>
                  <span>{formatPrice(total)}</span>
                </div>
              </div>
              <Button className="w-full" size="lg" disabled>
                Checkout
              </Button>
              <p className="text-xs leading-relaxed text-ink-soft">
                Checkout is turned off: Fathom is a search demo, and nothing here is for sale.
              </p>
              <Button variant="outline" className="w-full" asChild>
                <Link href="/#catalog">Keep browsing</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default function CartPage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="shell flex-1 py-10">
        <CartContent />
      </main>
      <SiteFooter />
    </div>
  )
}
