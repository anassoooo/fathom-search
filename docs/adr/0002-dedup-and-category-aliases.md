# 0002 — Merge duplicate listings at ingest; normalize overlapping categories

- **Status:** accepted
- **Date:** 2026-10-10
- **Task:** T002 follow-up (data profiling)

## Context
Profiling the full catalog (42,427 rows, `data/README.md`) found:
- **Duplicate listings.** 6,054 titles repeat (10,069 extra rows). They are typically
  the same item scraped under several categories, e.g. one Acer laptop under both
  *Electronics › Laptops* and *Gaming & Accessories › Gaming laptops*. Left alone, the
  same product fills several result slots, and eval metrics count a hit several times.
- **Overlapping categories.** *Art & Craft* / *Arts & Crafts* / *Art Supplies*, among
  others. A category filter, whether typed by a user or extracted by the LLM, would
  miss products filed under a sibling category.

## Decision
**1. Merge at ingest** (`vio/ingest/normalize.py`). Listings are the same item when
**normalized title + price + Amazon image ID** all match. The merged point keeps the
lowest-ID listing's fields and gains `categories`, `subcategories` (canonical, all
listings), `raw_categories` (original spellings), and `merged_ids`. Filters match on
the arrays, so a product is found under any category it was listed in.

**2. Category alias map** (`vio/catalog.py`, committed and reviewable). Merges were
chosen only where names are near-identical or subcategory overlap is large:

| Canonical | Merged from | Evidence (share of identical subcategories) |
|---|---|---|
| Arts & Crafts | Art & Craft, Art Supplies | 25% / 18%; near-identical names |
| Beauty & Personal Care | Beauty & Personal | truncated name; complementary subcategories |
| Health & Household | Healthcare & Wellness | 18% (vitamins, first aid, masks) |
| Music & Instruments | Music, Music Instruments | 18% (guitars, mics, drumsticks) |

*Kitchenware* and *Home Appliances* share 17% of subcategories but are kept apart:
they are distinct departments, and the merge in (1) already lists true duplicates
under both. Subcategory spelling variants ("Oil paints" / "Oil Paints") collapse to
the most frequent spelling.

## Alternatives considered
| Option | Why not |
|---|---|
| Identity = title + price | Falsely merged distinct items with brand-only titles: 23 different "PAVOI" jewelry pieces at one price became one product. 298 such groups. |
| Identity = image only | Merges different offers that reuse a photo ("Like-New Fire TV Stick" vs new). |
| Raw image URL instead of image ID | URLs differ only by thumbnail-size suffix (`._AC_UY218_` vs `._AC_UL320_`), which would miss true duplicates. |
| Collapse at query time (Qdrant group-by) | Extra work on every query; eval must still treat copies as one item; index stays 16% larger. |
| Leave as-is | Repeated results and distorted metrics. |

## Consequences
- 42,427 rows → **35,736 products** (6,691 merged, about 16%); 30 → **25 categories**;
  1,337 products are now reachable under more than one category.
- Point IDs come from the lowest merged `Product ID`, so they stay deterministic.
- `price_bucket` was computed per subcategory upstream; a merged product keeps its
  primary listing's bucket.
- Eval relevance labels (M2) are defined over merged products. A query can no longer
  be "solved" by several copies of one item.
- The legacy v1 collection used by the web app is unaffected until M4.
