'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Camera, Search } from 'lucide-react'
import { useAuth } from '@/components/auth-provider'
import { searchHref } from '@/components/header'
import { Button } from '@/components/ui/button'

// Requests that exercise the parts plain keyword search gets wrong: budgets,
// audiences, and needs described instead of named.
export const EXAMPLES = [
  'quiet mechanical keyboard under $80',
  'gift for a six-year-old who loves space',
  'something to keep coffee hot all morning',
  'waterproof hiking boots, cheap',
]

export function HeroSearch() {
  const [q, setQ] = useState('')
  const { user } = useAuth()
  const router = useRouter()

  const go = (query: string) => {
    const text = query.trim()
    if (text) router.push(searchHref(!!user, text))
  }

  return (
    <div className="space-y-4">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          go(q)
        }}
        className="flex items-center gap-2 rounded-xl border border-rule bg-surface p-1.5 pl-4 shadow-[0_1px_0_var(--rule)] focus-within:border-contour"
      >
        <Search className="size-5 shrink-0 text-ink-soft" aria-hidden />
        <label htmlFor="hero-q" className="sr-only">
          Describe what you are looking for
        </label>
        <input
          id="hero-q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Describe what you need"
          className="h-11 min-w-0 flex-1 bg-transparent text-base text-ink outline-none placeholder:text-ink-soft/70"
          maxLength={500}
          autoComplete="off"
        />
        <Button type="submit" size="lg" disabled={!q.trim()}>
          Search
        </Button>
      </form>

      <div className="flex flex-wrap items-center gap-x-1 gap-y-2 text-sm">
        <span className="mr-1 text-ink-soft">Try</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => go(ex)}
            className="rounded-full px-2.5 py-1 text-ink underline decoration-rule underline-offset-4 transition-colors hover:bg-shoal/70 hover:decoration-contour"
          >
            {ex}
          </button>
        ))}
      </div>

      <p className="text-sm text-ink-soft">
        <Link
          href={searchHref(!!user)}
          className="inline-flex items-center gap-1.5 text-ink underline decoration-rule underline-offset-4 hover:decoration-contour"
        >
          <Camera className="size-4" aria-hidden />
          Search with a photo instead
        </Link>
        {!user && <span className="block pt-1 sm:inline sm:pl-3 sm:pt-0">Searching needs a free account.</span>}
      </p>
    </div>
  )
}
