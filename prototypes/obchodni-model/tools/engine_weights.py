"""The weighting-scenario maps (MV9) computed by AIA's aia-sociomap-5 engine and drawn by AIA's
renderer of its maps (the report's figures), as engine_maps.py does for the indicator maps.

One ratings table per case: the rows are the tested weightings (every scenario's centre and its
fan of Dirichlet draws), the objects are the options, each cell the option's weighted score 0–10
under that weighting. The engine's layout and relations read every row unweighted (the signed-off
methodology), so two options lie close when the same weightings favour both. The engine's height
is the weighted mean rating: the rows of the decision owner's scenario carry weight 1 and every
other row a weight of 1e-6, so the height is the option's score under the owner's scenario (the
fan's mean, which is the centre's score). Pair statistics are not read: the rows are settings we
chose, not people (MV3's contract for the scenario mode).

Run from this folder with the repository's Python 3.12 environment (numpy 2.5, scipy 1.18,
numba 0.68, matplotlib, python-docx, Pillow) and PYTHONPATH at packages/aia_core/src:
    python3 engine_weights.py
It writes ../assets/si-weights-<case>-{top,3d,respondents}.jpg and engine_weights.json.
"""
import io
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from compute_weights import compute  # noqa: E402
from engine_maps import LABELS, summary  # noqa: E402

from aia_core.domain.sociomap.engine_v2 import compute_object_map  # noqa: E402
from aia_core.domain.sociomap.metrics import ObjectRole  # noqa: E402
from aia_core.domain.sociomap.models_v3 import ObjectMapInputs, RatingItem  # noqa: E402
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V5  # noqa: E402
from aia_core.infrastructure.report_docx.signed_off_map_figure import signed_off_snapshots  # noqa: E402

CASES = {
    "chemvitro": {"VR": "Vrbice", "LI": "Lipová", "KA": "Kamenec", "WE": "Wendelstedt", "LN": "Lindenau",
                  "ES": "Eschfeld", "OD": "Odrzyca", "BO": "Bory"},
    "velis": LABELS["options"],
}
OTHER_WEIGHT = 1e-6


def engine_map(rows, row_ids, objs, weights):
    inputs = ObjectMapInputs(
        respondent_ids=tuple(row_ids),
        donor_ids=tuple(row_ids),
        items=tuple(RatingItem(item_id=o, scale_min=0, scale_max=10) for o in objs),
        values=tuple(tuple(float(v) for v in r) for r in rows),
        weights=tuple(weights),
        object_ids=tuple(objs),
        object_items=tuple(objs),
        roles=dict.fromkeys(objs, ObjectRole.PRIMARY.value),
    )
    return compute_object_map(inputs, AIA_SOCIOMAP_V5, connectedness_interval=False)


def main():
    out = {}
    for case, labels in CASES.items():
        spec = json.load(open(os.path.join(HERE, f"spec_weights_{case}.json")))
        res = compute(spec, keep_rows=True)
        objs = res["objs"]
        owner = res["owner_scenario"]
        weights = [1.0 if s == owner else OTHER_WEIGHT for s in res["row_scenario"]]
        art = engine_map(res["row_values"].tolist(), res["row_ids"], objs, weights)
        # the height is the option's score under the owner's scenario: the centre's total, on 0–1
        centre = next(s for s in res["scenarios"] if s["code"] == owner)["centre"]
        for oi, h in enumerate(art.heights.values):
            want = centre[objs[oi]] / 10.0
            assert h is not None and abs(h - want) < 0.02, (case, objs[oi], h, want)
        out[case] = {**summary(art), "rows": res["rows"], "owner_scenario": owner,
                     "heights_as_scores": [None if h is None else round(h * 10, 2) for h in art.heights.values],
                     # the layout, so the board can name objects the renderer drew on one spot
                     "points": None if art.layout is None else [[round(p[0], 4), round(p[1], 4)] for p in art.layout.points],
                     "extent": None if art.layout is None else art.layout.extent}
        print(case, art.outcome, out[case]["method"], art.status_counts,
              None if art.credibility is None else (art.credibility.rule, art.credibility.split_half))
        if art.outcome != "MAPPED":
            continue
        for key, png in signed_off_snapshots(art, labels, respondents=True).items():
            Image.open(io.BytesIO(png)).convert("RGB").save(
                os.path.join(HERE, "..", "assets", f"si-weights-{case}-{key}.jpg"), "JPEG", quality=88)
    with open(os.path.join(HERE, "engine_weights.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
