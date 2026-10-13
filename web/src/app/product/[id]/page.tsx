import { Header } from '@/components/header'
import { ProductDetail } from '@/components/product-detail'
import { SiteFooter } from '@/components/site-footer'

interface ProductPageProps {
  params: Promise<{ id: string }>
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { id } = await params

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="shell flex-1 py-10 sm:py-14">
        <ProductDetail productId={id} />
      </main>
      <SiteFooter />
    </div>
  )
}
