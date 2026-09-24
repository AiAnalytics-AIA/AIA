"""Run the vendored 18.6.6 ui_server.py on a scratch copy, with a fictional panel.

WORKBENCH ONLY. The licence-bound population panel is not in the repository
(data-manifest.json; it is hydrated from EU object storage on develop). Without
it the interface stops at /api/bootstrap. This replaces the panel loader with a
60-row frame whose every respondent is `FIKTIVNI-###` in a `Fiktivní kraj`, so
the real ui_app.html boots and every screen can be drawn for design work.

Nothing it shows is data. It is never used for parity: that is
tools/legacy_oracle.py against the running unit (ADR 0011).

Run from the scratch copy's directory, under the workbench venv:
    python unit_standin.py --port 8767
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

# The names population_context.py registers as STATIC and LIVE. It registers them
# on first use, which is at import, so the files must exist before the import.
PANEL_FILES = ("FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz", "FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz")


def fictional_panel():  # type: ignore[no-untyped-def]
    """A frame with the columns the unit's code reads, every value invented.

    Column names come from the unit's own code and its in-tree labels
    (PERSONA_VALUE_LABELS_v17.json); no value comes from the panel.
    """
    import json

    import pandas as pd

    n = 60
    cols: dict[str, list[object]] = {
        "respondent_id": [f"FIKTIVNI-{i:03d}" for i in range(n)],
        "panel_row_id": list(range(n)),
        "pohlavi": ["muž", "žena"] * (n // 2),
        "vek": [18 + (i * 7) % 60 for i in range(n)],
        "kraj": ["Fiktivní kraj A", "Fiktivní kraj B", "Fiktivní kraj C"] * (n // 3),
        "vzdelani": ["základní", "SŠ", "VŠ"] * (n // 3),
    }
    for flag in ("is_parent", "is_student", "is_employed", "has_partner"):
        cols[flag] = [(i * 5 + len(flag)) % 2 for i in range(n)]
    for weight in (
        "vaha_strukturalni_2025",
        "vaha_populace_2025_aprox",
        "vaha_kalibrovana",
        "vaha_strana_2021_benchmark",
    ):
        cols[weight] = [1.0] * n
    scale_1_10 = [
        "smartphone_use_intensity_1_10",
        "computer_use_intensity_1_10",
        "digital_communication_intensity_1_10",
        "online_information_intensity_1_10",
        "online_entertainment_intensity_1_10",
        "online_transactions_intensity_1_10",
        "digital_personal_management_intensity_1_10",
        "tv_intensity_1_10",
        "radio_intensity_1_10",
        "print_intensity_1_10",
        "social_media_intensity_1_10",
        "gaming_intensity_1_10",
        "travel_intensity_1_10",
        "sport_activity_1_10",
        "outdoor_activity_1_10",
        "socializing_offline_1_10",
        "dining_out_1_10",
        "culture_activity_1_10",
        "nightlife_1_10",
        "diy_home_activity_1_10",
        "cooking_activity_1_10",
        "price_sensitivity_1_10",
        "deal_proneness_1_10",
        "premium_willingness_1_10",
        "status_consumption_1_10",
        "research_orientation_1_10",
        "review_reliance_1_10",
        "convenience_orientation_1_10",
        "social_proof_susceptibility_1_10",
        "influencer_receptivity_1_10",
        "authority_receptivity_1_10",
        "scarcity_response_1_10",
        "tv_ad_attention_1_10",
        "social_ad_attention_1_10",
        "search_ad_attention_1_10",
        "advertising_skepticism_1_10",
        "reactance_1_10",
        "ad_avoidance_1_10",
        "financial_capability_1_10",
    ]
    labels = json.loads(Path("PERSONA_VALUE_LABELS_v17.json").read_text(encoding="utf-8"))
    for k, name in enumerate(scale_1_10):
        cols[name] = [1 + (i * 3 + k) % 10 for i in range(n)]
    for k, name in enumerate(labels.get("variables", {})):
        cols.setdefault(name, [(i + k) % 11 for i in range(n)])
    return pd.DataFrame(cols)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8767)
    args = ap.parse_args(argv)

    here = Path.cwd()
    if not (here / "ui_server.py").exists():
        print("unit_standin: run from the workbench's scratch copy of app/", file=sys.stderr)
        return 2
    if "legacy/npc-panel-18.6.6/app" in here.as_posix():
        print("unit_standin: refusing to run inside the frozen vendored unit", file=sys.stderr)
        return 2

    frame = fictional_panel()
    for name in PANEL_FILES:
        frame.to_csv(here / name, index=False)

    sys.path.insert(0, str(here))
    import prototype_server as core  # the unit's own module, from the scratch copy

    core.load_panel_cached = lambda panel_path=None: frame

    sys.argv = ["ui_server.py", "--host", "127.0.0.1", "--port", str(args.port), "--no-open"]
    runpy.run_path(str(here / "ui_server.py"), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
