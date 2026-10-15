#!/usr/bin/env python3
"""Check that the launch film starts on the AIA mark the handoff forms.

The front door's handoff (apps/web/src/lib/dot-field.ts, markTargets) forms the
mark on the ideal lattice -- lattice x, y in {8, 14, 20, 26, 32}, 15 film px per
unit from (20, 20) at the film's centre, the A's points r 34.5, the rest r 13.5 --
and the film takes over on its first frame. If that frame is not the same mark,
the cut can be seen. This reads frame 0 of a film (1920 x 1080), finds its 25
dots, prints each beside its lattice point, and fails if any centre is more than
0.5 film px or any radius more than 0.5 px off.

    python tools/film_frame0.py apps/web/public/skin/brand/aia-liftoff.webm

Stdlib only; needs ffmpeg on PATH. A dot's centre and radius come from its
anti-aliased coverage (each pixel weighted by how far it is from the ground to
the dot's own colour), so they are sub-pixel.
"""

from __future__ import annotations

import math
import subprocess
import sys

W, H = 1920, 1080
GROUND = (17, 16, 21)  # brand-stage, the film's ground
LATTICE = (8, 14, 20, 26, 32)
PITCH = 15
BOLD = {
    (20, 8),
    (14, 14),
    (26, 14),
    (14, 20),
    (20, 20),
    (26, 20),
    (8, 26),
    (32, 26),
    (8, 32),
    (32, 32),
}
TOLERANCE = 0.5


def frame0(path: str) -> bytes:
    command = ["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1"]
    raw = subprocess.run(
        [*command, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True,
        capture_output=True,
    ).stdout
    if len(raw) != W * H * 3:
        raise SystemExit(f"expected a {W}x{H} frame, got {len(raw)} bytes")
    return raw


def blobs(raw: bytes) -> list[tuple[float, float, float]]:
    def px(x: int, y: int) -> tuple[int, int, int]:
        i = (y * W + x) * 3
        return raw[i], raw[i + 1], raw[i + 2]

    def lit(x: int, y: int) -> bool:
        return sum(px(x, y)) - sum(GROUND) >= 40

    seen: set[tuple[int, int]] = set()
    out = []
    for y in range(200, 880):
        for x in range(600, 1320):
            if (x, y) in seen or not lit(x, y):
                continue
            stack, pts = [(x, y)], []
            seen.add((x, y))
            while stack:
                a, b = stack.pop()
                pts.append((a, b))
                for q in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if q not in seen and lit(*q):
                        seen.add(q)
                        stack.append(q)
            if len(pts) < 50:  # compression noise, not a dot
                continue
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            core = px((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)
            k = max(range(3), key=lambda c: abs(core[c] - GROUND[c]))
            den = core[k] - GROUND[k]
            s = sx = sy = 0.0
            for yy in range(min(ys) - 3, max(ys) + 4):
                for xx in range(min(xs) - 3, max(xs) + 4):
                    w = max(0.0, min(1.0, (px(xx, yy)[k] - GROUND[k]) / den))
                    s, sx, sy = s + w, sx + w * (xx + 0.5), sy + w * (yy + 0.5)
            out.append((sx / s, sy / s, math.sqrt(s / math.pi)))
    return out


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    found = blobs(frame0(sys.argv[1]))
    if len(found) != 25:
        raise SystemExit(f"expected the mark's 25 dots in frame 0, found {len(found)}")
    worst = 0.0
    for gy in LATTICE:
        for gx in LATTICE:
            lx, ly = W / 2 + (gx - 20) * PITCH, H / 2 + (gy - 20) * PITCH
            lr = 34.5 if (gx, gy) in BOLD else 13.5
            x, y, r = min(found, key=lambda b: math.hypot(b[0] - lx, b[1] - ly))
            off = max(math.hypot(x - lx, y - ly), abs(r - lr))
            worst = max(worst, off)
            film = f"film {x:8.2f} {y:7.2f} r {r:5.2f}"
            print(f"({gx:2}, {gy:2})  {film}   lattice {lx:6.0f} {ly:4.0f} r {lr:4}")
    print(f"largest offset {worst:.2f} px (tolerance {TOLERANCE})")
    if worst > TOLERANCE:
        raise SystemExit("frame 0 is not the lattice mark: the cut would be seen")


if __name__ == "__main__":
    main()
