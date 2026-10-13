import { Wordmark } from '@/components/brand'

const LINKS = [
  { href: 'https://github.com/anassoooo/fathom-search', label: 'Source code' },
  { href: 'https://github.com/anassoooo/fathom-search#results', label: 'Evaluation' },
  { href: 'https://github.com/anassoooo/fathom-search#limitations', label: 'Limitations' },
  { href: 'https://v0-anassoooo.vercel.app', label: 'Portfolio' },
]

export function SiteFooter() {
  return (
    <footer className="border-t border-rule">
      <div className="shell flex flex-col gap-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <Wordmark />
          <p className="max-w-sm text-sm text-ink-soft">
            A portfolio project by Anas Bougrine. The listings are Amazon catalog data used for the
            demo, so nothing here is for sale.
          </p>
        </div>
        <nav aria-label="Project" className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href} className="text-ink-soft hover:text-ink">
              {l.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  )
}
