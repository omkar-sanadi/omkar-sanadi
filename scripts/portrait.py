"""Turn a headshot into ascii-portrait.svg (coloured ASCII, rows wipe in once).

Local-only (needs Pillow). Run: python scripts/portrait.py photo.png [x0 y0 x1 y1]
The crop box defaults to head-and-shoulders for the original 880x1178 photo.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps

OUT = Path(__file__).resolve().parent.parent / "ascii-portrait.svg"
RAMP = ".`:-=+*cs#%@"  # light -> dense; background cells are blank
W, H, BAR, PAD = 370, 400, 30, 14
COLS = 100
CHAR_W = (W - 2 * PAD) / COLS
LINE_H = CHAR_W * 1.8  # monospace glyphs are ~1.8x taller than wide


def background_mask(im):
    """Plain backdrop -> 255, subject -> 0. Only regions touching the border count."""
    px = im.load()
    cand = Image.new("L", im.size, 0)
    cp = cand.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y][:3]
            if g > r + 8 and g > b + 8 and g > 90:  # the sage-green backdrop
                cp[x, y] = 128
    for x in range(0, im.width, 8):  # flood from top edge + upper sides
        for seed in ((x, 0),):
            if cp[seed] == 128:
                ImageDraw.floodfill(cand, seed, 255)
    for y in range(0, im.height // 2, 8):
        for seed in ((0, y), (im.width - 1, y)):
            if cp[seed] == 128:
                ImageDraw.floodfill(cand, seed, 255)
    return cand.point(lambda v: 255 if v == 255 else 0)


def lift(rgb, floor=95):
    """Brighten dark colours so hair/suit stay visible on a dark card."""
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    if lum >= floor:
        return rgb
    k = floor / max(lum, 1)
    return tuple(min(255, int(c * k + (floor - lum) * 0.35)) for c in rgb)


def main():
    src = Image.open(sys.argv[1]).convert("RGB")
    box = tuple(map(int, sys.argv[2:6])) if len(sys.argv) >= 6 else (60, 70, 820, 790)
    im = src.crop(box)
    rows = round((H - BAR - 2 * PAD) / LINE_H)
    grid = (COLS, rows)

    fgimg = ImageOps.invert(background_mask(im)).resize(grid, Image.BOX).point(lambda v: 255 if v > 127 else 0)
    fg = fgimg.load()
    col = im.resize(grid, Image.BOX)
    lum = ImageOps.equalize(col.convert("L").filter(ImageFilter.UnsharpMask(2, 160, 2)), mask=fgimg).load()  # full ramp across the subject only
    cp, colors = col.load(), {}  # hex -> class index, filled as cells use them

    def cls_of(x, y):
        hx = "#%02x%02x%02x" % tuple(min(255, c // 20 * 20 + 10) for c in lift(cp[x, y]))
        return colors.setdefault(hx, len(colors))

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="{CHAR_W / 0.6:.2f}">',
           "STYLE",
           f'<rect width="{W}" height="{H}" rx="10" fill="#0d1117" stroke="#30363d"/>',
           f'<rect width="{W}" height="{BAR}" rx="10" fill="#161b22"/><rect y="20" width="{W}" height="10" fill="#161b22"/>',
           '<circle cx="18" cy="15" r="5.5" fill="#ff5f56"/><circle cx="36" cy="15" r="5.5" fill="#ffbd2e"/><circle cx="54" cy="15" r="5.5" fill="#27c93f"/>',
           f'<text x="{W / 2}" y="19" text-anchor="middle" fill="#8b949e" font-size="12">portrait.txt</text>',
           "<defs>"]
    top = BAR + PAD
    for y in range(rows):
        out.append(f'<clipPath id="r{y}"><rect x="{PAD}" y="{top + y * LINE_H:.1f}" width="0" height="{LINE_H + 1:.1f}">'
                   f'<animate attributeName="width" from="0" to="{W - 2 * PAD}" begin="{0.2 + y * 0.035:.3f}s" dur="0.5s" fill="freeze"/></rect></clipPath>')
    out.append("</defs>")

    for y in range(rows):
        runs = []  # [class, text]; blanks join whatever run they follow
        for x in range(COLS):
            fgc = fg[x, y] > 127
            cls = cls_of(x, y) if fgc else None
            ch = RAMP[min(len(RAMP) - 1, (255 - lum[x, y]) * len(RAMP) // 256)] if fgc else " "
            if runs and (cls is None or cls == runs[-1][0]):
                runs[-1][1] += ch
            else:
                runs.append([cls, ch])
        if not any(s.strip() for _, s in runs):
            continue
        spans = "".join(f'<tspan class="p{c}">{s}</tspan>' if c is not None and s.strip() else s for c, s in runs)
        out.append(f'<text clip-path="url(#r{y})" x="{PAD}" y="{top + (y + 1) * LINE_H - 2:.1f}" xml:space="preserve" '
                   f'textLength="{W - 2 * PAD}" lengthAdjust="spacing">{spans}</text>')
    out.append("</svg>")
    out[1] = "<style>" + "".join(f".p{i}{{fill:{h}}}" for h, i in colors.items()) + "</style>"
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT.name}: {COLS}x{rows} chars, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
