'use client'

import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface PaginationControlsProps {
  page: number
  limit: number
  total?: number
  hasMore: boolean
  onPageChange: (page: number) => void
  onLimitChange: (limit: number) => void
}

export function PaginationControls({
  page,
  limit,
  total,
  hasMore,
  onPageChange,
  onLimitChange,
}: PaginationControlsProps) {
  const totalPages = total ? Math.ceil(total / limit) : undefined

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 py-4">
      <div className="flex items-center gap-3">
        <span className="text-premium-label">Show</span>
        <Select
          value={String(limit)}
          onValueChange={(value) => onLimitChange(Number(value))}
        >
          <SelectTrigger className="w-24 bg-background border border-border/10 shadow-sm h-8 rounded-xl text-premium-label font-bold focus:ring-accent/30 transition-all">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="rounded-xl border-border/40">
            <SelectItem value="12">12</SelectItem>
            <SelectItem value="24">24</SelectItem>
            <SelectItem value="48">48</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-premium-label">per page</span>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>

        <div className="flex items-center gap-2 px-2">
          <span className="text-premium-title text-sm">Page {page}</span>
          {totalPages && (
            <span className="text-premium-label">of {totalPages}</span>
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={!hasMore}
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {total && (
        <div className="text-premium-label">
          {total.toLocaleString()} products total
        </div>
      )}
    </div>
  )
}
