'use client'

import React from "react"
import { QueryInsight, type QueryInsightData } from '@/components/query-insight'

import { useState, useEffect, useRef, useCallback, Suspense } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import useSWR from 'swr'
import { Header } from '@/components/header'
import { Send, ImageIcon, X, History, Star, Package, Sparkles, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { ProductDetail } from '@/components/product-detail'
import { cn } from "@/lib/utils"
import type { Product } from '@/lib/types'

interface HistoryItem {
  id: string
  prompt: string | null
  hasImage: boolean
  returnedProductIds: string[]
  createdAt: string
}

const fetcher = (url: string) => fetch(url).then((res) => res.json())

function AssistantContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const nextUrl = searchParams.get('next') || '/'

  const [prompt, setPrompt] = useState('')
  const [image, setImage] = useState<string | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [results, setResults] = useState<Product[]>([])
  const [insight, setInsight] = useState<QueryInsightData | null>(null)
  const [lastPrompt, setLastPrompt] = useState('')
  const [served, setServed] = useState<{ variant: string; traceId: string | null } | null>(null)

  // Online evaluation: every assistant impression/click carries the retrieval variant and
  // trace id that served it, so CTR can be compared per variant on /metrics (T054).
  const logEvent = (eventType: 'product_impression' | 'product_click', productId: string, rank: number, ctx = served) => {
    fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eventType,
        metadata: {
          product_id: productId,
          rank,
          list_type: 'assistant',
          query_type: image ? (prompt ? 'text+image' : 'image') : 'text',
          variant: ctx?.variant ?? 'unknown',
          trace_id: ctx?.traceId ?? null,
        },
      }),
    }).catch(() => {})
  }
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: historyData, mutate: mutateHistory } = useSWR<{ history: HistoryItem[] }>(
    '/api/assistant/history',
    fetcher
  )

  // Handle paste from clipboard
  const handlePaste = useCallback((e: ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return

    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) {
          const reader = new FileReader()
          reader.onload = (event) => {
            const base64 = event.target?.result as string
            setImage(base64.split(',')[1]) // Remove data:image/...;base64, prefix
            setImagePreview(base64)
          }
          reader.readAsDataURL(file)
        }
        break
      }
    }
  }, [])

  useEffect(() => {
    document.addEventListener('paste', handlePaste)

    // Restore state from sessionStorage
    const savedResults = sessionStorage.getItem('assistant_results')
    const savedPrompt = sessionStorage.getItem('assistant_prompt')
    const savedImage = sessionStorage.getItem('assistant_image')
    const savedImagePreview = sessionStorage.getItem('assistant_image_preview')

    // sessionStorage is client-only, so restoring must happen after mount. Rewritten in T055.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (savedResults) setResults(JSON.parse(savedResults))
    if (savedPrompt) setPrompt(savedPrompt)
    if (savedImage) setImage(savedImage)
    if (savedImagePreview) setImagePreview(savedImagePreview)

    return () => document.removeEventListener('paste', handlePaste)
  }, [handlePaste])

  // Sync state to sessionStorage
  useEffect(() => {
    if (results.length > 0) sessionStorage.setItem('assistant_results', JSON.stringify(results))
    else sessionStorage.removeItem('assistant_results')
  }, [results])

  useEffect(() => {
    if (prompt) sessionStorage.setItem('assistant_prompt', prompt)
    else sessionStorage.removeItem('assistant_prompt')
  }, [prompt])

  useEffect(() => {
    if (image) sessionStorage.setItem('assistant_image', image)
    else sessionStorage.removeItem('assistant_image')
  }, [image])

  useEffect(() => {
    if (imagePreview) sessionStorage.setItem('assistant_image_preview', imagePreview)
    else sessionStorage.removeItem('assistant_image_preview')
  }, [imagePreview])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (event) => {
        const base64 = event.target?.result as string
        setImage(base64.split(',')[1])
        setImagePreview(base64)
      }
      reader.readAsDataURL(file)
    }
  }

  const clearImage = () => {
    setImage(null)
    setImagePreview(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt && !image) return

    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/assistant/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt || undefined, image: image || undefined }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.error || 'Failed to get recommendations')
      }

      const data = await res.json()
      setResults(data.products)
      setInsight({
        understood: data.understood ?? null,
        boostedCategory: data.boostedCategory ?? null,
        appliedFilters: data.appliedFilters,
        degraded: data.degraded ?? [],
      })
      setLastPrompt(prompt)
      const ctx = { variant: data.variant ?? 'unknown', traceId: data.traceId ?? null }
      setServed(ctx)
      ;(data.products as Product[]).forEach((p, i) => logEvent('product_impression', p.id, i + 1, ctx))
      await mutateHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setIsLoading(false)
    }
  }

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(price)
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="flex flex-col min-h-screen selection:bg-accent/30">
      {/* Header */}
      <Header onHistoryClick={() => setShowHistory(true)}>
        <div className="flex items-center gap-2 group cursor-default">
          <h1 className="font-bold text-sm tracking-[0.15em] text-foreground/90 uppercase transition-all duration-300 group-hover:tracking-[0.2em] group-hover:text-accent">AI Assistant</h1>
          <Sparkles className="h-4 w-4 text-accent animate-pulse hover:scale-125 transition-transform duration-300" />
        </div>
      </Header>

      {/* Main Content Area */}
      <div className="flex-1 relative">
        {/* Search & Results View */}
        <div className="p-6 space-y-8 container-premium max-w-4xl mx-auto">
          {/* Expert Prompt Deck */}
          <div className="relative group animate-in fade-in slide-in-from-bottom-4 duration-700">
            <form onSubmit={handleSubmit} className="relative z-10 space-y-4">
              <div className="relative overflow-hidden rounded-2xl bg-background/30 backdrop-blur-3xl ring-1 ring-white/20 shadow-2xl shadow-accent/5 transition-all focus-within:ring-accent/40 focus-within:bg-background/50">
                <div className="p-1 flex items-center gap-2">
                  <Input
                    placeholder="Search for your style vision..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    disabled={isLoading}
                    className="flex-1 border-none bg-transparent shadow-none focus-visible:ring-0 text-md font-medium placeholder:text-muted-foreground/40 h-12 px-5"
                  />
                  <div className="flex items-center gap-1.5 pr-1.5">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isLoading}
                      className="h-11 w-11 rounded-xl hover:bg-white/10 transition-all text-muted-foreground hover:text-accent"
                    >
                      <ImageIcon className="h-5 w-5" />
                    </Button>
                    <Button
                      type="submit"
                      disabled={isLoading || (!prompt && !image)}
                      className="h-11 w-11 rounded-xl bg-accent text-accent-foreground hover:scale-105 active:scale-95 transition-all shadow-lg flex items-center justify-center"
                    >
                      {isLoading ? <Spinner className="h-5 w-5" /> : <Send className="h-5 w-5" />}
                    </Button>
                  </div>
                </div>

                {/* Image Preview Overlay */}
                {imagePreview && (
                  <div className="px-5 pb-4 animate-in zoom-in-95 duration-300">
                    <div className="relative inline-flex group/img">
                      <div className="absolute -inset-1 bg-accent/20 blur-md rounded-xl opacity-0 group-hover/img:opacity-100 transition-opacity" />
                      <Image
                        src={imagePreview || "/placeholder.svg"}
                        alt="Vibe reference"
                        width={80}
                        height={80}
                        className="relative rounded-xl object-cover ring-1 ring-white/30 shadow-xl"
                      />
                      <button
                        type="button"
                        onClick={clearImage}
                        className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-background/90 text-foreground flex items-center justify-center shadow-lg ring-1 ring-border/50 hover:bg-destructive hover:text-white transition-all scale-0 group-hover/img:scale-100"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </form>
          </div>

          {/* Error */}
          {error && (
            <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-lg">
              {error}
            </div>
          )}

          {/* Results Section */}
          {isLoading ? (
            <div className="grid grid-cols-2 gap-4 animate-pulse">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="rounded-2xl bg-muted/20 h-64 border border-border/10" />
              ))}
            </div>
          ) : results.length > 0 ? (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-8 duration-1000">
              {insight && <QueryInsight insight={insight} original={lastPrompt} />}
              <div className="flex items-center justify-between px-2">
                <h3 className="text-xs font-bold tracking-wider bg-accent/10 px-3 py-1 rounded-full text-accent uppercase">
                  Matches your vision ({results.length})
                </h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {results.map((product, idx) => (
                  <div key={product.id} className="animate-in fade-in zoom-in-95 duration-500" style={{ animationDelay: `${idx * 100}ms` }}>
                    <ProductMiniCard product={product} formatPrice={formatPrice} onClick={() => { logEvent('product_click', product.id, idx + 1); setSelectedProduct(product) }} />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center space-y-4 opacity-30">
              <Sparkles className="h-10 w-10 text-muted-foreground/40" />
              <p className="text-sm font-medium max-w-[200px] leading-relaxed">
                Your AI stylist is ready. Share a photo or a feeling.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Glassmorphism History Sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 right-0 w-80 z-50 transform transition-all duration-500 ease-in-out",
          "bg-background/20 backdrop-blur-3xl border-l border-white/10 ring-1 ring-white/10 shadow-2xl",
          showHistory ? "translate-x-0" : "translate-x-full"
        )}
      >
        <div className="flex flex-col h-full">
          <div className="flex items-center justify-between p-4 border-b border-white/5">
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-accent" />
              <h2 className="text-sm font-bold tracking-widest uppercase text-foreground/80">History</h2>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowHistory(false)}
              className="h-8 w-8 rounded-full hover:bg-white/10 transition-all"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          <ScrollArea className="flex-1">
            <div className="p-4 space-y-4">
              {historyData?.history?.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center opacity-40">
                  <Package className="h-8 w-8 mb-2" />
                  <p className="text-xs font-medium uppercase tracking-tighter">Empty archive</p>
                </div>
              ) : (
                historyData?.history?.map((item) => (
                  <Card key={item.id} className="group overflow-hidden bg-white/5 border-none ring-1 ring-white/5 hover:ring-accent/40 transition-all duration-300">
                    <div className="p-3 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs font-semibold line-clamp-2 leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">
                          {item.prompt || '(Visual Inquiry)'}
                        </p>
                        <span className="text-[10px] font-bold text-muted-foreground uppercase shrink-0 mt-0.5">
                          {formatDate(item.createdAt)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 pt-1">
                        {item.hasImage && (
                          <Badge variant="secondary" className="bg-accent/10 text-accent text-[9px] font-bold uppercase py-0 px-1.5 border-none">
                            Reference
                          </Badge>
                        )}
                        <span className="text-[10px] font-bold text-muted-foreground uppercase">
                          {item.returnedProductIds.length} Matches
                        </span>
                        <ChevronRight className="h-3 w-3 ml-auto text-muted-foreground opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
                      </div>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </ScrollArea>
        </div>
      </div>


      {/* Backdrop for Sidebar */}
      {showHistory && (
        <div
          className="fixed inset-0 bg-background/40 backdrop-blur-sm z-40 animate-in fade-in duration-300"
          onClick={() => setShowHistory(false)}
        />
      )}

      {/* Product Detail Modal */}
      <Dialog open={!!selectedProduct} onOpenChange={(open) => !open && setSelectedProduct(null)}>
        <DialogContent className="max-w-5xl h-[90vh] overflow-y-auto bg-background/80 backdrop-blur-2xl border-white/10 p-0 sm:rounded-3xl">
          <DialogTitle className="sr-only">Product Details</DialogTitle>
          <div className="p-6 md:p-10">
            {selectedProduct && <ProductDetail productId={selectedProduct.id} />}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ProductMiniCard({
  product,
  formatPrice,
  onClick,
}: {
  product: Product
  formatPrice: (price: number) => string
  onClick?: () => void
}) {
  const [imageError, setImageError] = useState(false)

  return (
    <div
      className="block group cursor-pointer"
      onClick={(e) => {
        if (onClick) {
          e.preventDefault()
          onClick()
        }
      }}
    >
      <Link href={`/product/${product.id}`} className="contents" onClick={(e) => onClick && e.preventDefault()}>
        <Card className="overflow-hidden bg-background/20 backdrop-blur-xl border-none ring-1 ring-white/5 shadow-lg group-hover:ring-accent/20 transition-all duration-300 rounded-2xl h-full flex flex-col">
          <div className="aspect-[4/5] relative bg-muted/30 overflow-hidden">
            {!imageError && product.image_url ? (
              <Image
                src={product.image_url || "/placeholder.svg"}
                alt={product.name}
                fill
                className="object-cover transition-transform duration-700 group-hover:scale-110"
                sizes="(max-width: 768px) 50vw, 33vw"
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <Package className="w-8 h-8 text-muted-foreground/20" />
              </div>
            )}
            <div className="absolute top-2 left-2">
              <Badge className="bg-background/80 backdrop-blur-md text-[0.65rem] font-bold px-2 py-0.5 border-none shadow-sm text-foreground">
                {product.category}
              </Badge>
            </div>
          </div>
          <CardContent className="p-3 flex-1 flex flex-col justify-between space-y-2">
            <p className="text-sm font-semibold line-clamp-2 leading-tight opacity-90 group-hover:opacity-100 transition-opacity">
              {product.name}
            </p>
            <div className="flex items-center justify-between pt-1">
              <span className="text-sm font-bold text-accent">{formatPrice(product.price)}</span>
              {product.rating > 0 && (
                <div className="flex items-center gap-1 opacity-60">
                  <Star className="h-2.5 w-2.5 fill-accent text-accent" />
                  <span className="text-xs font-medium">{product.rating.toFixed(1)}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </Link>
    </div>
  )
}

export default function AssistantPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen">
        <Spinner className="w-8 h-8" />
      </div>
    }>
      <AssistantContent />
    </Suspense>
  )
}
