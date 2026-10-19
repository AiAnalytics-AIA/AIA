#!/usr/bin/env python3
"""Check .planning/plans/mvp-master-plan.md against the plan files it coordinates.

The master plan is a register; a register that nothing reads rots. This tool
reads it and the front-matter of every plan and fails when:

* a reference ``plan#ID`` names a plan or a chunk that does not exist;
* a plan that is not ``done`` is missing from §3, or §3 names a plan that does
  not exist, or a plan sits in more than one of §3.1, §3.2 and §3.3;
* an acceptance criterion (AC-01 to AC-15), a gap (G<n>) or an interface (I<n>)
  in §3.4, §5 or §6.1 has no chunk reference that resolves;
* a typed count in prose ("38 gaps", "twenty-six interfaces") disagrees with the
  rows, or a section heading carries a count;
* ``class-b-search-route`` is listed as core, or the new-plan table of §6.3 does
  not name the six child plans or a plan file is missing for one.

    python tools/master_check.py            # check, print the derived counts
    python tools/master_check.py --quiet    # check only

Stdlib only. Exit status 1 on any failure, else 0.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import progress

REPO = progress.REPO
MASTER = progress.PLANS / "mvp-master-plan.md"
SELF = "mvp-master-plan"

_REF = re.compile(r"`([a-z0-9][a-z0-9-]*)#([A-Za-z0-9.]+)`")
_NUMBER_WORDS = {"twenty-six": 26, "thirty-eight": 38, "fifteen": 15, "six": 6}


def chunk_ids(plan: progress.Plan) -> set[str]:
    return {text.split(" ", 1)[0].rstrip(".") for _, text in plan.chunks}


def section(text: str, start: str, end: str) -> str:
    a = text.index(start)
    b = text.index(end, a + len(start)) if end else len(text)
    return text[a:b]


def table_rows(block: str) -> list[list[str]]:
    rows = []
    for line in block.splitlines():
        if line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    files = [f for f in sorted(progress.PLANS.glob("*.md")) if f.name != "README.md"]
    plans = {f.stem: progress.parse(f) for f in files}
    ids = {name: chunk_ids(p) for name, p in plans.items()}
    text = MASTER.read_text(encoding="utf-8")
    failures: list[str] = []

    # 1. every plan#ID reference resolves
    refs = _REF.findall(text)
    for plan, cid in sorted(set(refs)):
        if plan not in plans:
            failures.append(f"reference `{plan}#{cid}`: no such plan")
        elif cid not in ids[plan]:
            failures.append(f"reference `{plan}#{cid}`: {plan} has no chunk {cid}")

    # 2. the register
    s31 = section(text, "### 3.1 ", "### 3.2 ")
    s32 = section(text, "### 3.2 ", "### 3.3 ")
    s33 = section(text, "### 3.3 ", "### 3.4 ")
    named: dict[str, list[str]] = {"3.1": [], "3.2": [], "3.3": []}
    for key, block in (("3.1", s31), ("3.2", s32), ("3.3", s33)):
        for row in table_rows(block)[1:]:
            named[key] += re.findall(r"`([a-z0-9][a-z0-9-]*)`", row[0])
    seen: dict[str, str] = {}
    for key, lst in named.items():
        for name in lst:
            if name not in plans:
                failures.append(f"§{key} names `{name}`, which is not a plan file")
            if name in seen:
                failures.append(f"`{name}` is in §{seen[name]} and §{key}")
            seen[name] = key
    for name, plan in plans.items():
        if name != SELF and plan.status != "done" and name not in seen:
            failures.append(f"plan `{name}` ({plan.status}) is not in §3")
    if "class-b-search-route" in named["3.1"]:
        failures.append("`class-b-search-route` is deferred; it must not be in §3.1 (core)")

    # 3. AC, G and I rows each resolve to at least one chunk
    ac = table_rows(section(text, "### 3.4 ", "## 4. "))[1:]
    gaps = [
        r for r in table_rows(section(text, "### 6.1 ", "### 6.2 ")) if re.fullmatch(r"G\d+", r[0])
    ]
    ifaces = [
        r for r in table_rows(section(text, "## 5. ", "## 6. ")) if re.fullmatch(r"I\d+", r[0])
    ]
    wanted_ac = {f"AC-{n:02d}" for n in range(1, 16)}
    got_ac = {r[0] for r in ac}
    for missing in sorted(wanted_ac - got_ac):
        failures.append(f"{missing} is not in §3.4")
    for label, rows in (("AC", ac), ("gap", gaps), ("interface", ifaces)):
        for row in rows:
            if not _REF.search(" ".join(row[1:])):
                failures.append(f"{label} {row[0]} names no chunk")

    # 4. typed counts agree with the rows
    derived = {"gaps": len(gaps), "interfaces": len(ifaces)}
    for m in re.finditer(r"\b(\d+|twenty-six|thirty-eight) (gaps|interfaces)\b", text):
        n = int(m.group(1)) if m.group(1).isdigit() else _NUMBER_WORDS[m.group(1)]
        if n != derived[m.group(2)]:
            have = derived[m.group(2)]
            failures.append(f"prose says {m.group(1)} {m.group(2)}; the table has {have}")
    for line in text.splitlines():
        if line.startswith("### ") and re.search(r"\(\d+\)\s*$", line):
            failures.append(f"heading carries a typed count: {line}")

    # 5. the new plans of §6.3
    s63 = section(text, "### 6.3 ", "## 7. ")
    new_plans = [r[0].strip("`") for r in table_rows(s63)[1:]]
    if len(new_plans) != 6:
        failures.append(f"§6.3 names {len(new_plans)} new plans; the plan says six")
    for name in new_plans:
        if name not in plans:
            failures.append(f"§6.3 names `{name}`: no plan file")
    m13 = next((t for _, t in plans[SELF].chunks if t.startswith("M13.")), "")
    if "six" not in m13:
        failures.append("chunk M13 must say six child plans")

    if not args.quiet:
        counts = {k: len(v) for k, v in named.items()}
        opened = sum(1 for p in plans.values() if p.status != "done")
        print(f"plans: {len(plans)} files, {opened} not done")
        print(
            f"register: core {counts['3.1']}, outside the development plan "
            f"{counts['3.2']}, post-MVP {counts['3.3']}"
        )
        print(
            f"rows: {len(gaps)} gaps, {len(ifaces)} interfaces, {len(ac)} acceptance "
            f"criteria; {len(set(refs))} distinct chunk references"
        )
    if failures:
        print(f"\n{len(failures)} problem(s):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("master plan register: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
