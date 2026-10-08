'use client'

import React, { useCallback, useEffect, useState } from 'react'
import useEmblaCarousel from 'embla-carousel-react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { ProductCard } from './product-card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Product } from '@/lib/types'

interface ProductCarouselProps {
    products: Product[]
    className?: string
    title?: string
    analytics?: { list_type: string; query_type: string; seed_product_id?: string }
}

export function ProductCarousel({ products, className, title, analytics }: ProductCarouselProps) {
    const [emblaRef, emblaApi] = useEmblaCarousel({
        align: 'start',
        containScroll: 'trimSnaps',
        loop: false,
        dragFree: true,
    })

    const [prevBtnEnabled, setPrevBtnEnabled] = useState(false)
    const [nextBtnEnabled, setNextBtnEnabled] = useState(false)

    const scrollPrev = useCallback(() => emblaApi && emblaApi.scrollPrev(), [emblaApi])
    const scrollNext = useCallback(() => emblaApi && emblaApi.scrollNext(), [emblaApi])

    const onSelect = useCallback(() => {
        if (!emblaApi) return
        setPrevBtnEnabled(emblaApi.canScrollPrev())
        setNextBtnEnabled(emblaApi.canScrollNext())
    }, [emblaApi])

    useEffect(() => {
        if (!emblaApi) return
        // Initial read of the carousel's state (external system), then subscribe.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        onSelect()
        emblaApi.on('select', onSelect)
        emblaApi.on('reInit', onSelect)
    }, [emblaApi, onSelect])

    if (products.length === 0) return null

    return (
        <div className={cn("group/carousel relative", className)}>
            {title && (
                <div className="flex items-center justify-between mb-6 px-1">
                    <h2 className="text-2xl font-bold tracking-[0.05em] uppercase text-muted-foreground/60">
                        {title}
                    </h2>
                    <div className="hidden md:flex items-center gap-2 opacity-0 group-hover/carousel:opacity-100 transition-opacity duration-300">
                        <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm"
                            disabled={!prevBtnEnabled}
                            onClick={scrollPrev}
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm"
                            disabled={!nextBtnEnabled}
                            onClick={scrollNext}
                        >
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}

            <div className="overflow-hidden -mx-4 px-4 sm:-mx-0 sm:px-0" ref={emblaRef}>
                <div className="flex touch-pan-y -ml-4">
                    {products.map((product, idx) => (
                        <div
                            key={product.id}
                            className="flex-[0_0_85%] min-w-0 pl-4 sm:flex-[0_0_45%] md:flex-[0_0_33.333%] lg:flex-[0_0_25%]"
                        >
                            <div className="h-full transform transition-transform duration-300 hover:-translate-y-1">
                                <ProductCard
                                    product={product}
                                    rank={idx + 1}
                                    analytics={analytics}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
