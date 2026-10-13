'use client'

import { Chip, insightChips, type QueryInsightData } from '@/components/query-insight'
import { cn } from '@/lib/utils'

/**
 * The search pipeline drawn as a sounding line: a lead line dropped through each stage,
 * with real server timings. Segment length grows with the time a stage took, so the
 * line is literally longest where the work was.
 */

interface Stage {
  key: string
  title: string
  detail?: string
  ms?: number
  skipped?: string
  chips?: { label: string; value: string }[]
}

function buildStages(
  timings: Record<string, number>,
  insight: QueryInsightData,
  original: string,
  hasImage: boolean,
): Stage[] {
  const stages: Stage[] = []
  const llmDown = insight.degraded.includes('llm')

  if ('understand_ms' in timings || llmDown) {
    const chips = llmDown ? [] : insightChips(insight, original)
    stages.push({
      key: 'understand',
      title: 'Read the request',
      ms: timings.understand_ms,
      skipped: llmDown ? 'The language model did not answer, so this ran as a plain search.' : undefined,
      // A live LLM call never returns in under 5 ms; that only happens on a cache hit.
      detail: llmDown
        ? undefined
        : timings.understand_ms != null && timings.understand_ms < 5
          ? 'Answered from cache: this exact request was read before.'
          : chips.length === 0
            ? 'Nothing to add: the request was already a clear search.'
            : undefined,
      chips,
    })
  }
  if ('encode_ms' in timings) {
    stages.push({
      key: 'encode',
      title: hasImage && original ? 'Encoded your words and photo' : hasImage ? 'Encoded your photo' : 'Encoded the meaning',
      detail: 'Turned into embeddings, plus BM25 keyword weights for text.',
      ms: timings.encode_ms,
    })
  }
  if ('retrieve_ms' in timings) {
    stages.push({
      key: 'retrieve',
      title: 'Searched 35,736 products',
      detail: 'Keyword and vector results, merged into one list.',
      ms: timings.retrieve_ms,
    })
  }
  if ('rerank_ms' in timings || insight.degraded.includes('reranker')) {
    stages.push({
      key: 'rerank',
      title: 'Re-ranked the top candidates',
      detail: 'A cross-encoder compared each one with your words.',
      ms: timings.rerank_ms,
      skipped: insight.degraded.includes('reranker')
        ? 'The re-ranker timed out, so the merged order was kept.'
        : undefined,
    })
  }
  return stages
}

/** Pixels of line below a stage: grows with sqrt(ms), clamped so tiny stages stay readable. */
function segment(ms?: number) {
  if (ms == null) return 28
  return Math.round(Math.min(96, Math.max(20, 12 + Math.sqrt(ms) * 4.2)))
}

const ms = (n: number) => (n < 10 ? n.toFixed(1) : Math.round(n).toLocaleString())

export function SoundingLine({
  timings,
  insight,
  original,
  hasImage,
  resultCount,
  runId,
}: {
  timings: Record<string, number>
  insight: QueryInsightData
  original: string
  hasImage: boolean
  resultCount: number
  /** Changes on every search so the drop animation replays. */
  runId: string
}) {
  const stages = buildStages(timings, insight, original, hasImage)
  const total = timings.total_ms

  return (
    <section aria-labelledby="sounding-heading" className="scroll-mt-24 rounded-xl border border-rule bg-surface p-5" key={runId}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="sounding-heading" className="font-serif text-xl italic">
          How this search ran
        </h2>
        {total != null && (
          <p className="numerals text-sm text-ink-soft">
            <span className="font-semibold text-ink">{ms(total)}</span> ms total
          </p>
        )}
      </div>

      <ol className="relative mt-5">
        {/* the lead line */}
        <span
          aria-hidden
          className="animate-sound-drop absolute bottom-3 left-[6px] top-2 w-[1.5px] bg-contour/70"
        />
        {stages.map((s, i) => (
          <li
            key={s.key}
            className="animate-mark-in relative pl-7"
            style={{ animationDelay: `${180 + i * 140}ms`, paddingBottom: segment(s.ms) }}
          >
            <span
              aria-hidden
              className={cn(
                'absolute left-0 top-[5px] size-[13.5px] rounded-full border-2 bg-surface',
                s.skipped ? 'border-dashed border-ink-soft' : 'border-contour',
              )}
            />
            <div className="flex items-baseline justify-between gap-3">
              <h3 className={cn('text-[0.9375rem] font-medium', s.skipped && 'text-ink-soft')}>{s.title}</h3>
              <span className="numerals shrink-0 text-sm text-ink-soft">
                {s.skipped ? 'skipped' : s.ms != null ? `${ms(s.ms)} ms` : null}
              </span>
            </div>
            {(s.skipped || s.detail) && (
              <p className="mt-0.5 text-[0.8125rem] leading-snug text-ink-soft">{s.skipped ?? s.detail}</p>
            )}
            {s.chips && s.chips.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {s.chips.map((c) => (
                  <Chip key={c.label} label={c.label} value={c.value} />
                ))}
              </div>
            )}
          </li>
        ))}
        <li
          className="animate-mark-in relative pl-7"
          style={{ animationDelay: `${180 + stages.length * 140}ms` }}
        >
          <span aria-hidden className="absolute left-[1px] top-[4px] size-3 rotate-45 rounded-[2px] bg-signal" />
          <p className="text-[0.9375rem] font-semibold text-signal">
            {resultCount} {resultCount === 1 ? 'result' : 'results'}, best match first
          </p>
        </li>
      </ol>
      <p className="mt-4 border-t border-rule pt-3 text-xs leading-relaxed text-ink-soft">
        Times are measured on the search server for this request. The first search after a quiet
        spell is slower while the server loads its models.
      </p>
    </section>
  )
}
