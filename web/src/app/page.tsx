import Link from 'next/link'
import { Header } from '@/components/header'
import { Suspense } from 'react'
import { Catalog } from '@/components/catalog'
import { AssistantButton } from '@/components/assistant-button'
import { Button } from '@/components/ui/button'
import { Sparkles, ShoppingBag, ShieldCheck, Zap } from 'lucide-react'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-grid-premium bg-background/50 overflow-hidden selection:bg-accent/30">
      <Header />

      <main className="flex-1">
        {/* Professional Hero Section */}
        <section className="relative overflow-hidden pt-12 pb-16 md:pt-20 md:pb-24">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-full pointer-events-none opacity-50">
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-accent/10 blur-[120px] rounded-full" />
            <div className="absolute bottom-[10%] right-[-10%] w-[30%] h-[30%] bg-primary/10 blur-[100px] rounded-full" />
          </div>

          <div className="container relative z-10">
            <div className="max-w-4xl mx-auto text-center flex flex-col items-center space-y-8">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs font-bold uppercase tracking-widest animate-in fade-in slide-in-from-bottom-2 duration-700">
                <Sparkles className="w-3 h-3" />
                AI-Driven Fashion Discovery
              </div>

              <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight text-balance leading-[1.1]">
                Elevate Your <span className="bg-clip-text text-transparent bg-linear-to-r from-accent to-primary">Style</span> with Precision.
              </h1>

              <p className="text-xl md:text-2xl text-muted-foreground max-w-2xl leading-relaxed animate-in fade-in slide-in-from-bottom-4 duration-700 delay-200">
                Experience the world&apos;s most advanced e-commerce engine.
                Our AI understands your vibe, not just your keywords.
              </p>

              <div className="flex flex-wrap items-center justify-center gap-4 pt-4 animate-in fade-in slide-in-from-bottom-6 duration-700 delay-300">
                <Link href="#catalog">
                  <Button size="lg" variant="glow" className="h-14 px-10 rounded-2xl text-md font-bold">
                    Shop Collection
                    <ShoppingBag className="ml-2 w-5 h-5" />
                  </Button>
                </Link>
                <Link href="/assistant">
                  <Button size="lg" variant="outline" className="h-14 px-10 rounded-2xl text-md border-border/60 hover:bg-muted/50">
                    Try AI Assistant
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* Qdrant Attribution - Middle of page */}
        <div className="py-20 relative overflow-hidden bg-background/10 backdrop-blur-sm">
          <div className="container-premium max-w-7xl mx-auto flex flex-col items-center justify-center text-center space-y-6">
            <div className="flex items-center gap-3 text-sm font-semibold text-muted-foreground/40 tracking-[0.3em] uppercase">
              <div className="h-px w-10 bg-border/20" />
              Advanced Architecture
              <div className="h-px w-10 bg-border/20" />
            </div>
            <p className="text-xl md:text-2xl text-muted-foreground/80 font-medium flex flex-wrap items-center justify-center gap-3">
              Powered by <span className="text-foreground font-bold inline-flex items-center gap-3 bg-white/5 px-4 py-1.5 rounded-full ring-1 ring-white/10 shadow-sm">
                <span className="status-online" aria-hidden="true" />
                Qdrant Vector Database
              </span>
            </p>
            <p className="text-sm text-muted-foreground/40 uppercase tracking-widest font-bold">Lightning-fast semantic search</p>
          </div>
        </div>

        {/* Value Propositions */}
        <section className="py-16">
          <div className="container-premium">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
              <FeatureItem
                icon={<Zap className="w-6 h-6 text-accent" />}
                title="Semantic Search"
                description="Find what you actually want using natural language and image similarity."
              />
              <FeatureItem
                icon={<ShieldCheck className="w-6 h-6 text-emerald-500" />}
                title="Premium Quality"
                description="Curated collection of high-end products verified for authenticity."
              />
              <FeatureItem
                icon={<Sparkles className="w-6 h-6 text-primary" />}
                title="AI Personalization"
                description="Our assistant learns your preferences to give unique recommendations."
              />
            </div>
          </div>
        </section>

        {/* Main Catalog Section */}
        <section id="catalog" className="py-24 bg-dots/5 scroll-mt-20">
          <div className="container-premium space-y-10">
            <div className="flex flex-col items-center text-center gap-3 mb-8">
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight">Our Collection</h2>
              <p className="text-muted-foreground max-w-xl">Discover over 42,000 premium products curated for quality and style.</p>
            </div>

            <Suspense fallback={null}>
              <Catalog />
            </Suspense>
          </div>
        </section>
      </main>

      <footer className="border-t py-16">
        <div className="container-premium flex flex-col md:flex-row justify-between items-center gap-12 text-sm text-muted-foreground">
          <div className="flex flex-col items-center md:items-start gap-4">
            <div className="flex items-center gap-3">
              <span className="font-bold text-xl tracking-tight text-foreground">Fathom</span>
              <span className="text-premium-label opacity-60">© 2026</span>
            </div>
            <p className="max-w-xs text-center md:text-left text-premium-title !text-[0.7rem] !font-medium leading-relaxed opacity-70 uppercase tracking-wider">
              The world&apos;s most advanced AI-curated boutique, powered by vector-search technology.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-10">
            <div className="flex flex-col gap-3">
              <span className="text-premium-label text-foreground/80 mb-1">Company</span>
              <Link href="#" className="hover:text-foreground transition-colors text-premium-label opacity-70">Privacy Policy</Link>
              <Link href="#" className="hover:text-foreground transition-colors text-premium-label opacity-70">Terms of Service</Link>
            </div>
            <div className="flex flex-col gap-3">
              <span className="text-premium-label text-foreground/80 mb-1">Support</span>
              <Link href="#" className="hover:text-foreground transition-colors text-premium-label opacity-70">Shipping Info</Link>
              <Link href="#" className="hover:text-foreground transition-colors text-premium-label opacity-70">Returns</Link>
            </div>
            <div className="flex flex-col gap-3">
              <span className="text-premium-label text-foreground/80 mb-1">Social</span>
              <Link href="#" className="hover:text-foreground transition-colors text-premium-label opacity-70">Instagram</Link>
              <Link href="#" className="hover:text-foreground transition-colors text-premium-label opacity-70">Twitter</Link>
            </div>
          </div>
        </div>
      </footer>

      <AssistantButton />
    </div>
  )
}

function FeatureItem({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="flex flex-col items-center text-center space-y-4 group">
      <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center transition-colors group-hover:bg-accent/10 border border-border/40 group-hover:border-accent/20">
        {icon}
      </div>
      <h3 className="text-2xl font-bold">{title}</h3>
      <p className="text-muted-foreground leading-relaxed max-w-xs">{description}</p>
    </div>
  )
}
