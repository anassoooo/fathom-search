"""Generate Fathom's app icons from one geometry: nested depth contours drawn tighter
toward a single sounding (the deepest point, i.e. the result found).

The rings are eccentric circles, as on a nautical chart where contours bunch up on the
steep side of a basin; the outer ring doubles as a search lens. Chart magenta marks the
sounding, the way charts use magenta for the marks that matter.

Outputs (Next.js app-router conventions + a web manifest):
  web/src/app/icon.svg         vector favicon for modern browsers
  web/src/app/favicon.ico      16/32/48 px for legacy browsers and Windows
  web/src/app/apple-icon.png   180 px, full-bleed (iOS applies its own mask)
  web/public/icon-192.png, icon-512.png, icon-maskable-512.png  for the manifest
  web/public/og-mark.png       512 px mark on chart white, for social previews

Run with the backend venv (needs Pillow):
  cd backend && uv run --no-sync python ../scripts/make_icons.py [--preview out.png]
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
NAVY = (0x0F, 0x2A, 0x3D)  # deep water: the tile
SHOAL = (0xDC, 0xEB, 0xF1)  # outer contour
CONTOUR = (0x8F, 0xC1, 0xDD)  # inner contours, one step deeper
MAGENTA = (0xE0, 0x3A, 0x98)  # the sounding; brighter than the UI magenta to hold on navy
PAPER = (0xF5, 0xF8, 0xF7)

# Geometry on a 64-unit grid (the SVG viewBox). Each ring is (cx, cy, r, colour).
RADIUS = 14.0
STROKE = 3.2
RINGS = [(30.0, 30.0, 19.5, SHOAL), (32.5, 32.5, 11.5, CONTOUR), (34.5, 34.5, 5.0, CONTOUR)]
SOUNDING = (34.9, 34.9, 2.1)


def _hex(c: tuple[int, int, int]) -> str:
    return f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"


SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <title>Fathom</title>
  <rect width="64" height="64" rx="{RADIUS:g}" fill="{_hex(NAVY)}"/>
  <g fill="none" stroke-width="{STROKE:g}">
{chr(10).join(f'    <circle cx="{x:g}" cy="{y:g}" r="{r:g}" stroke="{_hex(c)}"/>' for x, y, r, c in RINGS)}
  </g>
  <circle cx="{SOUNDING[0]:g}" cy="{SOUNDING[1]:g}" r="{SOUNDING[2]:g}" fill="{_hex(MAGENTA)}"/>
</svg>
"""


def render(size: int, *, rounded: bool = True, tile: bool = True, rings: int = 3,
           weight: float = 1.0, glyph_scale: float = 1.0, ss: int = 16) -> Image.Image:
    """Render at `size` px. `rings` drops the innermost contours at tiny sizes, `weight`
    thickens strokes, `glyph_scale` shrinks the glyph toward the centre (maskable safe
    zone). `tile=False` draws the mark in navy on chart white instead."""
    big = size * ss
    k = glyph_scale * big / 64
    off = big * (1 - glyph_scale) / 2
    bg = (*NAVY, 255) if tile else (*PAPER, 255)
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle((0, 0, big - 1, big - 1), radius=RADIUS * big / 64, fill=bg)
    else:
        d.rectangle((0, 0, big, big), fill=bg)

    w = STROKE * weight
    for i, (x, y, r, c) in enumerate(RINGS[:rings]):
        colour = c if tile else (NAVY if i == 0 else (0x3A, 0x7C, 0xA5))
        ro = (r + w / 2) * k
        cx, cy = x * k + off, y * k + off
        d.ellipse((cx - ro, cy - ro, cx + ro, cy + ro), outline=(*colour, 255), width=round(w * k))
    x, y, r = SOUNDING
    r *= weight ** 0.5
    cx, cy = x * k + off, y * k + off
    d.ellipse((cx - r * k, cy - r * k, cx + r * k, cy + r * k), fill=(*MAGENTA, 255))
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=Path, help="also write a contact sheet PNG here")
    args = ap.parse_args()

    app, public = ROOT / "web/src/app", ROOT / "web/public"
    (app / "icon.svg").write_text(SVG, encoding="utf-8")

    # 16 px: two rings only, heavier strokes, so the mark stays legible.
    ico = {16: render(16, rings=2, weight=1.35), 32: render(32, weight=1.1), 48: render(48)}
    ico[48].save(app / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                 append_images=[ico[16], ico[32]])
    render(180, rounded=False).convert("RGB").save(app / "apple-icon.png")
    render(192).save(public / "icon-192.png")
    render(512).save(public / "icon-512.png")
    # Maskable: full-bleed tile, glyph inside the 80% safe zone.
    render(512, rounded=False, glyph_scale=0.8).save(public / "icon-maskable-512.png")
    render(512, rounded=False, tile=False, glyph_scale=0.7).convert("RGB").save(public / "og-mark.png")

    if args.preview:
        sizes = [16, 24, 32, 48, 64, 128]
        pad, scale = 24, 4  # tiny sizes are also shown magnified 4x with nearest-neighbour
        w = sum(s * scale for s in sizes) + pad * (len(sizes) + 1) + 2 * (256 + pad)
        h = 512 + 2 * pad
        sheet = Image.new("RGBA", (w, h), (*PAPER, 255))
        x = pad
        for sz in sizes:
            im = render(sz, rings=2 if sz < 24 else 3, weight=1.35 if sz < 24 else 1.0)
            sheet.alpha_composite(im.resize((sz * scale, sz * scale), Image.Resampling.NEAREST), (x, pad))
            x += sz * scale + pad
        sheet.alpha_composite(render(256), (x, pad))
        sheet.alpha_composite(render(256, tile=False, rounded=False), (x + 256 + pad, pad))
        sheet.save(args.preview)
    print("icons written")


if __name__ == "__main__":
    main()
