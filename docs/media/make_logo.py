"""CVCOPs logo, from first principles.

The product makes two layers: flow (where each pixel moved) and valid (whether to trust that). The mark is one
image tile holding a small field of arrows, with one cell replaced by a dot: the pixel it is not sure about.
Everything is outlines, so the SVG needs no font.
"""
import math
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

INK, PAPER, VERM, QUIET = "#2E2B28", "#FAF8F4", "#C8321A", "#5B554F"
OUT = Path(__file__).parent / "out"; OUT.mkdir(exist_ok=True)


def mark(x=0.0, y=0.0, size=256.0, tile=INK, arrow=PAPER, dot=VERM, n=3):
    """The tile, as SVG elements, placed at (x, y) with the given size."""
    s = size / 256.0
    out = [f'<rect x="{x + 12 * s:.2f}" y="{y + 12 * s:.2f}" width="{232 * s:.2f}" height="{232 * s:.2f}" rx="{50 * s:.2f}" fill="{tile}"/>']
    ang = math.radians(-28)                      # every arrow leans up and to the right
    ux, uy = math.cos(ang), math.sin(ang)
    # n = 3 is the full mark; n = 2 is the small one, for 32 px and below
    half, head, sw, step, first, rad, doubt = (21.0, 15.0, 11.0, 60, 68, 15, (1, 2)) if n == 3 else (30.0, 22.0, 17.0, 88, 84, 23, (1, 1))
    for r in range(n):
        for c in range(n):
            cx, cy = first + c * step, first + r * step
            if (r, c) == doubt:                  # the one pixel to doubt
                out.append(f'<circle cx="{x + cx * s:.2f}" cy="{y + cy * s:.2f}" r="{rad * s:.2f}" fill="{dot}"/>')
                continue
            x0, y0, x1, y1 = cx - ux * half, cy - uy * half, cx + ux * half, cy + uy * half
            pts = []
            for da in (math.radians(150), math.radians(-150)):
                a = ang + da
                pts.append((x1 + math.cos(a) * head, y1 + math.sin(a) * head))
            d = (f'M{x + x0 * s:.2f} {y + y0 * s:.2f}L{x + x1 * s:.2f} {y + y1 * s:.2f}'
                 f'M{x + pts[0][0] * s:.2f} {y + pts[0][1] * s:.2f}L{x + x1 * s:.2f} {y + y1 * s:.2f}L{x + pts[1][0] * s:.2f} {y + pts[1][1] * s:.2f}')
            out.append(f'<path d="{d}" fill="none" stroke="{arrow}" stroke-width="{sw * s:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
    return "\n  ".join(out)


def outlines(text, font_path, axes, px, x, baseline, fill, tracking=0.0):
    """Text as one SVG path, in a static instance of a variable font. Returns (svg, advance width in px)."""
    f = instancer.instantiateVariableFont(TTFont(font_path), axes)
    gs, cmap, upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
    k = px / upm
    pen = SVGPathPen(gs)
    adv = 0.0
    for ch in text:
        g = cmap[ord(ch)]
        gs[g].draw(TransformPen(pen, (k, 0, 0, -k, x + adv, baseline)))
        adv += gs[g].width * k + tracking
    return f'<path d="{pen.getCommands()}" fill="{fill}"/>', adv - tracking


FONTS = Path(__file__).parent / "fonts"   # put Fraunces.ttf, Archivo.ttf and JetBrainsMono.ttf here
FR = str(FONTS / "Fraunces.ttf")
AR = str(FONTS / "Archivo.ttf")
FR_AX = {"wght": 600, "opsz": 72, "SOFT": 0, "WONK": 0}


def svg(w, h, body, bg=None):
    r = f'<rect width="{w}" height="{h}" fill="{bg}"/>\n  ' if bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="CVCOPs">\n  {r}{body}\n</svg>\n'


def main():
    # 1. the mark alone
    (OUT / "logo-mark.svg").write_text(svg(256, 256, mark()))
    (OUT / "logo-mark-dark.svg").write_text(svg(256, 256, mark(tile=PAPER, arrow=INK)))
    (OUT / "logo-mark-small.svg").write_text(svg(256, 256, mark(n=2)))
    # 2. mark plus wordmark, for light and dark pages
    for name, ink, tile, arrow in (("logo-light.svg", INK, INK, PAPER), ("logo-dark.svg", PAPER, PAPER, INK)):
        word, wd = outlines("CVCOPs", FR, FR_AX, 150, 236, 166, ink, tracking=-1.5)
        (OUT / name).write_text(svg(int(236 + wd + 24), 220, mark(0, 2, 216, tile, arrow) + "\n  " + word))
    # 3. the social card, 1280 by 640
    word, wd = outlines("CVCOPs", FR, FR_AX, 170, 420, 298, INK, tracking=-2)
    tag, _ = outlines("Copernicus learns to see motion,", AR, {"wght": 450, "wdth": 100}, 44, 124, 458, QUIET)
    tag2, _ = outlines("and to say when it is not sure.", AR, {"wght": 450, "wdth": 100}, 44, 124, 516, QUIET)
    foot, _ = outlines("OPTICAL FLOW FOR HOUDINI 22 COPERNICUS, ON OPENCV", str(FONTS / "JetBrainsMono.ttf"), {"wght": 400}, 20, 124, 590, QUIET, tracking=2.4)
    body = mark(110, 118, 260) + "\n  " + word.replace("", "") + "\n  " + tag + "\n  " + tag2 + "\n  " + foot
    (OUT / "social-card.svg").write_text(svg(1280, 640, body, bg=PAPER))
    print("written:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
