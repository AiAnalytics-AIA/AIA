"""Checks the computed maps against the rules the boards print, and against Výsledky. Run after compute.py."""
import html
import json
import re

import numpy as np

so, ro = json.load(open("spec_options.json")), json.load(open("res_options.json"))
ss, rs = json.load(open("spec_suppliers.json")), json.load(open("res_suppliers.json"))

# A checklist scores 1 + 9 x share of items met, unrounded; an undocumented item is unknown, not absent
assert abs(rs["cells"]["P1"]["WI"]["lo"] - 4.6) < 1e-9  # nnyyn: 2 of 5, three evidenced absent
assert abs(rs["cells"]["V1"]["DE"]["lo"] - 7.75) < 1e-9  # yyny: 3 of 4
assert abs(rs["cells"]["P1"]["DE"]["lo"] - 10) < 1e-9
mo = rs["cells"]["P1"]["MO"]  # yy?y?: 3 met, 2 unknown
assert mo["state"] == "partial" and abs(mo["lo"] - 6.4) < 1e-9 and abs(mo["hi"] - 10) < 1e-9

# An unknown cell has a range and no score; v1's medians and the "nothing reported = 8" rule are gone
for res in (ro, rs):
    for row in res["cells"].values():
        for x in row.values():
            if x["state"] == "unknown":
                assert x["lo"] < x["hi"] and "score" not in x
assert rs["cells"]["R1"]["WI"]["state"] == "unknown"
assert rs["cells"]["P1"]["VL"]["state"] == "na"

# The map reads the model's own numbers: E1 and R1 are the medians and loss shares Výsledky prints
t = open("../KM4Results.dc.html").read()
t = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(style|script).*?</\1>", "", t, flags=re.S)))
t = re.sub(r"\s+", " ", t)
label = {"A": "A · Vlastní sklad", "A2": "A2 · Sklad po etapách", "B2": "B2 · 3PL CZ, pevná cena", "C": "C · Polský 3PL",
         "C2": "C2 · Polský 3PL + expres", "H": "H · Hybrid"}
e1 = {o: x["raw"] for o, x in ro["cells"]["E1"].items()}
r1 = {o: x["raw"] for o, x in ro["cells"]["R1"].items()}
for o, lab in label.items():
    m = re.search(re.escape(lab) + r".*?([+−]\d+,\d) [−+]?\d+,\d až [+−]?\d+,\d (\d,\d\d) [✔✘] (\d,\d\d)", t)
    assert m, o
    med = float(m.group(1).replace("−", "-").replace(",", "."))
    loss = float(m.group(3).replace(",", "."))
    assert abs(med - e1[o]) < 1e-9, (o, med, e1[o])
    assert abs(loss * 100 - r1[o]) < 1e-9, (o, loss, r1[o])

# A gate that fails rules the object out of every family; C fails the promise in the cities
iC = ro["objs"].index("C")
assert ro["gate"]["C"] == "fail" and all(v[iC] == 0 for v in ro["families"].values())

# C2 passes B2 exactly at the printed crossing of Ekonomika's weight, the others scaled in proportion
M = np.array(ro["M"])
W = np.array(ro["W"])
o = ro["objs"]


def totals(we):
    w = np.r_[we, W[1:] / W[1:].sum() * (1 - we)]
    return dict(zip(o, M @ w))


x = ro["crossings"]["C2>B2"]
assert totals(x - 0.001)["B2"] > totals(x - 0.001)["C2"]
assert totals(x + 0.001)["C2"] > totals(x + 0.001)["B2"]
assert abs(totals(W[0])["C2"] - ro["total"][o.index("C2")]) < 0.01
print("ok", x, ro["critical"], rs["critical"])

# Every scale the boards draw matches its spec: one label per band, and each level holds exactly its known objects
look = json.load(open("look.json"))
for m, spec, res in (("options", so, ro), ("suppliers", ss, rs)):
    for c in spec["categories"]:
        for i in c["indicators"]:
            lk = look[m].get(i["code"], {})
            if i["kind"] == "pásmo":
                assert len(lk["bands"]) == len(i["cuts"]), (m, i["code"])
            if i["kind"] == "slovní":
                got = {ob: v["v"] for ob, v in i["values"].items() if v["state"] == "known"}
                assert sorted(ob for _, _, mem in lk["levels"] for ob in mem) == sorted(got), (m, i["code"])
                assert all(got[ob] == score for _, score, mem in lk["levels"] for ob in mem), (m, i["code"])
print("scales ok")

# ---------------- the weighting-scenario map (MV9): compute_weights.py and engine_weights.py ----------------
for case in ("chemvitro", "velis"):
    spec = json.load(open(f"spec_weights_{case}.json"))
    res = json.load(open(f"res_weights_{case}.json"))
    objs = res["objs"]
    # a scored cell is on the declared value scale; a ranged value is a range of scores, never a single
    # number; a null value does not apply; an informational row has no cell; a gate is never a component
    comps = [c for p in spec["perspectives"] for c in p["components"] if not c.get("info")]
    assert len(comps) == res["scored"]
    for c in comps:
        assert c["role"] in ("saving", "part", "outside"), (case, c["code"])
        for o, v in c["values"].items():
            x = res["cells"][c["code"]][o]
            if v is None:
                assert x is None, (case, c["code"], o)
                continue
            assert 0 <= x["lo"] <= x["hi"] <= 10, (case, c["code"], o)
            assert x["ranged"] == isinstance(v, list), (case, c["code"], o)
    for p in spec["perspectives"]:
        for c in p["components"]:
            if c.get("info"):
                assert c["name"] not in res["cells"]
    # the overlap check: a vector weighting the saving and one of its parts is refused, every admitted scenario
    # weights only the roles its family admits, and its weights sum to one with none on a perspective its family
    # leaves empty
    for r in res["refused"]:
        assert {"saving", "part"} <= set(r["roles"]), (case, r["code"])
    for s in res["scenarios"]:
        fam = spec["families"][s["family"]]
        assert set(s["roles"]) <= set(fam["roles"]), (case, s["code"], s["roles"])
        assert abs(sum(s["w"].values()) - 1) < 5e-3, (case, s["code"])
        for p in spec["perspectives"]:
            if not any(not c.get("info") and c["role"] in fam["roles"] for c in p["components"]):
                assert s["w"][p["code"]] == 0, (case, s["code"], p["code"])
        assert abs(sum(s["share"].values()) - 1) < 5e-3, (case, s["code"])  # shares are rounded to 3 places
        # the centre's first is the option with the highest total; an option a gate rules out is never first after the gates
        assert s["first"] == max(s["centre"], key=s["centre"].get)
        for code, st in res["settings"].items():
            f = s["by_setting"][code]["first"]
            assert (f is None) == (not st["alive"]) and (f is None or st["state"][f] == "pass"), (case, s["code"], code)
            if s["by_setting"][code]["share"]:
                assert all(v == 0 for o, v in s["by_setting"][code]["share"].items() if st["state"][o] != "pass")
    assert abs(sum(res["pooled"].values()) - 1) < 5e-3
    # the engine's height is the owner's scenario score (its fan's mean), within 0.2 of a point
    eng = json.load(open("engine_weights.json"))[case]
    centre = next(s for s in res["scenarios"] if s["code"] == res["owner_scenario"])["centre"]
    for o, h in zip(objs, eng["heights_as_scores"]):
        assert abs(h - centre[o]) < 0.2, (case, o, h, centre[o])
    assert eng["rows"] == res["rows"] == (len(spec["scenarios"]) - len(res["refused"])) * (spec["fan"]["draws"] + 1)
# ChemVitro today: the rule as written lets no site through, so nobody is first after the gates
rc = json.load(open("res_weights_chemvitro.json"))
assert rc["settings"]["dnes"]["alive"] == [] and sorted(rc["settings"]["urady"]["alive"]) == ["KA", "LI", "OD"]
# the owner's "finance 0,5 · provoz 0,3 · logistika 0,2" over every component is the refused vector
assert [r["code"] for r in rc["refused"]] == ["FR_ALL"]
# Odrzyca is the leading site itself, so the shared-failure component does not apply to it
assert rc["cells"]["S1"]["OD"] is None
print("weights ok")
