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
  not name exactly the seven child plans or a plan file is missing for one;
* ``.planning/mvp-execution-contracts.md`` is inconsistent: a reference that does
  not resolve, a chunk assigned twice, a predecessor that is unknown, in a later
  wave or part of a cycle, or an open chunk of a core plan in neither the
  predecessor table nor the "every other open chunk" table.

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
CONTRACTS = REPO / ".planning" / "mvp-execution-contracts.md"
SELF = "mvp-master-plan"

NEW_PLANS = {
    "working-copy-edit-ops",
    "lead-orchestration",
    "run-qc-and-checkpoint",
    "report-delivery",
    "study-data-lifecycle",
    "production-environment",
    "assumptions-and-open-answer-coding",
}
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
    if set(new_plans) != NEW_PLANS or len(new_plans) != len(NEW_PLANS):
        gone = sorted(NEW_PLANS - set(new_plans))
        extra = sorted(set(new_plans) - NEW_PLANS)
        failures.append(
            f"§6.3 must name exactly the seven child plans: missing {gone}, unexpected {extra}"
        )
    for name in new_plans:
        if name not in plans:
            failures.append(f"§6.3 names `{name}`: no plan file")
    m13 = next((t for _, t in plans[SELF].chunks if t.startswith("MP13.")), "")
    if "seven" not in m13:
        failures.append("chunk MP13 must say seven child plans")

    # 6. the execution contracts: references, waves, predecessors, coverage
    ctext = CONTRACTS.read_text(encoding="utf-8")
    rows = [r for r in table_rows(ctext) if re.fullmatch(r"E\d+", r[0])]
    wave: dict[str, int] = {}
    graph: dict[str, list[str]] = {}
    assigned: dict[tuple[str, str], str] = {}
    for r in rows:
        wave[r[0]] = int(r[1][1:])
        graph[r[0]] = re.findall(r"E\d+", r[3])
        for plan, cid in _REF.findall(r[2]):
            if plan not in plans or cid not in ids[plan]:
                failures.append(f"{r[0]} names `{plan}#{cid}`, which does not exist")
            elif (plan, cid) in assigned:
                failures.append(f"`{plan}#{cid}` is in {assigned[(plan, cid)]} and {r[0]}")
            else:
                assigned[(plan, cid)] = r[0]
    for rid, needs in graph.items():
        for n in needs:
            if n not in wave:
                failures.append(f"{rid} needs {n}, which is not a row")
            elif wave[n] > wave[rid]:
                failures.append(f"{rid} (W{wave[rid]}) needs {n} (W{wave[n]}), a later wave")
    state: dict[str, int] = {}

    def visit(node: str, trail: list[str]) -> None:
        if state.get(node) == 1:
            failures.append("predecessor cycle: " + " -> ".join(trail))
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for nxt in graph.get(node, []):
            if nxt in graph:
                visit(nxt, [*trail, nxt])
        state[node] = 2

    for node in graph:
        visit(node, [node])
    rest = ctext[ctext.index("## Every other open chunk") :]
    rest = rest[: rest.index("\n## ", 5)]
    unscheduled = []
    for r in table_rows(rest)[1:]:
        found = _REF.findall(r[0])
        if not found or found[0][0] not in plans or found[0][1] not in ids[found[0][0]]:
            failures.append(f"execution contracts: row {r[0]} does not resolve")
            continue
        if found[0] in assigned:
            first = assigned[found[0]]
            failures.append(f"`{found[0][0]}#{found[0][1]}` is in {first} and the second table")
        assigned[found[0]] = "second table"
        if r[1] == "UNSCHEDULED":
            unscheduled.append(f"{found[0][0]}#{found[0][1]}")
    for name in named["3.1"]:
        for mark, text in plans[name].chunks:
            cid = text.split(" ", 1)[0].rstrip(".")
            if mark == " " and (name, cid) not in assigned:
                failures.append(f"open chunk `{name}#{cid}` has no wave in the execution contracts")

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
        print(f"execution contracts: {len(rows)} predecessor rows, {len(assigned)} chunks assigned")
        print(f"unscheduled (need a scope call): {len(unscheduled)}")
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
