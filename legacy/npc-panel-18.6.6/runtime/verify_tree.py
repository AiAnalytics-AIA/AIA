#!/usr/bin/env python3
"""Verify an extracted NPC Panel 18.6.6 tree against the reference identity.

Run before the tree is started so that the baseline is provably the audited
snapshot and not a drifted copy. Three tiers:

  identity  VERSION plus the entry-point files whose hash defines this
            release (ui_server.py, ui_app.html, worker_daemon.py, ...).
            Any mismatch is a failure: this is not 18.6.6.
  assets    the 22 runtime-critical data assets listed in SHA256SUMS.txt.
            Any mismatch is a failure: results would not be comparable.
  sweep     every other inventoried file. Mutable application state
            (SQLite databases, logs, outputs) is excluded. Differences are
            reported, not failed, because running the reference legitimately
            rewrites some of its own files.

Exit codes: 0 verified · 1 identity or asset failure · 2 usage error.
A JSON summary is written to <tree>/logs/tree-verification.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

EXPECTED_VERSION = "18.6.6"

IDENTITY_FILES = (
    "VERSION",
    "ui_server.py",
    "ui_app.html",
    "worker_daemon.py",
    "worker_job.py",
    "prototype_server.py",
    "launcher_bootstrap.py",
    "requirements.txt",
    "BUILD_EDITION.json",
    "edition_config.py",
    "research_os_config.py",
    "runtime_config.py",
)

# Inventory categories and path prefixes that the reference rewrites when it
# runs. They are never failed and are excluded from the sweep.
MUTABLE_CATEGORIES = {"database"}
MUTABLE_PREFIXES = ("data/", "logs/", "prototype_outputs/", "diagnostics/", "runs/", ".npc_runtime/")

SUMS_LINE = re.compile(r"^([0-9a-f]{64})\s+(.+?)\s*(?:#.*)?$")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_asset_sums(sums_path: Path) -> dict[str, str]:
    """Return {relative path: sha256} for the in-archive assets in SHA256SUMS.txt."""
    out: dict[str, str] = {}
    for raw in sums_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = SUMS_LINE.match(line)
        if not m:
            continue
        digest, rel = m.group(1), m.group(2).strip()
        if rel.lower().endswith(".zip"):
            continue  # the archive itself, not a file inside the tree
        out[rel] = digest
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tree", type=Path, help="extracted 18.6.6 tree (contains ui_server.py)")
    ap.add_argument("--sums", type=Path, default=Path("/opt/aia-reference/SHA256SUMS.txt"))
    ap.add_argument("--inventory", type=Path,
                    default=Path("/opt/aia-reference/reference-file-inventory.json"))
    ap.add_argument("--no-sweep", action="store_true", help="skip the full inventory sweep")
    ap.add_argument("--report", type=Path, help="where to write the JSON summary")
    args = ap.parse_args(argv)

    tree: Path = args.tree
    if not tree.is_dir():
        print(f"error: {tree} is not a directory", file=sys.stderr)
        return 2
    if not args.sums.is_file() or not args.inventory.is_file():
        print("error: SHA256SUMS.txt or reference-file-inventory.json not found", file=sys.stderr)
        return 2

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    inv_by_path = {f["path"]: f for f in inventory["files"]}
    asset_sums = load_asset_sums(args.sums)

    failures: list[str] = []
    notes: list[str] = []
    summary: dict = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tree": str(tree),
        "expected_zip_sha256": inventory.get("source_zip_sha256"),
        "identity": {},
        "assets": {},
        "sweep": None,
    }

    # --- identity -----------------------------------------------------------
    version_file = tree / "VERSION"
    declared = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else None
    summary["declared_version"] = declared
    if declared != EXPECTED_VERSION:
        failures.append(f"VERSION is {declared!r}, expected {EXPECTED_VERSION!r}")

    for rel in IDENTITY_FILES:
        rec = inv_by_path.get(rel)
        p = tree / rel
        if rec is None:
            notes.append(f"{rel}: not in inventory (skipped)")
            continue
        if not p.is_file():
            failures.append(f"identity file missing: {rel}")
            summary["identity"][rel] = "MISSING"
            continue
        actual = sha256_of(p)
        ok = actual == rec["sha256"]
        summary["identity"][rel] = "OK" if ok else f"MISMATCH {actual[:12]}… != {rec['sha256'][:12]}…"
        if not ok:
            failures.append(f"identity file differs from 18.6.6: {rel}")

    # --- runtime assets -----------------------------------------------------
    for rel, digest in sorted(asset_sums.items()):
        p = tree / rel
        if not p.is_file():
            failures.append(f"runtime asset missing: {rel}")
            summary["assets"][rel] = "MISSING"
            continue
        actual = sha256_of(p)
        ok = actual == digest
        summary["assets"][rel] = "OK" if ok else "MISMATCH"
        if not ok:
            failures.append(f"runtime asset differs from 18.6.6: {rel}")

    # --- full sweep (informational) -----------------------------------------
    if not args.no_sweep:
        present = changed = missing = 0
        changed_paths: list[str] = []
        missing_paths: list[str] = []
        for rel, rec in inv_by_path.items():
            if rec.get("category") in MUTABLE_CATEGORIES or rel.startswith(MUTABLE_PREFIXES):
                continue
            p = tree / rel
            if not p.is_file():
                missing += 1
                missing_paths.append(rel)
                continue
            present += 1
            if sha256_of(p) != rec["sha256"]:
                changed += 1
                changed_paths.append(rel)
        summary["sweep"] = {
            "inventoried_immutable_files": present + missing,
            "present": present,
            "changed": changed,
            "missing": missing,
            "changed_paths": changed_paths[:50],
            "missing_paths": missing_paths[:50],
        }
        if changed or missing:
            notes.append(f"sweep: {changed} changed, {missing} missing "
                         f"(informational; see report for paths)")

    summary["failures"] = failures
    summary["notes"] = notes
    summary["verdict"] = "VERIFIED" if not failures else "FAILED"

    report = args.report or (tree / "logs" / "tree-verification.json")
    try:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:  # read-only tree: still print the verdict
        notes.append(f"could not write report: {exc}")

    ident_ok = sum(1 for v in summary["identity"].values() if v == "OK")
    asset_ok = sum(1 for v in summary["assets"].values() if v == "OK")
    print(f"[verify] version {declared!r} · identity {ident_ok}/{len(summary['identity'])} "
          f"· assets {asset_ok}/{len(asset_sums)} · verdict {summary['verdict']}")
    for n in notes:
        print(f"[verify] note: {n}")
    for f in failures:
        print(f"[verify] FAIL: {f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
