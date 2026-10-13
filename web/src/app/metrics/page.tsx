'use client'

import React from "react"

import useSWR from 'swr'
import { Header } from '@/components/header'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Eye, MousePointer, ShoppingCart, Sparkles, MessageSquare } from 'lucide-react'

interface MetricsData {
  totals: {
    impressions: number
    clicks: number
    addToCarts: number
    assistantOpens: number
    assistantRecommends: number
  }
  rates: {
    ctr: string
    addToCartRate: string
  }
  assistant?: {
    ctrByVariant: Array<{ variant: string; impressions: number; clicks: number; ctr: number }>
  }
  recentEvents: Array<{
    id: string
    eventType: string
    createdAt: string
    hasUser: boolean
  }>
  dailyBreakdown: Array<{
    eventType: string
    count: number
  }>
}

const fetcher = async (url: string) => {
  const res = await fetch(url)
  const body = await res.json()
  if (!res.ok) throw new Error(body?.error ?? `Request failed (${res.status})`)
  return body
}

const eventTypeIcons: Record<string, React.ReactNode> = {
  product_impression: <Eye className="h-4 w-4" />,
  product_click: <MousePointer className="h-4 w-4" />,
  add_to_cart: <ShoppingCart className="h-4 w-4" />,
  assistant_open: <Sparkles className="h-4 w-4" />,
  assistant_recommend: <MessageSquare className="h-4 w-4" />,
}

const eventTypeLabels: Record<string, string> = {
  product_impression: 'Impression',
  product_click: 'Click',
  add_to_cart: 'Add to Cart',
  assistant_open: 'Assistant Open',
  assistant_recommend: 'Assistant Query',
}

export default function MetricsPage() {
  const { data, isLoading, error } = useSWR<MetricsData>('/api/metrics', fetcher, {
    refreshInterval: 30000, // Refresh every 30 seconds
  })

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <p className="text-muted-foreground">{error.message}</p>
      </div>
    )
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="shell flex-1 py-10">
        <div className="space-y-6">
          <div>
            <h1 className="display text-[2.25rem]">Usage</h1>
            <p className="mt-1 text-ink-soft">
              Impressions, clicks and carts logged by this site, with click-through per retrieval variant.
            </p>
          </div>

          {/* Key Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <MetricCard
              title="Impressions"
              value={data?.totals.impressions}
              icon={<Eye className="h-5 w-5" />}
              isLoading={isLoading}
            />
            <MetricCard
              title="Clicks"
              value={data?.totals.clicks}
              icon={<MousePointer className="h-5 w-5" />}
              isLoading={isLoading}
            />
            <MetricCard
              title="Add to Cart"
              value={data?.totals.addToCarts}
              icon={<ShoppingCart className="h-5 w-5" />}
              isLoading={isLoading}
            />
            <MetricCard
              title="Assistant Opens"
              value={data?.totals.assistantOpens}
              icon={<Sparkles className="h-5 w-5" />}
              isLoading={isLoading}
            />
            <MetricCard
              title="Assistant Queries"
              value={data?.totals.assistantRecommends}
              icon={<MessageSquare className="h-5 w-5" />}
              isLoading={isLoading}
            />
          </div>

          {/* Conversion Rates */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Click-Through Rate (CTR)</CardTitle>
                <CardDescription>Clicks / Impressions</CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-12 w-24" />
                ) : (
                  <p className="numerals text-4xl font-semibold">{data?.rates.ctr || '0%'}</p>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Add to Cart Rate</CardTitle>
                <CardDescription>Add to Cart / Impressions</CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-12 w-24" />
                ) : (
                  <p className="numerals text-4xl font-semibold">{data?.rates.addToCartRate || '0%'}</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Assistant CTR by retrieval variant */}
          <Card>
            <CardHeader>
              <CardTitle>Assistant CTR by variant</CardTitle>
              <CardDescription>
                Online clicks / impressions per retrieval variant (last 7 days)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-12 w-full" />
              ) : data?.assistant?.ctrByVariant.length ? (
                <table className="w-full text-sm">
                  <thead className="text-left text-muted-foreground">
                    <tr>
                      <th className="py-1 font-medium">Variant</th>
                      <th className="py-1 font-medium text-right">Impressions</th>
                      <th className="py-1 font-medium text-right">Clicks</th>
                      <th className="py-1 font-medium text-right">CTR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.assistant.ctrByVariant.map((row) => (
                      <tr key={row.variant} className="border-t border-border/40">
                        <td className="py-1 font-medium">{row.variant}</td>
                        <td className="py-1 text-right tabular-nums">{row.impressions}</td>
                        <td className="py-1 text-right tabular-nums">{row.clicks}</td>
                        <td className="py-1 text-right tabular-nums">{row.ctr}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-muted-foreground">No assistant traffic yet.</p>
              )}
            </CardContent>
          </Card>

          {/* Recent Events */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>Latest 50 events (auto-refreshes every 30s)</CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {data?.recentEvents.map((event) => (
                      <div
                        key={event.id}
                        className="flex items-center justify-between rounded-lg bg-shoal/50 p-3"
                      >
                        <div className="flex items-center gap-3">
                          <div className="rounded-full bg-surface p-2">
                            {eventTypeIcons[event.eventType] || <Eye className="h-4 w-4" />}
                          </div>
                          <div>
                            <p className="font-medium text-sm">
                              {eventTypeLabels[event.eventType] || event.eventType}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(event.createdAt)}
                            </p>
                          </div>
                        </div>
                        <Badge variant={event.hasUser ? 'default' : 'secondary'}>
                          {event.hasUser ? 'Logged In' : 'Anonymous'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}

function MetricCard({
  title,
  value,
  icon,
  isLoading,
}: {
  title: string
  value?: number
  icon: React.ReactNode
  isLoading: boolean
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            {isLoading ? (
              <Skeleton className="h-8 w-16 mt-1" />
            ) : (
              <p className="numerals text-2xl font-semibold">{value?.toLocaleString() || 0}</p>
            )}
          </div>
          <div className="rounded-full bg-shoal p-3 text-contour">{icon}</div>
        </div>
      </CardContent>
    </Card>
  )
}
