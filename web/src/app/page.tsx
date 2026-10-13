import { Suspense } from 'react'
import { Header } from '@/components/header'
import { Catalog } from '@/components/catalog'
import { HeroSearch } from '@/components/hero-search'
import { ContourField } from '@/components/brand'
import { SiteFooter } from '@/components/site-footer'

const REPO = 'https://github.com/anassoooo/fathom-search'

// A real sequence (the search pipeline, in order), so the steps are numbered.
const STEPS = [
  {
    title: 'Read the request',
    body: 'A language model pulls out what to look for, any budget, and a likely category. If it is unavailable, the search still runs without it.',
  },
  {
    title: 'Search two ways at once',
    body: 'Keyword search (BM25) and vector search over text and image embeddings run side by side, and their result lists are merged.',
  },
  {
    title: 'Re-rank the best candidates',
    body: 'A cross-encoder reads each top candidate together with your words and puts the closest matches first.',
  },
  {
    title: 'Show the working',
    body: 'The results page shows what was understood and how long each step took, so you can see why you got what you got.',
  },
]

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="flex-1">
        <section className="relative overflow-hidden border-b border-rule">
          <ContourField className="absolute -right-40 top-1/2 hidden w-[56rem] max-w-none -translate-y-1/2 md:block lg:-right-24" />
          <div className="shell relative py-16 sm:py-24 lg:py-28">
            <div className="max-w-[40rem] space-y-8">
              <h1 className="display text-[2.75rem] sm:text-[4rem] lg:text-[4.75rem]">
                Describe it, or show a photo.
              </h1>
              <p className="max-w-[34rem] text-lg leading-relaxed text-ink-soft sm:text-xl">
                Fathom searches 35,736 products by meaning, not just matching words. Ask the way
                you would ask a person, with a budget, a purpose, or a picture.
              </p>
              <HeroSearch />
            </div>
          </div>
        </section>

        <section aria-labelledby="how-heading" className="border-b border-rule bg-surface">
          <div className="shell py-16 sm:py-20">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <h2 id="how-heading" className="display text-[2rem] sm:text-[2.5rem]">
                What happens when you search
              </h2>
              <a
                href={`${REPO}#results`}
                className="text-sm text-ink underline decoration-rule underline-offset-4 hover:decoration-contour"
              >
                How the ranking was evaluated
              </a>
            </div>
            <ol className="mt-10 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step, i) => (
                <li key={step.title} className="relative border-t border-rule pt-5">
                  <span
                    aria-hidden
                    className="absolute -top-[5px] left-0 size-[9px] rounded-full border-2 border-contour bg-surface"
                  />
                  <p className="font-serif text-xl italic text-contour">{i + 1}</p>
                  <h3 className="mt-1 text-[1.0625rem] font-semibold">{step.title}</h3>
                  <p className="mt-2 text-[0.9375rem] leading-relaxed text-ink-soft">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="catalog" aria-labelledby="catalog-heading" className="scroll-mt-16">
          <div className="shell space-y-8 py-16 sm:py-20">
            <div className="space-y-2">
              <h2 id="catalog-heading" className="display text-[2rem] sm:text-[2.5rem]">
                Browse the catalog
              </h2>
              <p className="text-ink-soft">35,736 products across 25 categories.</p>
            </div>
            <Suspense fallback={null}>
              <Catalog />
            </Suspense>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}
