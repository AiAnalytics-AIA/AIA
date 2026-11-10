"""Indicator Sociomapa for the Velis case, method v2: two maps (options, suppliers).

A cell is known (a score by the declared rule), unknown (the range of scores it could take,
never a guess), not applicable (left out; the object's other criteria carry its weight), or a
checklist whose items are met, evidenced absent or unknown. Gates are pass / fail / unknown and
never compensated. Weights come from the decision owner's swing points.

The base point, the centre of every test, is the documented minimum: an unknown cell at the bottom
of its range. That is not the cell's score, only the conservative case; the tables print the range,
the top case shows where evidence could move an object, and the missing-data test says whether the
missing evidence could change who is first. The engine's maps get no value for an unknown cell.

Sensitivity, not probability: each family varies one kind of assumption around the base and
reports the share of the tested settings in which an object is first among those no gate rules
out. The settings are ours (the families' sizes and spreads are printed), so a share describes the
test, not the world. Future business performance is not simulated here: it is in Výsledky (the
model's futures), and E1 and R1 read it from there.
"""
import json
import math
import sys

import numpy as np

SEED = 20261105
EVIDENCE_SETS = {  # score noise (SD, points) by certainty: evidence uncertainty, never zero
    "nižší": {"Vysoká": 0.10, "Střední": 0.50, "Nízká": 1.00},
    "výchozí": {"Vysoká": 0.25, "Střední": 0.75, "Nízká": 1.50},
    "vyšší": {"Vysoká": 0.50, "Střední": 1.50, "Nízká": 2.50},
}
CONCENTRATIONS = (20, 60, 200)  # Dirichlet concentration around the owner's weights
PER = 300  # draws per setting group
COMBINED = 2000


def band(v, cuts):
    for up, s in cuts:
        if v <= up:
            return s
    raise ValueError(v)


def scale_range(ind):
    if ind["kind"] == "pásmo":
        ss = [s for _, s in ind["cuts"]]
        return min(ss), max(ss)
    if ind["kind"] == "slovní":
        return tuple(ind.get("range", (1, 10)))
    return 1, 10


def score_cell(ind, cell):
    """-> dict(state, lo, hi, cert, src, raw); lo == hi for a known cell."""
    st = cell["state"]
    if st == "na":
        return {"state": "na", "src": cell["src"]}
    if st == "unknown":
        lo, hi = scale_range(ind)
        return {"state": "unknown", "lo": lo, "hi": hi, "cert": None, "src": cell["src"], "raw": None}
    if st == "checklist":
        it = cell["v"]
        n, met, unk = len(it), it.count("y"), it.count("?")
        lo, hi = 1 + 9 * met / n, 1 + 9 * (met + unk) / n
        return {"state": "known" if unk == 0 else "partial", "lo": lo, "hi": hi, "cert": cell["cert"], "src": cell["src"],
                "raw": it, "known_share": 1 - unk / n}
    v = cell["v"]
    s = band(v, ind["cuts"]) if ind["kind"] == "pásmo" else v
    return {"state": "known", "lo": s, "hi": s, "cert": cell["cert"], "src": cell["src"], "raw": v}


def weights_of(points, cats):
    w = np.array([points[c["code"]] for c in cats], float)
    return w / w.sum()


def structure(spec, name):
    """The scored criteria under a named alternative structure: (cats, extra columns)."""
    cats = [dict(c) for c in spec["categories"]]
    if name == "bez R1":
        cats = [c for c in cats if c["code"] != "R"]
    return cats


def linear_score(ind, v, known_vals):
    lo_v, hi_v = min(known_vals), max(known_vals)
    if hi_v == lo_v:
        return band(v, ind["cuts"])
    up = band(hi_v, ind["cuts"]) >= band(lo_v, ind["cuts"])
    t = (v - lo_v) / (hi_v - lo_v)
    return 1 + 9 * (t if up else 1 - t)


def evaluate(spec, cats, W, pick, linear=False, experts=None):
    """Totals per object. pick(code, o, cell) -> a score for a non-na cell. W per category.
    experts: optional (weight, {o: score}) added as one more criterion."""
    objs = [o["id"] for o in spec["objects"]]
    T = np.zeros(len(objs))
    for oi, o in enumerate(objs):
        num = den = 0.0
        for c, w in zip(cats, W):
            vals = []
            for ind in c["indicators"]:
                cell = spec["_cells"][ind["code"]][o]
                if cell["state"] == "na":
                    continue
                if linear and ind["kind"] == "pásmo" and cell["state"] == "known":
                    kv = [x["raw"] for x in spec["_cells"][ind["code"]].values() if x["state"] == "known"]
                    vals.append(linear_score(ind, cell["raw"], kv))
                else:
                    vals.append(pick(ind["code"], o, cell))
            if vals:
                num += w * float(np.mean(vals))
                den += w
        if experts:
            we, ex = experts
            num, den = num * (1 - we) / den, 1 - we
            num += we * ex[o]
            den += we
        T[oi] = num / den
    return T


def compute(spec, keep_futures=False):
    objs = [o["id"] for o in spec["objects"]]
    cats = spec["categories"]
    cells = {ind["code"]: {o: score_cell(ind, ind["values"][o]) for o in objs} for c in cats for ind in c["indicators"]}
    spec["_cells"] = cells
    W = weights_of(spec["swing"][spec["owner"]], cats)
    lo = lambda k, o, x: x["lo"]  # noqa: E731
    mid = lo  # the base point: the documented minimum
    hi = lambda k, o, x: x["hi"]  # noqa: E731

    # gates
    gate = {}
    for o in objs:
        sts = [g["values"][o][0] for g in spec.get("gates", [])]
        gate[o] = "fail" if "fail" in sts else ("unknown" if "unknown" in sts else "pass")
    alive = np.array([gate[o] != "fail" for o in objs])

    # category means at the base point, and the object's coverage
    M = np.full((len(objs), len(cats)), np.nan)
    Mlo, Mhi = M.copy(), M.copy()
    coverage = []
    for oi, o in enumerate(objs):
        kw = aw = 0.0
        for ci, c in enumerate(cats):
            xs = [cells[i["code"]][o] for i in c["indicators"] if cells[i["code"]][o]["state"] != "na"]
            if not xs:
                continue
            M[oi, ci] = Mlo[oi, ci] = np.mean([x["lo"] for x in xs])
            Mhi[oi, ci] = np.mean([x["hi"] for x in xs])
            share = np.mean([x.get("known_share", 1.0 if x["state"] == "known" else 0.0) for x in xs])
            kw += W[ci] * share
            aw += W[ci]
        coverage.append(kw / aw)
    total = evaluate(spec, cats, W, lo)
    thi = evaluate(spec, cats, W, hi)
    tlo = total

    def firsts(T):
        T = np.where(alive, T, -np.inf)
        return int(np.argmax(T))

    lead = firsts(total)
    can_pass = [objs[i] for i in range(len(objs)) if alive[i] and i != lead and thi[i] > tlo[lead]]

    # decision-critical unknowns: a cell whose top value alone would put its object first
    critical = []
    for k, row in cells.items():
        for oi, o in enumerate(objs):
            x = row[o]
            if x["state"] in ("known", "na") or not alive[oi]:
                continue
            one = lambda kk, oo, y, k=k, o=o: y["hi"] if (kk, oo) == (k, o) else y["lo"]  # noqa: E731
            t1 = evaluate(spec, cats, W, one)
            others = max(t1[j] for j in range(len(objs)) if alive[j] and j != oi)
            if t1[oi] > others:
                critical.append([k, o, round(float(t1[oi]), 2), round(float(others), 2)])
    # not applicable: what the object's total would be with its n/a cells at the scale's ends
    na_test = {}
    for oi, o in enumerate(objs):
        nas = [k for k, row in cells.items() if row[o]["state"] == "na"]
        if nas:
            ends = []
            for v in (1.0, 10.0):
                pick = lambda kk, oo, y, v=v, o=o, nas=nas: v if (oo == o and kk in nas) else y["lo"]  # noqa: E731
                for kk in nas:
                    cells[kk][o] = {"state": "known", "lo": v, "hi": v, "cert": "Vysoká", "src": "test", "raw": None, "_na": True}
                ends.append(round(float(evaluate(spec, cats, W, pick)[oi]), 2))
                for kk in nas:
                    cells[kk][o] = {"state": "na", "src": spec_na_src(spec, kk, o)}
            na_test[o] = {"codes": nas, "at1": ends[0], "at10": ends[1]}

    rng = np.random.default_rng(SEED)
    fam = {}

    def share(rows):
        rows = np.asarray(rows)
        f = [firsts(r) for r in rows]
        return (np.bincount(f, minlength=len(objs)) / len(f)).round(3).tolist(), rows

    # 1. preferences: each stakeholder's own swing weights, and Dirichlet around the owner's
    pref = [evaluate(spec, cats, weights_of(p, cats), mid) for p in spec["swing"].values()]
    stake = {k: objs[firsts(t)] for k, t in zip(spec["swing"], pref)}
    for c in CONCENTRATIONS:
        pref += [evaluate(spec, cats, rng.dirichlet(c * W), mid) for _ in range(PER)]
    fam["váhy"], _ = share(pref)

    # 2. evidence: noise by certainty, three spreads; unknown cells at the base point
    def noisy(sd):
        def pick(k, o, x):
            if x["state"] == "unknown":
                return x["lo"]
            s = x["lo"] + rng.normal(0, sd[x["cert"]])
            return float(np.clip(s, 1, 10))
        return pick
    ev = []
    for name, sd in EVIDENCE_SETS.items():
        ev += [evaluate(spec, cats, W, noisy(sd)) for _ in range(PER)]
    fam["důkazy"], _ = share(ev)

    # 3. missing data: every unknown cell anywhere in its range
    def uni(k, o, x):
        return float(rng.uniform(x["lo"], x["hi"])) if x["lo"] != x["hi"] else x["lo"]
    fam["chybějící údaje"], _ = share([evaluate(spec, cats, W, uni) for _ in range(3 * PER)])

    # 4. structure: alternative defensible scoring structures, one setting each
    ex = spec.get("experts")
    structs = {"schválená": total, "lineární škály": evaluate(spec, cats, W, mid, linear=True)}
    if ex:
        structs["s experty 10 %"] = evaluate(spec, cats, W, mid, experts=(0.10, ex))
    rc = [c for c in cats if c["code"] != "R"]
    if len(rc) < len(cats):
        structs["bez R1"] = evaluate(spec, rc, weights_of({k: v for k, v in spec["swing"][spec["owner"]].items() if k != "R"}, rc), mid)
    struct_first = {k: objs[firsts(t)] for k, t in structs.items()}
    fam["struktura"] = (np.bincount([firsts(t) for t in structs.values()], minlength=len(objs)) / len(structs)).round(3).tolist()

    # 5. everything at once
    comb = []
    sd = EVIDENCE_SETS["výchozí"]
    for _ in range(COMBINED):
        w = rng.dirichlet(60 * W)
        s = rng.integers(len(structs))
        sname = list(structs)[s]

        def pick(k, o, x):
            if x["lo"] != x["hi"] and x["state"] != "known":
                return float(rng.uniform(x["lo"], x["hi"]))
            return float(np.clip(x["lo"] + rng.normal(0, sd[x["cert"]]), 1, 10))
        if sname == "bez R1":
            keep = [i for i, c in enumerate(cats) if c["code"] != "R"]
            comb.append(evaluate(spec, rc, w[keep] / w[keep].sum(), pick))
        else:
            comb.append(evaluate(spec, cats, w, pick, linear=(sname == "lineární škály"),
                                 experts=(0.10, ex) if sname == "s experty 10 %" else None))
    fam["vše najednou"], T = share(comb)
    Tc = T - T.mean(1, keepdims=True)
    C = np.corrcoef(Tc.T)
    Craw = np.corrcoef(T.T)

    Mf = np.nan_to_num(M, nan=np.nanmean(M))
    Z = (Mf - Mf.mean(0)) / Mf.std(0, ddof=0).clip(1e-9)
    R = np.corrcoef(Z)
    sim = np.rint((R + 1) * 5).astype(int)
    k = len(cats)
    tcrit = {6: 2.776, 7: 2.571, 8: 2.447, 9: 2.365, 10: 2.306}[k]
    rcrit = tcrit / math.sqrt(k - 2 + tcrit ** 2)

    crossings = {}
    for cat, a, b in spec.get("crossings", []):
        crossings[f"{a}>{b}"] = crossing(Mf, W, [c["code"] for c in cats].index(cat), objs.index(a), objs.index(b))

    out = {
        "objs": objs, "cat_codes": [c["code"] for c in cats], "W": W.round(4).tolist(),
        "stakeholder_weights": {k: weights_of(p, cats).round(3).tolist() for k, p in spec["swing"].items()},
        "cells": cells, "gate": gate, "coverage": np.round(coverage, 3).tolist(),
        "M": np.round(M, 2).tolist(), "Mlo": np.round(Mlo, 2).tolist(), "Mhi": np.round(Mhi, 2).tolist(),
        "total": total.round(2).tolist(), "tlo": tlo.round(2).tolist(), "thi": thi.round(2).tolist(),
        "lead": objs[lead], "critical": critical, "na_test": na_test, "can_pass": can_pass, "families": fam,
        "family_sizes": {"váhy": len(pref), "důkazy": len(ev), "chybějící údaje": 3 * PER, "struktura": len(structs), "vše najednou": COMBINED},
        "stakeholder_first": stake, "structure_first": struct_first,
        "median": np.median(T, 0).round(2).tolist(), "p05": np.percentile(T, 5, 0).round(2).tolist(),
        "p95": np.percentile(T, 95, 0).round(2).tolist(),
        "C": C.round(2).tolist(), "Craw": Craw.round(2).tolist(), "R": R.round(2).tolist(), "sim": sim.tolist(),
        "rcrit": round(rcrit, 2), "crossings": crossings,
    }
    if keep_futures:
        out["settings"] = T
    return out


def spec_na_src(spec, code, o):
    for c in spec["categories"]:
        for i in c["indicators"]:
            if i["code"] == code:
                return i["values"][o]["src"]


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
    assert gap(w - 1e-3) * gap(w + 1e-3) < 0
    return round(float(w), 4)


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    res = compute(spec)
    res.pop("cells")
    json.dump({**res, "cells": compute(json.load(open(sys.argv[1])))["cells"]}, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    o = res["objs"]
    print("W", dict(zip(res["cat_codes"], res["W"])))
    for k in ("gate", "coverage", "total", "tlo", "thi", "lead", "can_pass", "families", "stakeholder_first", "structure_first", "crossings"):
        v = res[k]
        print(k, dict(zip(o, v)) if isinstance(v, list) and len(v) == len(o) else v)
