'use client'

import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react'
import Image from 'next/image'
import { useRouter, useSearchParams } from 'next/navigation'
import useSWR from 'swr'
import { Camera, X, Search, ImageIcon } from 'lucide-react'
import { Header } from '@/components/header'
import { EXAMPLES } from '@/components/hero-search'
import { ProductCard } from '@/components/product-card'
import { ProductDetail } from '@/components/product-detail'
import { SoundingLine } from '@/components/sounding-line'
import type { QueryInsightData } from '@/components/query-insight'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import type { Product } from '@/lib/types'

interface HistoryItem {
  id: string
  prompt: string | null
  hasImage: boolean
  returnedProductIds: string[]
  createdAt: string
}

interface RunInfo {
  insight: QueryInsightData
  timings: Record<string, number>
  prompt: string
  hasImage: boolean
  runId: string
}

const fetcher = (url: string) => fetch(url).then((res) => res.json())

function readFile(file: File, done: (dataUrl: string) => void) {
  const reader = new FileReader()
  reader.onload = (event) => done(event.target?.result as string)
  reader.readAsDataURL(file)
}

function AssistantContent() {
  const [prompt, setPrompt] = useState('')
  const [image, setImage] = useState<string | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [results, setResults] = useState<Product[]>([])
  const [run, setRun] = useState<RunInfo | null>(null)
  const [served, setServed] = useState<{ variant: string; traceId: string | null } | null>(null)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [showHistory, setShowHistory] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const autoRan = useRef(false)
  const searchParams = useSearchParams()
  const router = useRouter()

  // Online evaluation: every assistant impression/click carries the retrieval variant and
  // trace id that served it, so CTR can be compared per variant on /metrics (T054).
  const logEvent = (
    eventType: 'product_impression' | 'product_click',
    productId: string,
    rank: number,
    ctx = served,
    queryType = run ? (run.hasImage ? (run.prompt ? 'text+image' : 'image') : 'text') : 'text',
  ) => {
    fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eventType,
        metadata: {
          product_id: productId,
          rank,
          list_type: 'assistant',
          query_type: queryType,
          variant: ctx?.variant ?? 'unknown',
          trace_id: ctx?.traceId ?? null,
        },
      }),
    }).catch(() => {})
  }

  const { data: historyData, mutate: mutateHistory } = useSWR<{ history: HistoryItem[] }>(
    '/api/assistant/history',
    fetcher,
  )

  const attach = useCallback((file: File) => {
    if (!file.type.startsWith('image/')) return
    readFile(file, (dataUrl) => {
      setImage(dataUrl.split(',')[1]) // strip the data:image/...;base64, prefix
      setImagePreview(dataUrl)
    })
  }, [])

  const handlePaste = useCallback(
    (e: ClipboardEvent) => {
      for (const item of e.clipboardData?.items ?? []) {
        if (item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) attach(file)
          break
        }
      }
    },
    [attach],
  )

  const runSearch = useCallback(
    async (text: string, img: string | null) => {
      if (!text && !img) return
      setIsLoading(true)
      setError(null)
      try {
        const res = await fetch('/api/assistant/recommend', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: text || undefined, image: img || undefined }),
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok) throw new Error(data.error || `Search failed (${res.status}). Try again in a moment.`)

        setResults(data.products)
        const info: RunInfo = {
          insight: {
            understood: data.understood ?? null,
            boostedCategory: data.boostedCategory ?? null,
            appliedFilters: data.appliedFilters,
            degraded: data.degraded ?? [],
          },
          timings: data.timings ?? {},
          prompt: text,
          hasImage: !!img,
          runId: data.traceId ?? String(Date.now()),
        }
        setRun(info)
        const ctx = { variant: data.variant ?? 'unknown', traceId: data.traceId ?? null }
        setServed(ctx)
        const queryType = img ? (text ? 'text+image' : 'image') : 'text'
        ;(data.products as Product[]).forEach((p, i) => logEvent('product_impression', p.id, i + 1, ctx, queryType))
        await mutateHistory()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Search failed. Try again in a moment.')
      } finally {
        setIsLoading(false)
      }
    },
    // logEvent only reads its arguments here; mutateHistory is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mutateHistory],
  )

  useEffect(() => {
    document.addEventListener('paste', handlePaste)

    // sessionStorage is client-only, so restoring must happen after mount.
    const savedResults = sessionStorage.getItem('assistant_results')
    const savedRun = sessionStorage.getItem('assistant_run')
    const savedPrompt = sessionStorage.getItem('assistant_prompt')
    const savedImage = sessionStorage.getItem('assistant_image')
    const savedImagePreview = sessionStorage.getItem('assistant_image_preview')
    /* eslint-disable react-hooks/set-state-in-effect */
    if (savedResults) setResults(JSON.parse(savedResults))
    if (savedRun) setRun(JSON.parse(savedRun))
    if (savedPrompt) setPrompt(savedPrompt)
    if (savedImage) setImage(savedImage)
    if (savedImagePreview) setImagePreview(savedImagePreview)

    // A query handed over from the home page runs straight away.
    const q = searchParams.get('q')?.trim()
    if (q && !autoRan.current) {
      autoRan.current = true
      setPrompt(q)
      setImage(null)
      setImagePreview(null)
      router.replace('/assistant', { scroll: false })
      void runSearch(q, null)
    }
    /* eslint-enable react-hooks/set-state-in-effect */

    return () => document.removeEventListener('paste', handlePaste)
  }, [handlePaste, runSearch, router, searchParams])

  // Keep the page as it was if the visitor opens a product and comes back.
  useEffect(() => {
    const persist = (key: string, value: string | null) => {
      if (value) sessionStorage.setItem(key, value)
      else sessionStorage.removeItem(key)
    }
    persist('assistant_results', results.length ? JSON.stringify(results) : null)
    persist('assistant_run', run ? JSON.stringify(run) : null)
    persist('assistant_prompt', prompt || null)
    persist('assistant_image', image)
    persist('assistant_image_preview', imagePreview)
  }, [results, run, prompt, image, imagePreview])

  const clearImage = () => {
    setImage(null)
    setImagePreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void runSearch(prompt.trim(), image)
  }

  const rerun = (text: string) => {
    setPrompt(text)
    clearImage()
    setShowHistory(false)
    void runSearch(text, null)
  }

  const formatDate = (dateStr: string) =>
    new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })

  const hasResults = results.length > 0

  return (
    <div className="flex min-h-screen flex-col">
      <Header onHistoryClick={() => setShowHistory(true)} />

      <main className="shell flex-1 py-8 sm:py-10">
        <h1 className="sr-only">Search</h1>

        <form
          role="search"
          onSubmit={handleSubmit}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            const file = e.dataTransfer.files?.[0]
            if (file) attach(file)
          }}
          className={cn(
            'rounded-xl border bg-surface transition-colors focus-within:border-contour',
            dragging ? 'border-dashed border-contour bg-shoal/40' : 'border-rule',
          )}
        >
          <div className="flex items-center gap-2 p-1.5 pl-4">
            <Search className="size-5 shrink-0 text-ink-soft" aria-hidden />
            <label htmlFor="q" className="sr-only">
              Describe what you are looking for
            </label>
            <input
              id="q"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isLoading}
              placeholder={image ? 'Add words to steer the photo search (optional)' : 'Describe what you need'}
              className="h-12 min-w-0 flex-1 bg-transparent text-[1.0625rem] outline-none placeholder:text-ink-soft/70"
              maxLength={500}
              autoComplete="off"
            />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) attach(file)
              }}
              className="hidden"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              aria-label="Add a photo"
            >
              <Camera className="size-5" />
            </Button>
            <Button type="submit" size="lg" disabled={isLoading || (!prompt.trim() && !image)}>
              {isLoading ? <Spinner className="size-4" /> : null}
              Search
            </Button>
          </div>

          {imagePreview && (
            <div className="flex items-center gap-3 border-t border-rule px-4 py-3">
              <div className="relative size-14 overflow-hidden rounded-md border border-rule bg-white">
                <Image src={imagePreview} alt="Your photo" fill className="object-cover" unoptimized />
              </div>
              <p className="flex-1 text-sm text-ink-soft">Searching by this photo.</p>
              <Button type="button" variant="ghost" size="sm" onClick={clearImage}>
                <X className="size-4" />
                Remove photo
              </Button>
            </div>
          )}
        </form>
        <p className="mt-2 text-xs text-ink-soft">
          Add a photo with the camera button, by dropping it on the search bar, or by pasting it.
        </p>

        {error && (
          <p role="alert" className="mt-6 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </p>
        )}

        {isLoading ? (
          <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="space-y-3">
                  <Skeleton className="aspect-square w-full rounded-lg" />
                  <Skeleton className="h-4 w-4/5" />
                  <Skeleton className="h-5 w-1/3" />
                </div>
              ))}
            </div>
            <Skeleton className="hidden h-80 rounded-xl lg:block" />
          </div>
        ) : hasResults && run ? (
          <div className="mt-10 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <section aria-labelledby="results-heading">
              <h2 id="results-heading" className="display text-[1.75rem] sm:text-[2rem]">
                {run.prompt ? `Results for “${run.prompt}”` : 'Results for your photo'}
              </h2>
              <a
                href="#sounding-heading"
                className="numerals mt-2 inline-block text-sm text-ink underline decoration-rule underline-offset-4 hover:decoration-contour lg:hidden"
              >
                How this search ran
                {run.timings.total_ms != null ? `, ${Math.round(run.timings.total_ms).toLocaleString()} ms` : ''}
              </a>
              <div className="mb-6" />
              <div className="grid grid-cols-2 gap-x-4 gap-y-8 md:grid-cols-3">
                {results.map((product, idx) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    rank={idx + 1}
                    showRank
                    track={false}
                    onSelect={(e) => {
                      e.preventDefault()
                      logEvent('product_click', product.id, idx + 1)
                      setSelectedProduct(product)
                    }}
                  />
                ))}
              </div>
            </section>
            <aside className="lg:sticky lg:top-24">
              <SoundingLine
                timings={run.timings}
                insight={run.insight}
                original={run.prompt}
                hasImage={run.hasImage}
                resultCount={results.length}
                runId={run.runId}
              />
            </aside>
          </div>
        ) : (
          <div className="mx-auto mt-16 max-w-xl text-center">
            <h2 className="display text-[2rem] sm:text-[2.5rem]">What are you looking for?</h2>
            <p className="mt-3 text-ink-soft">
              Write it the way you would say it, budget and all, or add a photo of something
              similar. Here are a few to start with:
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => rerun(ex)}
                  className="rounded-full border border-rule bg-surface px-3.5 py-1.5 text-sm text-ink transition-colors hover:border-contour"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Recent searches */}
      <div
        className={cn(
          'fixed inset-y-0 right-0 z-50 w-[min(22rem,100vw)] border-l border-rule bg-surface shadow-2xl transition-transform duration-300',
          showHistory ? 'translate-x-0' : 'translate-x-full',
        )}
        aria-hidden={!showHistory}
        inert={!showHistory}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-rule px-5 py-4">
            <h2 className="font-serif text-xl italic">Recent searches</h2>
            <Button variant="ghost" size="icon-sm" onClick={() => setShowHistory(false)} aria-label="Close recent searches">
              <X className="size-4" />
            </Button>
          </div>
          <ScrollArea className="flex-1">
            <ul className="divide-y divide-rule">
              {historyData?.history?.length === 0 && (
                <li className="px-5 py-10 text-center text-sm text-ink-soft">
                  Searches you run will be listed here.
                </li>
              )}
              {historyData?.history?.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    disabled={!item.prompt}
                    onClick={() => item.prompt && rerun(item.prompt)}
                    className="w-full px-5 py-3.5 text-left transition-colors enabled:hover:bg-shoal/50 disabled:cursor-default"
                  >
                    <span className="line-clamp-2 text-sm font-medium">
                      {item.prompt || (
                        <span className="inline-flex items-center gap-1.5 text-ink-soft">
                          <ImageIcon className="size-4" aria-hidden /> Photo search
                        </span>
                      )}
                    </span>
                    <span className="numerals mt-1 block text-xs text-ink-soft">
                      {formatDate(item.createdAt)}, {item.returnedProductIds.length} results
                      {item.hasImage && item.prompt ? ', with a photo' : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </ScrollArea>
        </div>
      </div>
      {showHistory && (
        <div className="fixed inset-0 z-40 bg-ink/20 animate-in fade-in duration-200" onClick={() => setShowHistory(false)} />
      )}

      <Dialog open={!!selectedProduct} onOpenChange={(open) => !open && setSelectedProduct(null)}>
        <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto p-0 sm:rounded-xl">
          <DialogTitle className="sr-only">{selectedProduct?.name ?? 'Product details'}</DialogTitle>
          <div className="p-6 md:p-10">{selectedProduct && <ProductDetail productId={selectedProduct.id} />}</div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default function AssistantPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center">
          <Spinner className="size-8" />
        </div>
      }
    >
      <AssistantContent />
    </Suspense>
  )
}
