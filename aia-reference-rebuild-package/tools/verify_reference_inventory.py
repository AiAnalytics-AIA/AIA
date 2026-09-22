#!/usr/bin/env python3
"""Verify the reference rebuild package for internal consistency.

Runs from the committed manifest alone, so it works in CI without the reference
tree present. With --reference it additionally re-hashes the real tree.

Checks (each one exists because its absence would let something disappear
quietly):

  C1  every manifest file appears in the inventory
  C2  every inventory record appears in the manifest       (no invented files)
  C3  no duplicate inventory ids
  C4  every record carries a SHA256 of the right shape
  C5  every record has a category, and none is `unknown`
  C6  every record has a disposition from the permitted set
  C7  no production-relevant record is still UNKNOWN_NEEDS_DECISION
  C8  capability-map file references all resolve to inventory ids
  C9  inventory counts match the manifest's canonical_file_count
  C10 (--reference only) every file hashes to its manifest value

Exit 0 = all checks pass. Exit 1 = at least one failed. Exit 2 = bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PERMITTED_DISPOSITIONS = frozenset(
    {
        "PORTED",
        "REIMPLEMENTED",
        "REPLACED",
        "DEFERRED",
        "DATA_ASSET",
        "TEST_CHARACTERIZATION",
        "TOOLING_ONLY",
        "SUPERSEDED_LEGACY",
        "INTENTIONALLY_RETIRED",
        "UNKNOWN_NEEDS_DECISION",
    }
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Report:
    def __init__(self) -> None:
        self.failed = 0
        self.passed = 0

    def check(self, code: str, name: str, problems: list[str], *, limit: int = 10) -> None:
        if problems:
            print(f"FAIL  {code}  {name}  ({len(problems)})")
            for problem in problems[:limit]:
                print(f"        {problem}")
            if len(problems) > limit:
                print(f"        ... and {len(problems) - limit} more")
            self.failed += 1
        else:
            print(f"ok    {code}  {name}")
            self.passed += 1

    def skip(self, code: str, name: str, why: str) -> None:
        print(f"skip  {code}  {name}  ({why})")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/migration/reference-manifest.json"))
    parser.add_argument("--package", type=Path, default=Path("aia-reference-rebuild-package"))
    parser.add_argument("--reference", type=Path, default=None, help="optional: re-hash the real tree")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    inventory_path = args.package / "reference-file-inventory.json"
    if not inventory_path.is_file():
        print(f"inventory not found: {inventory_path}", file=sys.stderr)
        print("run tools/build_reference_inventory.py first", file=sys.stderr)
        return 2

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest_files: dict[str, str] = manifest["files"]
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = inventory["files"]

    print(f"evidence mode : {inventory.get('evidence_mode')}")
    print(f"manifest      : {args.manifest} ({len(manifest_files)} files)")
    print(f"inventory     : {inventory_path} ({len(records)} records)")
    print()

    report = Report()
    ids = [record["id"] for record in records]
    id_set = set(ids)

    report.check("C1", "every manifest file is inventoried",
                 sorted(set(manifest_files) - id_set))
    report.check("C2", "no inventory record is absent from the manifest",
                 sorted(id_set - set(manifest_files)))
    report.check("C3", "no duplicate inventory ids",
                 sorted({i for i in ids if ids.count(i) > 1}))
    report.check("C4", "every record carries a well-formed SHA256",
                 [r["id"] for r in records
                  if not isinstance(r.get("sha256"), str) or not SHA256_RE.match(r["sha256"])])
    report.check("C5", "every record has a known category",
                 [r["id"] for r in records if not r.get("category") or r["category"] == "unknown"])
    report.check("C6", "every disposition is from the permitted set",
                 [f"{r['id']}: {r.get('disposition')!r}" for r in records
                  if r.get("disposition") not in PERMITTED_DISPOSITIONS])
    report.check("C7", "no production-relevant record is still UNKNOWN_NEEDS_DECISION",
                 [r["id"] for r in records
                  if r.get("production_relevant") is True
                  and r.get("disposition") == "UNKNOWN_NEEDS_DECISION"])

    capability_map = args.package / "capability-map.json"
    if capability_map.is_file():
        data = json.loads(capability_map.read_text(encoding="utf-8"))
        dangling: list[str] = []
        for capability in data.get("capabilities", []):
            for ref in capability.get("reference_files", []):
                if ref not in id_set:
                    dangling.append(f"{capability.get('id', '?')} -> {ref}")
        report.check("C8", "capability-map file references resolve", dangling)
    else:
        report.skip("C8", "capability-map file references resolve", "capability-map.json not present yet")

    declared = manifest.get("canonical_file_count")
    report.check("C9", "inventory count matches the manifest's canonical_file_count",
                 [] if declared in (None, len(records))
                 else [f"manifest says {declared}, inventory has {len(records)}"])

    if args.reference is not None:
        if not args.reference.is_dir():
            print(f"reference tree not found: {args.reference}", file=sys.stderr)
            return 2
        mismatches: list[str] = []
        for rel, expected in sorted(manifest_files.items()):
            candidate = args.reference / rel
            if not candidate.is_file():
                mismatches.append(f"{rel}: missing from the tree")
            elif sha256_of(candidate) != expected:
                mismatches.append(f"{rel}: hash differs from the manifest")
        report.check("C10", "reference tree hashes match the manifest", mismatches)
    else:
        report.skip("C10", "reference tree hashes match the manifest",
                    "no --reference given; manifest-only run")

    print()
    unknown = sum(1 for r in records if r.get("disposition") == "UNKNOWN_NEEDS_DECISION")
    undetermined = sum(1 for r in records if r.get("production_relevant") == "undetermined")
    print(f"UNKNOWN_NEEDS_DECISION : {unknown} of {len(records)}")
    print(f"production-relevance undetermined : {undetermined} of {len(records)}")
    if unknown:
        print("\nThe audit is NOT complete while any record is UNKNOWN_NEEDS_DECISION.")
        print("Resolving them requires the reference tree: disposition is a claim")
        print("about behaviour, and behaviour is not knowable from a path and a hash.")

    print()
    if report.failed:
        print(f"verify: FAILED ({report.failed} failed, {report.passed} passed)")
        return 1
    print(f"verify: {report.passed} checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
