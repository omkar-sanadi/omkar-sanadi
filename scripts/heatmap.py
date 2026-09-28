"""Scrape the public contributions calendar and render contrib-heatmap.svg.

No token, no deps: stdlib only. Run: python scripts/heatmap.py [username]
"""
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else "WIZ4RD-OM24"
OUT = Path(__file__).resolve().parent.parent / "contrib-heatmap.svg"
COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
CELL, GAP, LEFT, TOP = 12, 3, 36, 40


def fetch(user):
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions",
                                 headers={"User-Agent": "profile-readme"})
    return urllib.request.urlopen(req, timeout=30).read().decode()


def parse(html):
    days = {}  # id -> [date, level]
    for td in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", html):
        d, i, lv = (re.search(p, td) for p in (r'data-date="([\d-]+)"', r'id="([^"]+)"', r'data-level="(\d)"'))
        if d and i and lv:
            days[i[1]] = [date.fromisoformat(d[1]), int(lv[1]), 0]
    for tid, text in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)', html):
        m = re.match(r"([\d,]+) contribution", text.strip())
        if tid in days and m:
            days[tid][2] = int(m[1].replace(",", ""))
    return sorted(days.values())


def streaks(days):
    best = cur = 0
    for _, _, n in days:
        cur = cur + 1 if n else 0
        best = max(best, cur)
    # current streak: today may still be empty, so don't let it break the run
    run = days[:-1] if days and not days[-1][2] else days
    now = 0
    for _, _, n in reversed(run):
        if not n:
            break
        now += 1
    return now, best


def render(days):
    start = days[0][0]
    offset = (start.weekday() + 1) % 7  # GitHub weeks start on Sunday
    weeks = (len(days) + offset + 6) // 7
    width = LEFT + weeks * (CELL + GAP) + 10
    height = TOP + 7 * (CELL + GAP) + 50
    total = sum(n for *_, n in days)
    now, best = streaks(days)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
           "<style>.c{opacity:0;animation:in .4s ease-out forwards}"
           "@keyframes in{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}"
           ".t{fill:#8b949e;font-size:11px}</style>",
           f'<rect width="{width}" height="{height}" rx="10" fill="#0d1117"/>']

    last_month = None
    for idx, (d, lv, n) in enumerate(days):
        w, dow = divmod(idx + offset, 7)
        x, y = LEFT + w * (CELL + GAP), TOP + dow * (CELL + GAP)
        if d.day <= 7 and d.month != last_month and dow == 0:
            out.append(f'<text class="t" x="{x}" y="{TOP - 10}">{d.strftime("%b")}</text>')
            last_month = d.month
        delay = (w + dow) * 0.018  # diagonal wipe
        out.append(f'<rect class="c" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{COLORS[lv]}">'
                   f"<title>{n} on {d.isoformat()}</title></rect>")
    for dow, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text class="t" x="6" y="{TOP + dow * (CELL + GAP) + 10}">{label}</text>')

    fy = TOP + 7 * (CELL + GAP) + 26
    out.append(f'<text x="{LEFT}" y="{fy}" font-size="12" fill="#c9d1d9">'
               f'<tspan fill="#39d353">{total:,}</tspan> contributions in the last year  ·  '
               f'current streak <tspan fill="#39d353">{now}d</tspan>  ·  longest <tspan fill="#39d353">{best}d</tspan></text>')
    lx = width - 10 - len(COLORS) * (CELL + GAP) - 70
    out.append(f'<text class="t" x="{lx}" y="{fy}">Less</text>')
    for i, c in enumerate(COLORS):
        out.append(f'<rect x="{lx + 30 + i * (CELL + GAP)}" y="{fy - 10}" width="{CELL}" height="{CELL}" rx="2.5" fill="{c}"/>')
    out.append(f'<text class="t" x="{lx + 34 + len(COLORS) * (CELL + GAP)}" y="{fy}">More</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    days = parse(fetch(USER))
    assert len(days) > 300, f"only parsed {len(days)} days; GitHub markup may have changed"
    OUT.write_text(render(days), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(days)} days, {sum(n for *_, n in days)} contributions")
