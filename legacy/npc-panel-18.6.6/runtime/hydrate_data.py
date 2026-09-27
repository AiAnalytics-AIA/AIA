#!/usr/bin/env python3
"""Hydrate the runtime data files into the working tree, with hash verification.

The extracted unit keeps licence-bound and bulky files out of app/ and out of
Git; ``data-manifest.json`` lists them with their SHA256. At container start
this copies each one from the data mount (``NPC_DATA_SOURCE``) to its place in
the tree, skipping files already present with the right hash, and refuses to
continue when one is missing or differs. State seeds are verified when first
installed; an existing working state database is never overwritten.

    hydrate_data.py <tree> --manifest data-manifest.json --source /data [--warn]

Exit codes: 0 hydrated · 1 missing or mismatched files (strict) · 2 usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tree", type=Path)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--source", type=Path, required=True, help="directory holding the data files at their relative paths")
    ap.add_argument("--warn", action="store_true", help="report problems but exit 0")
    ap.add_argument("--classes", default="", help="comma-separated classes to hydrate (default: all)")
    args = ap.parse_args(argv)

    if not args.manifest.is_file():
        print(f"error: no manifest at {args.manifest}", file=sys.stderr)
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    wanted = {c for c in args.classes.split(",") if c}
    entries = [e for e in manifest["files"] if not wanted or e.get("class") in wanted]

    if not args.source.is_dir():
        print(f"[hydrate] ERROR: data source {args.source} is not a directory; "
              f"{len(entries)} files cannot be hydrated", file=sys.stderr)
        return 0 if args.warn else 1

    copied = kept = unverified = 0
    missing: list[str] = []
    mismatched: list[str] = []
    for e in entries:
        rel, digest = e["path"], e["sha256"]
        target = args.tree / rel
        # State seeds initialise a new volume. The reference legitimately writes
        # these databases; their changed hash is not asset drift (verify_tree.py).
        # Replacing one here loses projects while AIA retains their bindings.
        if e.get("class") == "state_seed" and target.is_file():
            kept += 1
            continue
        if target.is_file() and sha256_of(target) == digest:
            kept += 1
            continue
        src = args.source / rel
        if not src.is_file():
            missing.append(rel)
            continue
        ok = sha256_of(src) == digest
        if not ok:
            mismatched.append(rel)
            if not args.warn:
                continue           # strict: never place a file that is not the audited one
            unverified += 1        # warn: place it, but say so
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        if ok:
            copied += 1

    print(f"[hydrate] {copied} copied · {kept} already present · {len(missing)} missing · "
          f"{len(mismatched)} mismatched"
          + (f" ({unverified} placed unverified, --warn)" if unverified else "")
          + f"  (source {args.source})")
    for rel in missing[:20]:
        print(f"[hydrate] MISSING    {rel}")
    for rel in mismatched[:20]:
        print(f"[hydrate] MISMATCH   {rel}")
    if (missing or mismatched) and not args.warn:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
