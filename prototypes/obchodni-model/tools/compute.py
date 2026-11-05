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
            s = 1 + 9 * v / ind["items"]  # the declared rule, unrounded; only the board rounds for display
        else:  # slovní / přímo
            s = v
        out[o] = {"raw": v, "score": s, "cert": cert, "src": src}
    # rule 3: a missing value takes the median of the others' scores, certainty Odhad
    med = st.median([out[o]["score"] for o in known])
    for o in objs:
        if out[o] is None:
            out[o] = {"raw": None, "score": med, "cert": "Odhad", "src": "chybí → medián ostatních"}
    return out


def compute(spec, keep_futures=False):
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

    crossings = {}
    for cat, a, b in spec.get("crossings", []):
        crossings[f"{a}>{b}"] = crossing(M, W, [c["code"] for c in cats].index(cat), objs.index(a), objs.index(b))

    return {
        "crossings": crossings,
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
        **({"futures": T, "base": base} if keep_futures else {}),
    }


def crossing(M, W, k, a, b):
    """The weight of category k at which object a's total reaches object b's, the other weights
    scaled in proportion. Totals are linear in that weight, so the crossing is exact."""
    rest = np.delete(np.arange(len(W)), k)
    Wr = W[rest] / W[rest].sum()

    def gap(w):
        t = w * M[:, k] + (1 - w) * (M[:, rest] @ Wr)
        return t[a] - t[b]

    g0, g1 = gap(0.0), gap(1.0)
    if g0 == g1 or not (min(g0, g1) <= 0 <= max(g0, g1)):
        return None
    w = g0 / (g0 - g1)
    assert gap(w - 1e-3) * gap(w + 1e-3) < 0  # the order really flips here
    return round(float(w), 4)


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
