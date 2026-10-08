import { Header } from '@/components/header'
import { ProductDetail } from '@/components/product-detail'
import { AssistantButton } from '@/components/assistant-button'

interface ProductPageProps {
    params: Promise<{ id: string }>
}

export default async function ProductPage({ params }: ProductPageProps) {
    const { id } = await params

    return (
        <div className="min-h-screen flex flex-col bg-background/40 backdrop-blur-3xl bg-grid-premium/10 selection:bg-accent/30">
            <Header>
                <h1 className="font-bold text-sm tracking-[0.15em] text-foreground/90 uppercase">Product Details</h1>
            </Header>
            <main className="flex-1 container-premium py-12">
                <ProductDetail productId={id} />
            </main>
            <AssistantButton />
        </div>
    )
}
