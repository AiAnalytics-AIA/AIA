"""The weighting-scenario map's numbers (MV9), for a spec written by specs_weights.py.

Each component's value is read onto its declared value scale (worst anchor 0, best anchor 10,
linear, clipped); a ranged value gives a range of scores, and the base point is its documented
minimum, never a score in between. An option's total under a weight vector over the perspectives
is the weighted mean of its perspective scores, each perspective the plain mean of its components;
a perspective with no component takes no weight. Gates are pass / fail / unknown and never
compensated: an option a gate rules out is drawn on the map for comparison and is never first.

A scenario is a named weight vector; around each the fan draws Dirichlet weights with the
printed concentration (the same spread for every scenario) and keeps every other input at the
base point, so the fan tests weights alone. What is reported per scenario: who is first at the
centre among every option (preference information) and among the options the gates let through,
and each option's share of the fan's draws in which it is first. Shares are shares of tested
settings, which we chose; they are not probabilities. The client's rule decides; the map and the
tables say what the weightings prefer.
"""
import json
import sys

import numpy as np


def score(comp, v):
    lo, hi = comp["anchors"]
    return float(np.clip(10.0 * (v - lo) / (hi - lo), 0.0, 10.0))


def cells(spec):
    """{component code: {object: {lo, hi, ranged}}} on the value scale."""
    out = {}
    for p in spec["perspectives"]:
        for c in p["components"]:
            row = {}
            for o, v in c["values"].items():
                if isinstance(v, list):
                    a, b = score(c, v[0]), score(c, v[1])
                    row[o] = {"lo": min(a, b), "hi": max(a, b), "ranged": True}
                else:
                    s = score(c, v)
                    row[o] = {"lo": s, "hi": s, "ranged": False}
            out[c["code"]] = row
    return out


def active(spec):
    return [p for p in spec["perspectives"] if p["components"]]


def weight_vector(spec, weights):
    """The scenario's weights over the active perspectives, renormalised; an unnamed one is 0."""
    ps = active(spec)
    w = np.array([float(weights.get(p["code"], 0.0)) for p in ps])
    if w.sum() <= 0:
        raise ValueError(weights)
    return w / w.sum()


def totals(spec, C, w, pick):
    """Each option's total under weights w (over the active perspectives); pick(code, o, cell) -> a score."""
    objs = [o["id"] for o in spec["objects"]]
    ps = active(spec)
    T = np.zeros(len(objs))
    for oi, o in enumerate(objs):
        for p, wp in zip(ps, w):
            if wp == 0:
                continue
            T[oi] += wp * float(np.mean([pick(c["code"], o, C[c["code"]][o]) for c in p["components"]]))
    return T


def gate_state(spec, setting):
    objs = [o["id"] for o in spec["objects"]]
    st = {}
    for o in objs:
        states = []
        for g in spec["gates"]:
            v = setting["override"].get(g["code"], {}).get(o, g["values"][o])
            states.append(v[0])
        st[o] = "fail" if "fail" in states else ("unknown" if "unknown" in states else "pass")
    return st


def compute(spec, keep_rows=False):
    objs = [o["id"] for o in spec["objects"]]
    C = cells(spec)
    base = lambda k, o, x: x["lo"]  # noqa: E731
    rng = np.random.default_rng(spec["fan"]["seed"])
    conc, draws = spec["fan"]["concentration"], spec["fan"]["draws"]

    settings = {}
    for s in spec["gate_settings"]:
        st = gate_state(spec, s)
        settings[s["code"]] = {"name": s["name"], "state": st, "alive": [o for o in objs if st[o] == "pass"]}

    def first(T, alive=None):
        T = np.asarray(T, float).copy()
        if alive is not None:
            if not alive:
                return None
            T[[o not in alive for o in objs]] = -np.inf
        return objs[int(np.argmax(T))]

    scenarios, rows, row_ids, row_scenario = [], [], [], []
    for sc in spec["scenarios"]:
        w = weight_vector(spec, sc["weights"])
        centre = totals(spec, C, w, base)
        top = totals(spec, C, w, lambda k, o, x: x["hi"])
        nz = w > 0
        fan = np.zeros((draws, len(objs)))
        fan_w = np.zeros((draws, len(w)))
        for d in range(draws):
            wd = np.zeros_like(w)
            wd[nz] = rng.dirichlet(conc * w[nz])
            fan_w[d] = wd
            fan[d] = totals(spec, C, wd, base)
        firsts_all = [first(r) for r in fan]
        share_all = {o: round(firsts_all.count(o) / draws, 3) for o in objs}
        by_setting = {}
        for code, s in settings.items():
            f = [first(r, s["alive"]) for r in fan]
            by_setting[code] = {"first": first(centre, s["alive"]),
                                "share": {o: round(f.count(o) / draws, 3) for o in objs} if s["alive"] else None}
        # a ranged cell whose top value alone would make its option first at this centre
        critical = []
        for k, row in C.items():
            for o, x in row.items():
                if not x["ranged"]:
                    continue
                one = lambda kk, oo, y, k=k, o=o: y["hi"] if (kk, oo) == (k, o) else y["lo"]  # noqa: E731
                t1 = totals(spec, C, w, one)
                if first(t1) == o and first(centre) != o:
                    critical.append([k, o, round(float(t1[objs.index(o)]), 2)])
        scenarios.append({
            "code": sc["code"], "name": sc["name"], "who": sc["who"],
            "w": {p["code"]: round(float(x), 3) for p, x in zip(active(spec), w)},
            "centre": dict(zip(objs, centre.round(2).tolist())), "top": dict(zip(objs, top.round(2).tolist())),
            "first": first(centre), "share": share_all, "by_setting": by_setting, "critical": critical,
            "fan_w_sd": fan_w.std(0).round(3).tolist(),
        })
        rows.append(centre)
        row_ids.append(f"{sc['code']}:0")
        row_scenario.append(sc["code"])
        for d in range(draws):
            rows.append(fan[d])
            row_ids.append(f"{sc['code']}:{d + 1}")
            row_scenario.append(sc["code"])
    R = np.array(rows)
    pooled = {o: round(float(np.mean([first(r) == o for r in R])), 3) for o in objs}

    # the perspective scores at the base point, for the board's table
    persp = {}
    for p in active(spec):
        persp[p["code"]] = {o: round(float(np.mean([C[c["code"]][o]["lo"] for c in p["components"]])), 2) for o in objs}
    out = {
        "case": spec["case"], "objs": objs, "active": [p["code"] for p in active(spec)],
        "cells": {k: {o: {"lo": round(x["lo"], 2), "hi": round(x["hi"], 2), "ranged": x["ranged"]} for o, x in row.items()} for k, row in C.items()},
        "persp": persp, "settings": settings, "scenarios": scenarios, "pooled": pooled,
        "rows": len(rows), "fan": spec["fan"], "owner_scenario": spec["owner_scenario"],
    }
    if keep_rows:
        out["row_values"], out["row_ids"], out["row_scenario"] = R, row_ids, row_scenario
    return out


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    res = compute(spec)
    json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(res["case"], "rows", res["rows"], "pooled", res["pooled"])
    for s in res["scenarios"]:
        print(s["code"], s["w"], "first", s["first"], {k: v["first"] for k, v in s["by_setting"].items()}, "critical", s["critical"])
        print("   centre", s["centre"])
        print("   share", s["share"])
