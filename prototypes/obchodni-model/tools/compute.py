"""Indicator Sociomapa for the Velis case: two maps (options, suppliers), the cloud workbook's method.

Fixed method: score 1-10 by rule, certainty, category mean, weighted total (height),
z-score per category, profile correlation -> similarity (r+1)*5, scenarios over weights and
certainty, co-movement of totals. Everything study-specific is in the two SPECs.
"""
import json, math, statistics as st, sys
import numpy as np

CERT_SD = {"Vysoká": 0.0, "Střední": 0.75, "Nízká": 1.5, "Odhad": 1.5}
SEED = 20261105
FUTURES = 2000


def band(v, cuts):
    """cuts: list of (upper_inclusive, score), checked in order; last may be (inf, s)."""
    for up, s in cuts:
        if v <= up:
            return s
    raise ValueError(v)


def score_indicator(ind, objs):
    out = {}
    known = [o for o in objs if ind["values"].get(o) is not None]
    for o in objs:
        cell = ind["values"].get(o)
        if cell is None:
            out[o] = None
            continue
        v, cert, src = cell
        if ind["kind"] == "pásmo":
            s = band(v, ind["cuts"])
        elif ind["kind"] == "checklist":
            s = round(1 + 9 * v / ind["items"])
        else:  # slovní / přímo
            s = v
        out[o] = {"raw": v, "score": s, "cert": cert, "src": src}
    # rule 3: a missing value takes the median of the others' scores, certainty Odhad
    med = st.median([out[o]["score"] for o in known])
    for o in objs:
        if out[o] is None:
            out[o] = {"raw": None, "score": med, "cert": "Odhad", "src": "chybí → medián ostatních"}
    return out


def compute(spec):
    objs = [o["id"] for o in spec["objects"]]
    cats = spec["categories"]
    scores = {}
    for c in cats:
        for ind in c["indicators"]:
            scores[ind["code"]] = score_indicator(ind, objs)
    W = np.array([c["w"] for c in cats])
    assert abs(W.sum() - 1) < 1e-9, W.sum()

    def cat_means(sc):
        return np.array([[np.mean([sc[i["code"]][o] for i in c["indicators"]]) for c in cats] for o in objs])

    base = {k: {o: v[o]["score"] for o in objs} for k, v in scores.items()}
    M = cat_means(base)  # objects x categories
    total = M @ W
    Z = (M - M.mean(0)) / M.std(0, ddof=0).clip(1e-9)
    R = np.corrcoef(Z)
    sim = np.rint((R + 1) * 5).astype(int)

    # scenarios: Dirichlet weights, score noise by certainty
    rng = np.random.default_rng(SEED)
    codes = list(scores)
    sd = {k: {o: CERT_SD[scores[k][o]["cert"]] for o in objs} for k in codes}
    T = np.zeros((FUTURES, len(objs)))
    for f in range(FUTURES):
        w = rng.dirichlet(60 * W)
        sc = {}
        for k in codes:
            sc[k] = {}
            for o in objs:
                s = base[k][o]
                if sd[k][o] > 0:
                    s = float(np.clip(np.rint(s + rng.normal(0, sd[k][o])), 1, 10))
                sc[k][o] = s
        T[f] = cat_means(sc) @ w
    best = np.bincount(T.argmax(1), minlength=len(objs)) / FUTURES
    Tc = T - T.mean(1, keepdims=True)
    C = np.corrcoef(Tc.T)

    # classical MDS on profile distance
    D = np.sqrt(np.clip(2 * (1 - R), 0, None))
    n = len(objs)
    J = np.eye(n) - 1 / n
    B = -0.5 * J @ (D ** 2) @ J
    ev, V = np.linalg.eigh(B)
    idx = ev.argsort()[::-1][:2]
    X = V[:, idx] * np.sqrt(np.clip(ev[idx], 0, None))
    stress = None
    if spec.get("flip"):
        X = X * np.array(spec["flip"])

    # reliability of a profile link with k categories: |r| needed at p < .05, two-sided
    k = len(cats)
    tcrit = {7: 2.571, 8: 2.447, 9: 2.365, 10: 2.306}[k]
    rcrit = tcrit / math.sqrt(k - 2 + tcrit ** 2)

    return {
        "objs": objs,
        "cat_codes": [c["code"] for c in cats],
        "scores": scores,
        "M": M.round(2).tolist(),
        "total": total.round(2).tolist(),
        "Z": Z.round(2).tolist(),
        "R": R.round(2).tolist(),
        "sim": sim.tolist(),
        "best": best.round(3).tolist(),
        "median": np.median(T, 0).round(2).tolist(),
        "p05": np.percentile(T, 5, 0).round(2).tolist(),
        "p95": np.percentile(T, 95, 0).round(2).tolist(),
        "C": C.round(2).tolist(),
        "X": X.round(4).tolist(),
        "rcrit": round(rcrit, 2),
    }


def terrain_svg(res, labels, W=720, H=470, cell=3, sigma=0.62, links=None, cid="m"):
    """Envelope terrain: each object a hill of its height (total), terraces on the 1-10 scale."""
    ramp = ["#2c3e9e", "#2f6fd1", "#2aa3d8", "#37c2a9", "#2bb53f", "#99d02d", "#e7ee31", "#f5a332", "#e8672b", "#c8302a"]
    X = np.array(res["X"])
    h = np.array(res["total"])
    span = (X.max(0) - X.min(0)).max()
    Xn = (X - X.mean(0)) / span  # roughly -0.5..0.5
    pad = 105
    sx = (W - 2 * pad)
    sy = (H - 2 * pad)
    s = min(sx, sy * 1.0)
    P = np.c_[W / 2 + Xn[:, 0] * s, H / 2 - Xn[:, 1] * s]
    # display only: points closer than 46 px are pushed apart so each can be read
    for _ in range(200):
        moved = False
        for i in range(len(P)):
            for j in range(i + 1, len(P)):
                d = P[j] - P[i]
                dist = float(np.hypot(*d))
                if dist < 46:
                    u = d / dist if dist > 1e-6 else np.array([1.0, 0.0])
                    P[i] -= u * (46 - dist) / 2
                    P[j] += u * (46 - dist) / 2
                    moved = True
        if not moved:
            break
    nx, ny = W // cell, H // cell
    gx = (np.arange(nx) + 0.5) * cell
    gy = (np.arange(ny) + 0.5) * cell
    GX, GY = np.meshgrid(gx, gy)
    F = np.zeros_like(GX)
    sg = sigma * s / 2.2
    for (px, py), hi in zip(P, h):
        F = np.maximum(F, hi * np.exp(-((GX - px) ** 2 + (GY - py) ** 2) / (2 * sg ** 2)))
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{labels["aria"]}" style="display:block;background:var(--surface-sunken,#eef0f2);border-radius:8px">']
    for lv in range(1, 11):
        mask = F >= lv
        d = []
        for j in range(ny):
            row = mask[j]
            i = 0
            while i < nx:
                if row[i]:
                    k = i
                    while k < nx and row[k]:
                        k += 1
                    d.append(f"M{i*cell} {j*cell}h{(k-i)*cell}v{cell}h{-(k-i)*cell}z")
                    i = k
                else:
                    i += 1
        if d:
            parts.append(f'<path fill="{ramp[lv-1]}" d="{"".join(d)}"/>')
    if links:
        for a, b, r in links:
            col = "#f4f1ec" if r > 0 else "#ff7a59"
            wdt = 1.5 + 3 * abs(r)
            dash = "" if r > 0 else ' stroke-dasharray="7 5"'
            parts.append(f'<line x1="{P[a][0]:.1f}" y1="{P[a][1]:.1f}" x2="{P[b][0]:.1f}" y2="{P[b][1]:.1f}" stroke="{col}" stroke-width="{wdt:.1f}" stroke-linecap="round"{dash} opacity=".95"/>')
    boxes = []
    for i, (px, py) in enumerate(P):
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="#14171c" stroke="#fff" stroke-width="2"/>')
    for i, (px, py) in enumerate(P):
        lab = labels["names"][i]
        tw = 7.4 * len(lab) + 14
        for tx, ty in ((px - tw / 2, py - 30), (px - tw / 2, py + 10), (px + 10, py - 10), (px - tw - 10, py - 10)):
            box = (tx, ty, tx + tw, ty + 21)
            clear = all(box[2] < b0[0] or box[0] > b0[2] or box[3] < b0[1] or box[1] > b0[3] for b0 in boxes)
            clear = clear and all(not (box[0] - 4 < qx < box[2] + 4 and box[1] - 4 < qy < box[3] + 4) for k, (qx, qy) in enumerate(P) if k != i)
            if clear and box[1] > 0 and box[3] < H:
                break
        boxes.append(box)
        px = tx + tw / 2
        parts.append(f'<rect x="{px - tw/2:.1f}" y="{ty:.1f}" width="{tw:.1f}" height="21" rx="4" fill="#14171c" opacity=".86"/>')
        parts.append(f'<text x="{px:.1f}" y="{ty + 15:.1f}" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="600" fill="#fff">{lab}</text>')
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    res = compute(spec)
    json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    objs = res["objs"]
    print("total", dict(zip(objs, res["total"])))
    print("best", dict(zip(objs, res["best"])))
    print("median", dict(zip(objs, res["median"])), "p05", res["p05"], "p95", res["p95"])
    print("rcrit", res["rcrit"])
    for i, a in enumerate(objs):
        print(a, "R", res["R"][i], "sim", res["sim"][i], "C", res["C"][i])
    print("X", res["X"])
