"""The two maps of each board computed by AIA's own aia-sociomap-5 engine, and drawn by AIA's own
renderer of that engine's maps (the report's figures, infrastructure/report_docx/signed_off_map_figure.py).

Two readings of the same scores, each a ratings table the engine maps as it maps respondents:
- indicators as the rows: each indicator "rates" every option 1-10 (the cloud method's profile:
  options close when they score alike across indicators);
- the 2 000 tested settings as the rows (weights, evidence, missing data and structure varied at
  once): each setting's weighted total per option (options close when they come out well in the
  same settings). They are sensitivity settings we chose, not futures and not people.

Run from this folder with the repository's Python 3.12 environment and PYTHONPATH pointing at
packages/aia_core/src (numpy 2.5, scipy 1.18, numba 0.68, matplotlib):
    python3 engine_maps.py
It writes the figures to ../assets/si-*.jpg and what the boards print about them to engine.json.
"""
import io
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from compute import compute  # noqa: E402

from aia_core.domain.sociomap.engine_v2 import compute_object_map  # noqa: E402
from aia_core.domain.sociomap.metrics import ObjectRole  # noqa: E402
from aia_core.domain.sociomap.models_v3 import ObjectMapInputs, RatingItem  # noqa: E402
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V5  # noqa: E402
from aia_core.infrastructure.report_docx.signed_off_map_figure import signed_off_snapshots  # noqa: E402

LABELS = {
    "options": {"A": "A · Hala", "A2": "A2 · Hala po etapách", "B": "B · 3PL CZ", "B2": "B2 · Pevná cena",
                "C": "C · 3PL PL", "C2": "C2 · PL + expres", "H": "H · Hybrid"},
    "suppliers": {"DE": "Delta", "WI": "Wisła", "VL": "Vlastní provoz", "MO": "Morava*", "PO": "Polaris*", "DU": "Dunaj*"},
}


def engine_map(rows, row_ids, objs, weights=None):
    inputs = ObjectMapInputs(
        respondent_ids=tuple(row_ids),
        donor_ids=tuple(row_ids),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objs),
        values=tuple(tuple(None if v is None else float(v) for v in r) for r in rows),
        # The engine's height (F8) is each object's weighted mean rating; the relation and the
        # layout read the ratings unweighted. A profile row carries its category's weight shared
        # among the category's indicators, so a height is exactly the board's weighted total.
        weights=tuple(weights) if weights else (1.0,) * len(rows),
        object_ids=tuple(objs),
        object_items=tuple(objs),
        roles=dict.fromkeys(objs, ObjectRole.PRIMARY.value),
    )
    return compute_object_map(inputs, AIA_SOCIOMAP_V5, connectedness_interval=False)


def summary(art):
    layout = art.layout
    cred = art.credibility
    rel = art.relations
    m = len(art.object_ids)
    pairs = [(art.object_ids[i], art.object_ids[j], rel.status[i][j], rel.r[i][j])
             for i in range(m) for j in range(i + 1, m)]
    return {
        "outcome": art.outcome,
        "method": None if layout is None else str(layout.method),
        "status_counts": art.status_counts,
        "credibility": None if cred is None else json.loads(cred.model_dump_json()),
        "pairs": [[a, b, str(s), None if r is None else round(r, 3)] for a, b, s, r in pairs],
        "heights": [None if h is None else round(h, 3) for h in art.heights.values],
        "segments": None if getattr(art.respondents, "segments", None) is None else json.loads(art.respondents.segments.model_dump_json()),
    }


def main():
    out = {}
    for name in ("options", "suppliers"):
        spec = json.load(open(os.path.join(HERE, f"spec_{name}.json")))
        res = compute(spec, keep_futures=True)
        objs = res["objs"]
        cells = res["cells"]
        W = dict(zip(res["cat_codes"], res["W"]))
        # profile rows: the scored indicators; a cell that is not fully known gets no value
        codes, ind_w = [], []
        for c in spec["categories"]:
            for i in c["indicators"]:
                codes.append(i["code"])
                ind_w.append(W[c["code"]] / len(c["indicators"]))
        ind_rows = [[cells[k][o]["lo"] if cells[k][o]["state"] == "known" else None for o in objs] for k in codes]
        fut_rows = res["settings"].tolist()
        for view, rows, ids in (("profil", ind_rows, codes), ("nastaveni", fut_rows, [f"t{k}" for k in range(len(fut_rows))])):
            art = engine_map(rows, ids, objs, ind_w if view == "profil" else None)
            if view == "profil":  # the height is the weighted mean of the object's known cells
                for oi, h in enumerate(art.heights.values):
                    kn = [(w, r[oi]) for w, r in zip(ind_w, ind_rows) if r[oi] is not None]
                    want = (sum(w * v for w, v in kn) / sum(w for w, _ in kn) - 1) / 9
                    assert h is not None and abs(h - want) < 5e-3, (name, objs[oi], h, want)
            out[f"{name}/{view}"] = summary(art)
            if art.outcome != "MAPPED" or view == "profil":  # from 7 criteria the profile map is undetermined: not drawn
                continue
            for key, png in signed_off_snapshots(art, LABELS[name], respondents=(view == "nastaveni")).items():
                # JPEG at quality 88, as the canvas's other map images; the renderer's PNG is 1-1.4 MB
                Image.open(io.BytesIO(png)).convert("RGB").save(
                    os.path.join(HERE, "..", "assets", f"si-{name}-{view}-{key}.jpg"), "JPEG", quality=88)
            print(name, view, art.outcome, out[f"{name}/{view}"]["method"], art.status_counts)
    with open(os.path.join(HERE, "engine.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
