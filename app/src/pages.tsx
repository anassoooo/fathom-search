import { Header } from '@/components/header'
import { Catalog } from '@/components/catalog'
import { AssistantButton } from '@/components/assistant-button'

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 container py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Products</h1>
            <p className="text-muted-foreground mt-1">
              Discover our curated collection of products
            </p>
          </div>
          <Catalog />
        </div>
      </main>
      <AssistantButton />
    </div>
  )
}
