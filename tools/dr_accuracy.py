#!/usr/bin/env python3
"""Deep Research accuracy on a truth set, and its verifier's on a gold set (plan chunks 25, 48).

    python tools/dr_accuracy.py check --truth <set.json>
    python tools/dr_accuracy.py pin   --truth <set.json> --by <name> [--at YYYY-MM-DD]
                                      [--pins <manifest>]
    python tools/dr_accuracy.py score --truth <set.json> --run <bundle-or-run.json> [--run …]
                                      --out <report.json> [--preset NAME] [--pins <manifest>]
                                      [--allow-unverified] [--allow-uncommitted-pins]
    python tools/dr_accuracy.py calibrate --gold <gold.json> --answers <answers.json>
                                      --out <report.json>

``check`` validates a truth set and says what stands between it and a pin: the
facts not verified, the facts without a question, value, period or place.

``pin`` records the set's hash in the manifest (default
``docs/evaluation/deep-research/truth-set-pins.json``). It refuses a real set with
an unverified fact, and a set id already pinned at another hash. Commit the
manifest before any run: that is what "fixed and recorded before any run" means.

``score`` refuses a set whose hash the manifest does not pin, a manifest that is
not committed (tracked and unchanged in git), and unverified facts -- each with
one exception, for fictional sets only: ``--allow-unverified`` and
``--allow-uncommitted-pins``. A run file is a sealed evidence bundle
(``"kind": "deep_research_bundle"``, its seal checked) or a run record
(``"kind": "deep_research_accuracy_run"``). ``--preset`` makes the command refuse a
run of any other preset, so a mis-filed run cannot be pooled under the wrong one.
The report (JSON) is written to ``--out``; a short summary is printed.

``calibrate`` scores the independent verifier's answers over a gold set (chunk 48): its
miss rate (a bad finding judged supported) and false-alarm rate (a good one set aside),
each with its Wilson 95 % upper bound, against the proposed thresholds. The gold set's
hash is pinned by ``test_deep_research_calibration.py``; answers to another version of
it, or from another prompt or contract, are refused. ``RECORDED`` answers prove the
tooling and say so (``TOOLING_ONLY``); only ``LIVE`` answers meet or miss the thresholds,
and neither changes what runs record (``NOT_CALIBRATED``): a person does, with the live
measurement in the plan's § 13. This command calls no model: live answers are produced
elsewhere and brought here as a file.

Exit status: 0 done, 2 refused (the reason on stderr). Nothing leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from aia_core.domain.deep_research.accuracy import (
    BundleRefused,
    RunRecord,
    accuracy_report,
    render_summary,
    run_from_bundle,
)
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.calibration import (
    CalibrationRefused,
    GoldSet,
    VerifierAnswers,
    calibrate,
    render_calibration,
)
from aia_core.domain.deep_research.truth_set import (
    TruthSet,
    TruthSetPins,
    TruthSetRefused,
    add_pin,
    empty_pins,
    load_pins,
    load_truth_set,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PINS = ROOT / "docs" / "evaluation" / "deep-research" / "truth-set-pins.json"


class Refused(Exception):
    """The command refuses; the message says why."""


def _read_truth(path: Path) -> TruthSet:
    try:
        return load_truth_set(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise Refused(f"{path}: not a valid truth set: {exc}") from exc


def _read_pins(path: Path) -> TruthSetPins:
    if not path.exists():
        return empty_pins()
    try:
        return load_pins(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise Refused(f"{path}: not a valid pin manifest: {exc}") from exc


def _shown(path: Path) -> str:
    """A path as the manifest records it: relative to the repository when inside it."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def committed(path: Path) -> bool:
    """Whether ``path`` is tracked in this repository and unchanged against HEAD."""
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return False
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", str(resolved)],
        capture_output=True,
        check=False,
    )
    if tracked.returncode != 0:
        return False
    changed = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--", str(resolved)],
        capture_output=True,
        check=False,
    )
    return changed.returncode == 0


def _read_run(path: Path) -> RunRecord:
    try:
        text = path.read_text(encoding="utf-8")
        kind = json.loads(text).get("kind")
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise Refused(f"{path}: not a JSON object: {exc}") from exc
    try:
        if kind == "deep_research_bundle":
            return run_from_bundle(EvidenceBundle.model_validate_json(text))
        if kind == "deep_research_accuracy_run":
            return RunRecord.model_validate_json(text, strict=True)
    except (ValidationError, BundleRefused) as exc:
        raise Refused(f"{path}: {exc}") from exc
    raise Refused(f"{path}: kind {kind!r} is neither a bundle nor a run record")


def cmd_check(args: argparse.Namespace) -> int:
    truth = _read_truth(Path(args.truth))
    unverified = truth.unverified()
    unscorable = [f.fact_id for f in truth.facts if not f.scorable]
    print(f"{truth.set_id}: {len(truth.facts)} facts {dict(truth.topics())}")
    print(f"sha256 {truth.sha256()}")
    print("FICTIONAL" if truth.fictional else f"register {truth.register_version}")
    print(f"unverified: {len(unverified)}" + (f" ({', '.join(unverified)})" if unverified else ""))
    print(f"unscorable: {len(unscorable)}" + (f" ({', '.join(unscorable)})" if unscorable else ""))
    return 0


def cmd_pin(args: argparse.Namespace) -> int:
    truth_path = Path(args.truth)
    pins_path = Path(args.pins)
    truth = _read_truth(truth_path)
    pins = _read_pins(pins_path)
    at = date.fromisoformat(args.at) if args.at else date.today()
    try:
        updated = add_pin(pins, truth, path=_shown(truth_path), pinned_at=at, pinned_by=args.by)
    except TruthSetRefused as exc:
        raise Refused(str(exc)) from exc
    if updated == pins:
        print(f"{truth.set_id} is already pinned at {truth.sha256()}")
        return 0
    pins_path.parent.mkdir(parents=True, exist_ok=True)
    pins_path.write_text(
        json.dumps(updated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"pinned {truth.set_id} at {truth.sha256()} in {_shown(pins_path)}; commit it")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    truth = _read_truth(Path(args.truth))
    pins_path = Path(args.pins)
    if args.allow_uncommitted_pins and not truth.fictional:
        raise Refused("--allow-uncommitted-pins is for fictional sets only")
    if not args.allow_uncommitted_pins and not committed(pins_path):
        raise Refused(
            f"{_shown(pins_path)} is not committed (tracked and unchanged): the pin is what "
            "fixes the set before a run"
        )
    pins = _read_pins(pins_path)
    runs = [_read_run(Path(p)) for p in args.run]
    if args.preset is not None:
        wrong = [r.run_id for r in runs if r.preset != args.preset]
        if wrong:
            raise Refused(f"run(s) {', '.join(wrong)} are not of preset {args.preset}")
    try:
        report = accuracy_report(truth, pins, runs, allow_unverified=args.allow_unverified)
    except TruthSetRefused as exc:
        raise Refused(str(exc)) from exc
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(render_summary(report))
    print(f"report: {out}")
    return 0


def _read_model[T: (GoldSet, VerifierAnswers)](path: Path, model: type[T], what: str) -> T:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise Refused(f"{path}: not a valid {what}: {exc}") from exc


def cmd_calibrate(args: argparse.Namespace) -> int:
    gold = _read_model(Path(args.gold), GoldSet, "gold set")
    answers = _read_model(Path(args.answers), VerifierAnswers, "verifier answers file")
    try:
        report = calibrate(gold, answers)
    except CalibrationRefused as exc:
        raise Refused(str(exc)) from exc
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(render_calibration(report))
    print(f"report: {out}")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="validate a truth set and say what blocks its pin")
    check.add_argument("--truth", required=True)
    check.set_defaults(func=cmd_check)
    pin = sub.add_parser("pin", help="record a truth set's hash in the pin manifest")
    pin.add_argument("--truth", required=True)
    pin.add_argument("--pins", default=str(DEFAULT_PINS))
    pin.add_argument("--by", required=True, help="who fixes the set")
    pin.add_argument("--at", help="the date it is fixed (YYYY-MM-DD; default today)")
    pin.set_defaults(func=cmd_pin)
    score = sub.add_parser("score", help="score runs against a pinned truth set")
    score.add_argument("--truth", required=True)
    score.add_argument("--pins", default=str(DEFAULT_PINS))
    score.add_argument("--run", action="append", required=True, help="a bundle or run record")
    score.add_argument("--out", required=True, help="where the JSON report is written")
    score.add_argument("--preset", help="refuse any run of another preset")
    score.add_argument("--allow-unverified", action="store_true", help="fictional sets only")
    score.add_argument("--allow-uncommitted-pins", action="store_true", help="fictional only")
    score.set_defaults(func=cmd_score)
    cal = sub.add_parser("calibrate", help="score the verifier's answers over a gold set")
    cal.add_argument("--gold", required=True)
    cal.add_argument("--answers", required=True)
    cal.add_argument("--out", required=True, help="where the JSON report is written")
    cal.set_defaults(func=cmd_calibrate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        status: int = args.func(args)
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return status


if __name__ == "__main__":
    sys.exit(main())
