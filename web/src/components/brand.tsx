import { cn } from '@/lib/utils'

/**
 * Fathom's mark: depth contours that bunch toward one sounding (the result found).
 * Same geometry as scripts/make_icons.py, drawn with theme tokens so it works in both
 * colour schemes.
 */
export function FathomMark({ className, title }: { className?: string; title?: string }) {
  return (
    <svg
      viewBox="8 8 48 48"
      className={cn('shrink-0', className)}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}
      <g fill="none" strokeWidth={3.2}>
        <circle cx={30} cy={30} r={19.5} stroke="var(--ink)" />
        <circle cx={32.5} cy={32.5} r={11.5} stroke="var(--contour)" />
        <circle cx={34.5} cy={34.5} r={5} stroke="var(--contour)" />
      </g>
      <circle cx={34.9} cy={34.9} r={2.1} fill="var(--signal)" />
    </svg>
  )
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <FathomMark className="size-7" />
      <span className="font-serif text-[1.45rem] font-medium italic leading-none tracking-[-0.01em] [font-variation-settings:'opsz'_36]">
        fathom
      </span>
    </span>
  )
}

/** Deterministic pseudo-random in [0, 1), so server and client draw the same chart. */
function rand(seed: number) {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

function contourPath(cx: number, cy: number, base: number, seed: number) {
  const pts: string[] = []
  const n = 96
  const p1 = rand(seed) * Math.PI * 2
  const p2 = rand(seed + 1) * Math.PI * 2
  const p3 = rand(seed + 2) * Math.PI * 2
  for (let i = 0; i <= n; i++) {
    const t = (i / n) * Math.PI * 2
    const r =
      base *
      (1 + 0.09 * Math.sin(2 * t + p1) + 0.05 * Math.sin(3 * t + p2) + 0.025 * Math.sin(5 * t + p3))
    pts.push(`${(cx + r * Math.cos(t)).toFixed(1)},${(cy + r * 0.82 * Math.sin(t)).toFixed(1)}`)
  }
  return `M${pts.join('L')}Z`
}

/**
 * A patch of bathymetric chart: wobbly depth contours around a basin, with a few
 * soundings (depths in fathoms) set in italic as on a real chart. Decorative only.
 */
export function ContourField({ className }: { className?: string }) {
  const basin = { x: 380, y: 300 }
  // Contours sit closer together toward the deep end, as on a steep slope.
  const levels = [34, 62, 92, 126, 164, 206, 252, 302, 356]
  const soundings = [
    { x: 120, y: 90, d: 7 },
    { x: 610, y: 120, d: 9 },
    { x: 205, y: 470, d: 12 },
    { x: 560, y: 455, d: 14 },
    { x: 300, y: 210, d: 21 },
    { x: 470, y: 250, d: 26 },
    { x: 690, y: 330, d: 8 },
  ]
  return (
    <svg viewBox="0 0 760 600" className={cn('pointer-events-none select-none', className)} aria-hidden>
      <g fill="none" stroke="var(--contour)" strokeWidth={1}>
        {levels.map((r, i) => (
          <path
            key={r}
            d={contourPath(basin.x + i * 6, basin.y + i * 4, r, i * 3 + 1)}
            opacity={0.18 + (i % 3 === 0 ? 0.14 : 0)}
            strokeDasharray={i === 4 ? '5 5' : undefined}
          />
        ))}
      </g>
      <g
        fill="var(--ink-soft)"
        fontFamily="var(--font-serif)"
        fontStyle="italic"
        fontSize={15}
        opacity={0.55}
      >
        {soundings.map((s) => (
          <text key={`${s.x}-${s.y}`} x={s.x} y={s.y}>
            {s.d}
          </text>
        ))}
      </g>
      <circle cx={basin.x + 4} cy={basin.y + 3} r={5} fill="var(--signal)" />
      <text
        x={basin.x + 14}
        y={basin.y + 8}
        fill="var(--signal)"
        fontFamily="var(--font-serif)"
        fontStyle="italic"
        fontSize={17}
      >
        34
      </text>
    </svg>
  )
}
