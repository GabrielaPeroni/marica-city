"""Generates the printed illustrations: uv run python scripts/generate_deco.py templates/includes/deco"""

import math
import random
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def P(pts):
    return " ".join(f"{f(x)},{f(y)}" for x, y in pts)


def smooth(pts):
    """Open Catmull-Rom curve through points as cubic beziers (no leading M)."""
    n = len(pts)
    d = f"{f(pts[0][0])},{f(pts[0][1])}"
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{f(c1[0])},{f(c1[1])} {f(c2[0])},{f(c2[1])} {f(p2[0])},{f(p2[1])}"
    return d


def svg(name, vb, body, extra=""):
    (OUT / f"{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" '
        f'class="deco {{{{ deco_class }}}}" fill="currentColor" aria-hidden="true" '
        f'focusable="false"{extra}>{body}</svg>\n',
        encoding="utf-8",
    )


def bez(p0, p1, p2, t):
    a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
    return (a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1])


def frond(seed, curve, name, n=26, spread=58, length=150):
    random.seed(seed)
    p0, p1, p2 = (20, 380), curve, (360, 40)
    shapes = []
    left, right = [], []
    for i in range(41):
        t = i / 40
        x, y = bez(p0, p1, p2, t)
        x2, y2 = bez(p0, p1, p2, min(t + 0.01, 1))
        ang = math.atan2(y2 - y, x2 - x)
        w = 5 * (1 - t) + 0.8
        left.append(
            (x + math.cos(ang + math.pi / 2) * w, y + math.sin(ang + math.pi / 2) * w)
        )
        right.append(
            (x + math.cos(ang - math.pi / 2) * w, y + math.sin(ang - math.pi / 2) * w)
        )
    shapes.append(f'<path d="M{P(left)} L{P(right[::-1])}Z"/>')
    for i in range(n):
        t = 0.1 + 0.88 * i / (n - 1)
        x, y = bez(p0, p1, p2, t)
        x2, y2 = bez(p0, p1, p2, min(t + 0.01, 1))
        ang = math.atan2(y2 - y, x2 - x)
        for side in (1, -1):
            L = (
                length
                * (math.sin(math.pi * min(t * 1.05, 1)) ** 0.55)
                * random.uniform(0.85, 1.08)
                * (1 - 0.55 * t)
            )
            if L < 8:
                continue
            a = ang + side * math.radians(spread + random.uniform(-6, 6))
            droop = side * random.uniform(0.15, 0.3)
            tip = (x + math.cos(a) * L, y + math.sin(a) * L)
            mid = (
                x + math.cos(a + droop) * L * 0.55,
                y + math.sin(a + droop) * L * 0.55,
            )
            w = max(L * 0.09, 3)
            na = a + math.pi / 2
            b1 = (x + math.cos(na) * w, y + math.sin(na) * w)
            b2 = (x - math.cos(na) * w, y - math.sin(na) * w)
            m1 = (mid[0] + math.cos(na) * w * 1.1, mid[1] + math.sin(na) * w * 1.1)
            m2 = (mid[0] - math.cos(na) * w * 1.1, mid[1] - math.sin(na) * w * 1.1)
            shapes.append(
                f'<path d="M{f(b1[0])},{f(b1[1])} Q{f(m1[0])},{f(m1[1])} {f(tip[0])},{f(tip[1])} '
                f'Q{f(m2[0])},{f(m2[1])} {f(b2[0])},{f(b2[1])}Z"/>'
            )
    svg(name, "0 0 420 420", "".join(shapes))


def monstera():
    pts = []
    n = 240
    slits = [0.11, 0.19, 0.28, 0.38, 0.62, 0.72, 0.81, 0.89]
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = -(
            13 * math.cos(t)
            - 5 * math.cos(2 * t)
            - 2 * math.cos(3 * t)
            - math.cos(4 * t)
        )
        u, r = i / n, 1.0
        for s in slits:
            d = abs(u - s)
            if d < 0.013:
                r = min(r, 0.45 + d / 0.013 * 0.55)
        pts.append((200 + x * 11 * r, 200 + y * 11 * r))
    outline = "M" + " L".join(f"{f(x)},{f(y)}" for x, y in pts) + "Z"
    holes = "".join(
        f'<ellipse cx="{hx}" cy="{hy}" rx="{rx}" ry="{ry}" transform="rotate({rot} {hx} {hy})"/>'
        for hx, hy, rx, ry, rot in [
            (150, 200, 9, 16, 30),
            (250, 200, 9, 16, -30),
            (145, 255, 7, 13, 45),
            (255, 255, 7, 13, -45),
            (175, 310, 6, 10, 55),
            (225, 310, 6, 10, -55),
        ]
    )
    midrib = '<path d="M198,150 Q201,260 199,378 L202,378 Q204,260 202,150Z"/>'
    body = (
        '<defs><mask id="monstera-cut"><rect width="400" height="420" fill="white"/>'
        f'<g fill="black">{holes}{midrib}</g></mask></defs>'
        f'<path d="{outline}" mask="url(#monstera-cut)"/>'
        '<path d="M197,152 Q192,95 168,40 L175,37 Q200,92 204,152Z"/>'
    )
    svg("monstera", "0 0 400 420", body)


def aroeira():
    """Restinga branch (aroeira) with pink-pepper berries in --deco-accent."""
    random.seed(11)
    p0, p1, p2 = (30, 400), (120, 180), (330, 50)
    body = ""
    left, right = [], []
    for i in range(31):
        t = i / 30
        x, y = bez(p0, p1, p2, t)
        w = 3.2 * (1 - t) + 0.8
        left.append((x - w, y))
        right.append((x + w, y))
    body += f'<path d="M{P(left)} L{P(right[::-1])}Z"/>'
    berries = ""
    for i in range(7):
        t = 0.14 + i * 0.12
        x, y = bez(p0, p1, p2, t)
        x2, y2 = bez(p0, p1, p2, t + 0.01)
        ang = math.degrees(math.atan2(y2 - y, x2 - x))
        for side in (1, -1):
            L = 78 * (1 - 0.45 * t) * random.uniform(0.9, 1.1)
            a = ang + side * random.uniform(38, 52)
            cx = x + math.cos(math.radians(a)) * L / 2
            cy = y + math.sin(math.radians(a)) * L / 2
            body += (
                f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(L / 2)}" ry="{f(L / 4.6)}" '
                f'transform="rotate({f(a)} {f(cx)} {f(cy)})"/>'
            )
        if i in (1, 3, 5):
            bx, by = x + random.uniform(-6, 6), y + 18
            for _ in range(6):
                berries += (
                    f'<circle cx="{f(bx + random.uniform(-14, 14))}" '
                    f'cy="{f(by + random.uniform(-10, 14))}" r="{f(random.uniform(4.5, 6.5))}"/>'
                )
    body += f'<g style="fill: var(--deco-accent, currentColor)">{berries}</g>'
    svg("aroeira", "0 0 360 420", body)


def sun():
    random.seed(3)
    body = '<circle cx="100" cy="100" r="38"/>'
    for i in range(14):
        a = 2 * math.pi * i / 14 + random.uniform(-0.05, 0.05)
        r1, r2, w = 50, random.uniform(78, 92), 0.11
        pts = [
            (100 + math.cos(a - w) * r1, 100 + math.sin(a - w) * r1),
            (100 + math.cos(a) * r2, 100 + math.sin(a) * r2),
            (100 + math.cos(a + w) * r1, 100 + math.sin(a + w) * r1),
        ]
        body += f'<path d="M{P(pts)}Z"/>'
    svg("sun", "0 0 200 200", body)


def gulls():
    body = "".join(
        f'<path transform="translate({x} {y}) scale({s})" '
        'd="M0,10 Q14,-6 30,8 Q46,-6 60,10 Q46,2 30,16 Q14,2 0,10Z"/>'
        for x, y, s in [(30, 60, 1), (95, 30, 0.7), (140, 75, 0.55)]
    )
    svg("gulls", "0 0 180 110", body)


def wave():
    """Section edge: filled below an organic wave line, stretched to the width."""
    pts = [
        (
            i,
            34
            + 14 * math.sin(i / 1440 * math.pi * 2.3 + 0.6)
            + 7 * math.sin(i / 1440 * math.pi * 6.1),
        )
        for i in range(0, 1441, 40)
    ]
    svg(
        "wave",
        "0 0 1440 80",
        f'<path d="M{smooth(pts)} L1440,80 L0,80Z"/>',
        ' preserveAspectRatio="none"',
    )


def skyline():
    """Maricá hills with the Pedra do Elefante dome, for the footer's top edge."""
    pts = [
        (0, 120),
        (90, 104),
        (190, 90),
        (260, 92),
        (320, 66),
        (370, 42),
        (420, 30),
        (480, 26),
        (540, 34),
        (585, 58),
        (610, 84),
        (650, 98),
        (720, 84),
        (800, 96),
        (880, 74),
        (960, 58),
        (1010, 66),
        (1080, 92),
        (1160, 88),
        (1240, 102),
        (1330, 94),
        (1440, 108),
    ]
    svg(
        "skyline",
        "0 0 1440 160",
        f'<path d="M0,160 L{smooth(pts)} L1440,160Z"/>',
        ' preserveAspectRatio="none"',
    )


frond(1, (40, 120), "frond")
frond(4, (230, 330), "frond-low", n=22, spread=62, length=130)
monstera()
aroeira()
sun()
gulls()
wave()
skyline()
print("ok", sorted(p.name for p in OUT.iterdir()))
