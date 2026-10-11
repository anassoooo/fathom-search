"""Generate Fathom's app icons from one geometry: a lens with a wave inside (search + depth).

Outputs (Next.js app-router conventions + a web manifest):
  web/src/app/icon.svg         vector favicon for modern browsers
  web/src/app/favicon.ico      16/32/48 px for legacy browsers and Windows
  web/src/app/apple-icon.png   180 px, full-bleed (iOS applies its own mask)
  web/public/icon-192.png, icon-512.png, icon-maskable-512.png  for the manifest

Run with the backend venv (needs Pillow + numpy):
  cd backend && uv run --no-sync python ../scripts/make_icons.py [--preview out.png]
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
VIOLET = (0x5B, 0x2B, 0xB5)  # sampled from the existing logo (#6030B0 family)
ORANGE = (0xF0, 0x74, 0x23)  # sampled from the existing logo (#F07020 family)
# Straight violet->orange interpolation passes through a muddy mauve; a vivid magenta
# midpoint keeps the tile saturated end to end, like the glowing logo.
MAGENTA, MID = (0xC0, 0x34, 0x8C), 0.55
WHITE = (255, 255, 255, 255)

# Geometry on a 64-unit grid (the SVG viewBox).
LENS_C, LENS_R, LENS_W = (27.0, 27.0), 14.0, 6.0
HANDLE = ((37.5, 37.5), (50.0, 50.0))
HANDLE_W = 7.0
WAVE_Y, WAVE_X0, WAVE_X1, WAVE_AMP, WAVE_W = 29.0, 18.5, 35.5, 4.0, 3.2
RADIUS = 14.0

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <title>Fathom</title>
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#{VIOLET[0]:02X}{VIOLET[1]:02X}{VIOLET[2]:02X}"/>
      <stop offset="{MID:g}" stop-color="#{MAGENTA[0]:02X}{MAGENTA[1]:02X}{MAGENTA[2]:02X}"/>
      <stop offset="1" stop-color="#{ORANGE[0]:02X}{ORANGE[1]:02X}{ORANGE[2]:02X}"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="{RADIUS:g}" fill="url(#g)"/>
  <g fill="none" stroke="#fff" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="{LENS_C[0]:g}" cy="{LENS_C[1]:g}" r="{LENS_R:g}" stroke-width="{LENS_W:g}"/>
    <path d="M{HANDLE[0][0]:g} {HANDLE[0][1]:g}L{HANDLE[1][0]:g} {HANDLE[1][1]:g}" stroke-width="{HANDLE_W:g}"/>
    <path d="M{WAVE_X0:g} {WAVE_Y:g}c3 -{WAVE_AMP:g} 5.5 -{WAVE_AMP:g} 8.5 0s5.5 {WAVE_AMP:g} 8.5 0" stroke-width="{WAVE_W:g}"/>
  </g>
</svg>
"""


def _gradient(size: int) -> Image.Image:
    """Diagonal violet -> orange, top-left to bottom-right (same as the SVG)."""
    t = np.add.outer(np.arange(size), np.arange(size)) / (2 * (size - 1))
    lo, hi = t / MID, (t - MID) / (1 - MID)  # position within each of the two segments
    rgb = np.stack(
        [
            np.where(t < MID, (1 - lo) * v + lo * m, (1 - hi) * m + hi * o)
            for v, m, o in zip(VIOLET, MAGENTA, ORANGE, strict=True)
        ],
        axis=-1,
    )
    return Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")


def _thick_polyline(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], width: float) -> None:
    draw.line(pts, fill=WHITE, width=round(width))
    r = width / 2
    for x, y in pts:  # round joins and caps
        draw.ellipse((x - r, y - r, x + r, y + r), fill=WHITE)


def _wave_points(s: float) -> list[tuple[float, float]]:
    """The SVG's two cubic halves, sampled densely."""
    def cubic(p0, p1, p2, p3, n=40):  # type: ignore[no-untyped-def]
        out = []
        for i in range(n + 1):
            u = i / n
            x = (1 - u) ** 3 * p0[0] + 3 * (1 - u) ** 2 * u * p1[0] + 3 * (1 - u) * u**2 * p2[0] + u**3 * p3[0]
            y = (1 - u) ** 3 * p0[1] + 3 * (1 - u) ** 2 * u * p1[1] + 3 * (1 - u) * u**2 * p2[1] + u**3 * p3[1]
            out.append((x * s, y * s))
        return out

    x0, y, a = WAVE_X0, WAVE_Y, WAVE_AMP
    first = cubic((x0, y), (x0 + 3, y - a), (x0 + 5.5, y - a), (x0 + 8.5, y))
    second = cubic((x0 + 8.5, y), (x0 + 11.5, y + a), (x0 + 14, y + a), (x0 + 17, y))
    return first + second[1:]


def render(size: int, *, rounded: bool = True, wave: bool = True, weight: float = 1.0,
           glyph_scale: float = 1.0, ss: int = 16) -> Image.Image:
    """Render at `size` px. `weight` thickens strokes for tiny sizes; `glyph_scale`
    shrinks the glyph toward the centre (maskable safe zone)."""
    big = size * ss
    s = big / 64
    img = _gradient(big)
    if rounded:
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=RADIUS * s, fill=255)
        img.putalpha(mask)

    glyph = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(glyph)
    cx, cy = LENS_C[0] * s, LENS_C[1] * s
    r_out = (LENS_R + LENS_W * weight / 2) * s
    d.ellipse((cx - r_out, cy - r_out, cx + r_out, cy + r_out), outline=WHITE,
              width=round(LENS_W * weight * s))
    (hx0, hy0), (hx1, hy1) = HANDLE
    _thick_polyline(d, [(hx0 * s, hy0 * s), (hx1 * s, hy1 * s)], HANDLE_W * weight * s)
    if wave:
        _thick_polyline(d, _wave_points(s), WAVE_W * weight * s)
    if glyph_scale != 1.0:
        g = round(big * glyph_scale)
        small = glyph.resize((g, g), Image.Resampling.LANCZOS)
        glyph = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        glyph.paste(small, ((big - g) // 2, (big - g) // 2))
    img.alpha_composite(glyph)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=Path, help="also write a contact sheet PNG here")
    args = ap.parse_args()

    app, public = ROOT / "web/src/app", ROOT / "web/public"
    (app / "icon.svg").write_text(SVG, encoding="utf-8")

    # 16 px: no wave (it would blur), heavier strokes. 32/48 px: full mark.
    ico = {16: render(16, wave=False, weight=1.15), 32: render(32), 48: render(48)}
    ico[48].save(app / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                 append_images=[ico[16], ico[32]])
    render(180, rounded=False).convert("RGB").save(app / "apple-icon.png")
    render(192).save(public / "icon-192.png")
    render(512).save(public / "icon-512.png")
    # Maskable: full-bleed tile, glyph inside the 80% safe zone.
    render(512, rounded=False, glyph_scale=0.8).save(public / "icon-maskable-512.png")

    if args.preview:
        sizes = [16, 24, 32, 48, 64, 128]
        pad, scale = 24, 4  # tiny sizes are also shown magnified 4x with nearest-neighbour
        w = sum(s * scale for s in sizes) + pad * (len(sizes) + 1) + 512 + pad
        h = 512 + 2 * pad
        sheet = Image.new("RGBA", (w, h), (246, 245, 242, 255))
        x = pad
        for sz in sizes:
            im = render(sz, wave=sz >= 24, weight=1.15 if sz < 24 else 1.0)
            sheet.alpha_composite(im.resize((sz * scale, sz * scale), Image.Resampling.NEAREST), (x, pad))
            x += sz * scale + pad
        sheet.alpha_composite(render(512), (x, pad))
        sheet.save(args.preview)
    print("icons written:", ", ".join(sorted(p.name for p in [*app.glob("icon.svg"), app / "favicon.ico", app / "apple-icon.png", *public.glob("icon-*.png")])))


if __name__ == "__main__":
    main()
