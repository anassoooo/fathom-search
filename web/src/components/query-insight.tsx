'use client'

import { AlertTriangle, Sparkles } from 'lucide-react'

export interface QueryInsightData {
  understood: {
    search_text?: string
    price_min?: number | null
    price_max?: number | null
    price_intent?: 'cheap' | 'premium' | null
  } | null
  boostedCategory: string | null
  appliedFilters?: { price_min?: number | null; price_max?: number | null; price_bucket?: string | null }
  degraded: string[]
}

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n)

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border/50 bg-background/60 px-3 py-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </span>
  )
}

/** Shows what the LLM inferred from the request: the transparency half of query understanding. */
export function QueryInsight({ insight, original }: { insight: QueryInsightData; original: string }) {
  const llmDown = insight.degraded.includes('llm')
  const u = insight.understood
  const f = insight.appliedFilters ?? {}
  const chips: { label: string; value: string }[] = []

  if (u?.search_text && u.search_text.trim().toLowerCase() !== original.trim().toLowerCase()) {
    chips.push({ label: 'Searched for', value: `“${u.search_text}”` })
  }
  if (f.price_min != null && f.price_max != null) {
    chips.push({ label: 'Budget', value: `${money(f.price_min)} – ${money(f.price_max)}` })
  } else if (f.price_max != null) {
    chips.push({ label: 'Budget', value: `up to ${money(f.price_max)}` })
  } else if (f.price_min != null) {
    chips.push({ label: 'Budget', value: `from ${money(f.price_min)}` })
  }
  if (f.price_bucket) {
    chips.push({ label: 'Price range', value: f.price_bucket === 'cheap' ? 'budget picks' : f.price_bucket })
  }
  if (insight.boostedCategory) {
    chips.push({ label: 'Prioritizing', value: insight.boostedCategory })
  }

  if (llmDown) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-border/50 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
        AI query understanding is unavailable right now, so these are standard search results.
      </div>
    )
  }
  if (chips.length === 0) return null

  return (
    <div className="space-y-2 px-2" aria-label="How your request was understood">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5 text-accent" aria-hidden />
        How we understood your request
      </p>
      <div className="flex flex-wrap gap-2">
        {chips.map((c) => (
          <Chip key={c.label} label={c.label} value={c.value} />
        ))}
      </div>
    </div>
  )
}
