import { NextResponse } from 'next/server'
import { isAdmin } from '@/lib/auth'
import { prisma } from '@/lib/prisma'

type Meta = {
  list_type?: string
  query_type?: string
  product_id?: string
  seed_product_id?: string
  rank?: number
  returned_product_ids?: string[]
}

function safeParse(meta: string | null): Meta {
  if (!meta) return {}
  try {
    return JSON.parse(meta) as Meta
  } catch {
    return {}
  }
}

export async function GET() {
  if (!(await isAdmin())) {
    return NextResponse.json({ error: 'Metrics are restricted to admins' }, { status: 403 })
  }
  try {
    // Keep your global totals (fast counts)
    const [impressions, clicks, addToCarts, assistantOpens, assistantRecommends] =
      await Promise.all([
        prisma.event.count({ where: { eventType: 'product_impression' } }),
        prisma.event.count({ where: { eventType: 'product_click' } }),
        prisma.event.count({ where: { eventType: 'add_to_cart' } }),
        prisma.event.count({ where: { eventType: 'assistant_open' } }),
        prisma.event.count({ where: { eventType: 'assistant_recommend' } }),
      ])

    const ctr = impressions > 0 ? (clicks / impressions) : 0
    const addToCartRate = impressions > 0 ? (addToCarts / impressions) : 0

    // Time window (recommended for "quality of recommendations")
    const sevenDaysAgo = new Date()
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)

    // Pull recent events once, then compute breakdowns in-memory
    const recentEvents = await prisma.event.findMany({
      where: { createdAt: { gte: sevenDaysAgo } },
      orderBy: { createdAt: 'desc' },
      take: 5000,
      select: { id: true, eventType: true, createdAt: true, userId: true, metadata: true },
    })

    // Similar-products CTR (overall + by query_type + by rank)
    let similarImpressions = 0
    let similarClicks = 0

    const similarByQuery: Record<string, { imp: number; clk: number }> = {}

    const MAX_RANK = 5
    const similarByRank = Array.from({ length: MAX_RANK }, (_, i) => ({
      rank: i + 1,
      impressions: 0,
      clicks: 0,
    }))

    for (const e of recentEvents) {
      const m = safeParse(e.metadata)
      const listType = m.list_type ?? 'unknown'
      const queryType = m.query_type ?? 'unknown'

      if (listType !== 'similar') continue

      if (!similarByQuery[queryType]) similarByQuery[queryType] = { imp: 0, clk: 0 }

      if (e.eventType === 'product_impression') {
        similarImpressions++
        similarByQuery[queryType].imp++
      } else if (e.eventType === 'product_click') {
        similarClicks++
        similarByQuery[queryType].clk++
      }

      // Track by rank
      const r = typeof m.rank === 'number' ? m.rank : Number(m.rank)
      if (Number.isFinite(r) && r >= 1 && r <= MAX_RANK) {
        const idx = r - 1
        if (e.eventType === 'product_impression') similarByRank[idx].impressions++
        if (e.eventType === 'product_click') similarByRank[idx].clicks++
      }
    }

    const similarCtr = similarImpressions > 0 ? (similarClicks / similarImpressions) : 0

    const similarCtrByQueryType = Object.entries(similarByQuery).map(([query_type, v]) => ({
      query_type,
      impressions: v.imp,
      clicks: v.clk,
      ctr: v.imp ? +(100 * v.clk / v.imp).toFixed(2) : 0,
    }))

    const similarCtrByRankTop5 = similarByRank.map((x) => ({
      rank: x.rank,
      impressions: x.impressions,
      clicks: x.clicks,
      ctr: x.impressions ? +(100 * x.clicks / x.impressions).toFixed(2) : 0,
    }))

    // Keep your "latest 50 events" feed (not restricted)
    const recentEventsItems = await prisma.event.findMany({
      orderBy: { createdAt: 'desc' },
      take: 50,
    })

    const dailyEventsGroupBy = await prisma.event.groupBy({
      by: ['eventType'],
      _count: { _all: true },
      where: { createdAt: { gte: sevenDaysAgo } },
    })

    return NextResponse.json({
      totals: { impressions, clicks, addToCarts, assistantOpens, assistantRecommends },
      rates: {
        ctr: `${(ctr * 100).toFixed(2)}%`,
        addToCartRate: `${(addToCartRate * 100).toFixed(2)}%`,
      },

      // ✅ New: recommendation-specific engagement
      similar: {
        impressions: similarImpressions,
        clicks: similarClicks,
        ctr: `${(similarCtr * 100).toFixed(2)}%`,
        ctrByQueryType: similarCtrByQueryType,
        ctrByRankTop5: similarCtrByRankTop5,
      },

      recentEvents: recentEventsItems.map((e) => ({
        id: e.id,
        eventType: e.eventType,
        createdAt: e.createdAt,
        hasUser: !!e.userId,
      })),
      dailyBreakdown: dailyEventsGroupBy.map((d) => ({
        eventType: d.eventType,
        count: d._count._all,
      })),
    })
  } catch (error) {
    console.error('Error fetching metrics:', error)
    return NextResponse.json({ error: 'Failed to fetch metrics' }, { status: 500 })
  }
}
