"""Checks the computed maps against the rules the boards print. Run after compute.py."""
import json
import numpy as np

so, ro = json.load(open("spec_options.json")), json.load(open("res_options.json"))
rs = json.load(open("res_suppliers.json"))

# A checklist scores 1 + 9 x share, unrounded (SI1, SI4 catalogue)
assert abs(rs["scores"]["P1"]["WI"]["score"] - 4.6) < 1e-9  # 2 of 5
assert abs(rs["scores"]["V1"]["DE"]["score"] - 7.75) < 1e-9  # 3 of 4
assert abs(rs["scores"]["P1"]["DE"]["score"] - 10) < 1e-9  # 5 of 5

# C2 passes B2 exactly at the printed crossing of Ekonomika's weight, the others scaled in proportion
M = np.array(ro["M"])
W = np.array([c["w"] for c in so["categories"]])
o = ro["objs"]


def totals(we):
    w = np.r_[we, W[1:] / W[1:].sum() * (1 - we)]
    return dict(zip(o, M @ w))


x = ro["crossings"]["C2>B2"]
assert totals(x - 0.001)["B2"] > totals(x - 0.001)["C2"]
assert totals(x + 0.001)["C2"] > totals(x + 0.001)["B2"]
assert totals(0.22)["B2"] > max(v for k, v in totals(0.22).items() if k != "B2")
print("ok", x, ro["crossings"]["C2>B"])
