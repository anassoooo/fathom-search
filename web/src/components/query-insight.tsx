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

/** What the LLM inferred from the request: the transparency half of query understanding. */
export function insightChips(insight: QueryInsightData, original: string) {
  const u = insight.understood
  const f = insight.appliedFilters ?? {}
  const chips: { label: string; value: string }[] = []

  if (u?.search_text && u.search_text.trim().toLowerCase() !== original.trim().toLowerCase()) {
    chips.push({ label: 'Looked for', value: `“${u.search_text}”` })
  }
  if (f.price_min != null && f.price_max != null) {
    chips.push({ label: 'Budget', value: `${money(f.price_min)} to ${money(f.price_max)}` })
  } else if (f.price_max != null) {
    chips.push({ label: 'Budget', value: `up to ${money(f.price_max)}` })
  } else if (f.price_min != null) {
    chips.push({ label: 'Budget', value: `from ${money(f.price_min)}` })
  }
  if (f.price_bucket) {
    chips.push({ label: 'Price range', value: f.price_bucket === 'cheap' ? 'budget picks' : f.price_bucket })
  }
  if (insight.boostedCategory) {
    chips.push({ label: 'Favoured', value: insight.boostedCategory })
  }
  return chips
}

export function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex max-w-full items-baseline gap-1.5 rounded-md bg-shoal px-2 py-1 text-[0.8125rem] leading-tight">
      <span className="shrink-0 text-ink-soft">{label}</span>
      <span className="min-w-0 truncate font-medium text-ink">{value}</span>
    </span>
  )
}
