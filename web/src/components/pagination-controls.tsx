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
    <div className="flex flex-col items-center justify-between gap-4 border-t border-rule pt-6 sm:flex-row">
      <div className="flex items-center gap-2 text-sm text-ink-soft">
        <label htmlFor="per-page">Show</label>
        <Select value={String(limit)} onValueChange={(value) => onLimitChange(Number(value))}>
          <SelectTrigger id="per-page" className="h-8 w-20 bg-surface">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="12">12</SelectItem>
            <SelectItem value="24">24</SelectItem>
            <SelectItem value="48">48</SelectItem>
          </SelectContent>
        </Select>
        <span>per page</span>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          <ChevronLeft className="size-4" />
          Previous
        </Button>
        <span className="numerals px-2 text-sm text-ink-soft">
          Page <span className="font-medium text-ink">{page}</span>
          {totalPages ? ` of ${totalPages.toLocaleString()}` : null}
        </span>
        <Button variant="outline" size="sm" onClick={() => onPageChange(page + 1)} disabled={!hasMore}>
          Next
          <ChevronRight className="size-4" />
        </Button>
      </div>

      {total ? (
        <p className="numerals text-sm text-ink-soft">{total.toLocaleString()} products</p>
      ) : (
        <span className="hidden sm:block" />
      )}
    </div>
  )
}
