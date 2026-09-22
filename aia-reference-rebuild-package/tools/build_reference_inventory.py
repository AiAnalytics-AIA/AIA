#!/usr/bin/env python3
"""Build the reference file inventory for the NPC Panel prototype.

Two modes, because the reference tree is not always present:

  TREE mode      --reference <path>    Walks the real reference tree. Produces
                                       the full inventory: path, size, SHA256,
                                       line count for text files, category, and
                                       cross-checks every hash against the
                                       committed manifest.

  MANIFEST mode  (default)             Derives what can be known from the
                                       committed manifest alone
                                       (docs/migration/reference-manifest.json):
                                       path and SHA256 per file, plus a category
                                       inferred from path and extension. Sizes,
                                       line counts and contents are NOT knowable
                                       in this mode and are emitted as null.

The distinction is recorded in every output as `evidence_mode`. A consumer must
never treat a MANIFEST-mode inventory as a content audit: it proves which files
exist and what they hash to, and nothing about what they do.

Non-destructive: reads only, writes only inside the output package.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# --- Categories ------------------------------------------------------------
#
# Category is a statement about file TYPE and location, which a path and an
# extension can support. It is deliberately not a statement about behaviour --
# that needs the contents, and is the job of the capability map.

CATEGORY_PYTHON_APP = "python_application_source"
CATEGORY_PYTHON_TEST = "python_test"
CATEGORY_PYTHON_TOOLING = "python_tooling"
CATEGORY_FRONTEND_HTML = "frontend_html"
CATEGORY_FRONTEND_JS = "frontend_javascript"
CATEGORY_CSS = "css"
CATEGORY_SQL = "sql"
CATEGORY_POLICY = "methodology_or_policy"
CATEGORY_JSON_DATA = "json_data_or_config"
CATEGORY_CSV_DATA = "csv_data_asset"
CATEGORY_COMPRESSED = "compressed_data_asset"
CATEGORY_DOCS = "documentation"
CATEGORY_LAUNCHER = "launcher_script"
CATEGORY_PACKAGING = "packaging"
CATEGORY_TEXT = "text"
CATEGORY_UNKNOWN = "unknown"

# Filename fragments that mark a machine-readable rule set rather than ordinary
# data. These files encode product methodology and are treated as first-class
# in the rebuild contract, so they are separated from bulk JSON here.
POLICY_MARKERS = (
    "PRODUCT_POLICY",
    "DATA_CONTRACT",
    "POLICY",
    "CONTRACT",
    "REGISTRY",
    "ACCEPTANCE",
    "GATE",
    "METHODOLOG",
    "CALIBRATION",
    "BENCHMARK",
    "HOLDOUT",
    "PRICING",
    "MODEL_POLICY",
    "DIMENSION",
)

TOOLING_DIRS = ("npc_tools/", "tools/", "npc_ingest/", "_npc_update_backup/")
TOOLING_PREFIXES = ("BUILD_", "MAKE_", "GENERATE_", "DIAG", "FIX_", "CHECK_")


def zone_of(relpath: str) -> str:
    """Where in the reference tree a file lives.

    Deliberately separate from category. An HTML file under demo_library/ is
    still an HTML file: folding location into type hid 74 of the prototype's 76
    HTML files behind a `demo_library_asset` label on the first build of this
    inventory, which is exactly the kind of silent disappearance this package
    exists to prevent.
    """
    return relpath.split("/", 1)[0] if "/" in relpath else "(root)"


def categorize(relpath: str) -> str:
    """Classify a reference file by TYPE, from its path alone."""
    lower = relpath.lower()
    name = relpath.rsplit("/", 1)[-1]
    upper_name = name.upper()
    suffix = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""

    if suffix == ".py":
        if lower.startswith("tests/") or name.startswith("test_") or name.endswith("_test.py"):
            return CATEGORY_PYTHON_TEST
        if any(lower.startswith(d) for d in TOOLING_DIRS):
            return CATEGORY_PYTHON_TOOLING
        if any(upper_name.startswith(p) for p in TOOLING_PREFIXES):
            return CATEGORY_PYTHON_TOOLING
        return CATEGORY_PYTHON_APP

    if suffix in (".bat", ".sh", ".ps1"):
        return CATEGORY_LAUNCHER
    if suffix == ".html":
        return CATEGORY_FRONTEND_HTML
    if suffix == ".js":
        return CATEGORY_FRONTEND_JS
    if suffix == ".css":
        return CATEGORY_CSS
    if suffix == ".sql":
        return CATEGORY_SQL
    if suffix == ".toml":
        return CATEGORY_PACKAGING
    if suffix == ".md":
        return CATEGORY_DOCS
    if suffix == ".gz":
        return CATEGORY_COMPRESSED
    if suffix == ".csv":
        return CATEGORY_CSV_DATA
    if suffix == ".json":
        if any(marker in upper_name for marker in POLICY_MARKERS):
            return CATEGORY_POLICY
        return CATEGORY_JSON_DATA
    if suffix == ".txt":
        return CATEGORY_TEXT
    return CATEGORY_UNKNOWN


# Categories whose disposition can be defended from path evidence alone.
# Everything else needs the file's contents and stays UNKNOWN_NEEDS_DECISION.
EVIDENCE_DISPOSITIONS: dict[str, tuple[str, str]] = {
    CATEGORY_PYTHON_TEST: (
        "TEST_CHARACTERIZATION",
        "path: lives under tests/ or is named test_*; its role is to characterise "
        "behaviour, whatever behaviour that turns out to be",
    ),
}


def sha256_of(path: Path) -> str:
    """Hash a file in chunks, so a large panel need not fit in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def line_count(path: Path) -> int | None:
    """Count lines in a text file, or None when it is not decodable text."""
    try:
        with path.open("r", encoding="utf-8", errors="strict") as handle:
            return sum(1 for _ in handle)
    except (UnicodeDecodeError, OSError):
        return None


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    with manifest_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def build_record(relpath: str, manifest_hash: str, *, mode: str, root: Path | None) -> dict[str, Any]:
    category = categorize(relpath)
    disposition, basis = EVIDENCE_DISPOSITIONS.get(
        category,
        (
            "UNKNOWN_NEEDS_DECISION",
            "contents not read: the reference tree was not available when this "
            "inventory was built",
        ),
    )

    record: dict[str, Any] = {
        "id": relpath,
        "path": relpath,
        "filename": relpath.rsplit("/", 1)[-1],
        "zone": zone_of(relpath),
        "extension": ("." + relpath.rsplit(".", 1)[-1].lower()) if "." in relpath.rsplit("/", 1)[-1] else "",
        "category": category,
        "sha256": manifest_hash,
        "size_bytes": None,
        "line_count": None,
        "production_relevant": "undetermined",
        "disposition": disposition,
        "disposition_basis": basis,
        "hash_verified_against_manifest": None,
        "notes": "",
    }

    if mode == "tree" and root is not None:
        actual = root / relpath
        if actual.is_file():
            record["size_bytes"] = actual.stat().st_size
            record["line_count"] = line_count(actual)
            actual_hash = sha256_of(actual)
            record["sha256"] = actual_hash
            record["hash_verified_against_manifest"] = actual_hash == manifest_hash
            if actual_hash != manifest_hash:
                record["notes"] = "HASH MISMATCH against committed manifest"
        else:
            record["notes"] = "listed in manifest but missing from the reference tree"
            record["hash_verified_against_manifest"] = False

    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("docs/migration/reference-manifest.json"),
        help="the committed reference manifest",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="path to the reference tree; omit to build in MANIFEST mode",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("aia-reference-rebuild-package"),
        help="output package directory",
    )
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    manifest = load_manifest(args.manifest)
    files: dict[str, str] = manifest["files"]

    root: Path | None = args.reference
    mode = "manifest"
    if root is not None:
        if not root.is_dir():
            print(f"reference tree not found: {root}", file=sys.stderr)
            return 2
        mode = "tree"

    records = [build_record(rel, sha, mode=mode, root=root) for rel, sha in sorted(files.items())]

    by_category: dict[str, int] = {}
    by_disposition: dict[str, int] = {}
    by_zone: dict[str, int] = {}
    for record in records:
        by_category[record["category"]] = by_category.get(record["category"], 0) + 1
        by_disposition[record["disposition"]] = by_disposition.get(record["disposition"], 0) + 1
        by_zone[record["zone"]] = by_zone.get(record["zone"], 0) + 1

    inventory = {
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence_mode": mode,
        "evidence_caveat": (
            "MANIFEST mode: paths and hashes are authoritative; sizes, line counts "
            "and every behavioural claim are NOT established, because the reference "
            "tree was not available. Re-run with --reference to complete."
            if mode == "manifest"
            else "TREE mode: built from the reference tree and cross-checked against the manifest."
        ),
        "manifest_path": str(args.manifest),
        "manifest_sha256": sha256_of(args.manifest),
        "manifest_canonical_file_count": manifest.get("canonical_file_count"),
        "record_count": len(records),
        "counts_by_category": dict(sorted(by_category.items())),
        "counts_by_zone": dict(sorted(by_zone.items())),
        "counts_by_disposition": dict(sorted(by_disposition.items())),
        "files": records,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "reference-file-inventory.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(inventory, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    csv_path = args.out / "reference-file-inventory.csv"
    columns = [
        "id", "path", "filename", "zone", "extension", "category", "sha256", "size_bytes",
        "line_count", "production_relevant", "disposition", "disposition_basis",
        "hash_verified_against_manifest", "notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)

    print(f"evidence mode : {mode}")
    print(f"records       : {len(records)}")
    print(f"wrote         : {json_path}")
    print(f"wrote         : {csv_path}")
    print("categories:")
    for name, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
        print(f"  {count:5d}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
