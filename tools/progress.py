#!/usr/bin/env python3
"""Print every plan's status, read from the plan files' own front-matter.

A feature's status lives in its plan file, never in a shared index that every
PR edits (CLAUDE.md §1, §4). This tool is the index: it reads the front-matter
of ``.planning/plans/*.md`` and ``.planning/plans/done/*.md`` and prints one
table. Nothing it prints is committed, so it cannot conflict.

    ---
    status: in-progress        # planned | in-progress | done
    chunks:
      - "[x] 1. What landed"
      - "[ ] 2. What is next"
      - "[-] 3. Dropped or superseded, and by what"
    ---
    # <feature>

    python tools/progress.py            # the status table, in-progress first
    python tools/progress.py --check    # validate every plan's front-matter

``--check`` validates the front-matter only: both keys present, ``status`` one
of the three values, every chunk a quoted ``"[x] …"``, ``"[ ] …"`` or
``"[-] …"`` line, and no open chunk under ``status: done``. It compares nothing
against any committed file. Exit status: 1 when a plan is malformed, else 0.

Stdlib only, like the rest of ``tools/``: a checker that needs its own toolchain
gets disabled the first time that toolchain breaks.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLANS = REPO / ".planning" / "plans"

STATUSES = ("in-progress", "planned", "done")
_CHUNK = re.compile(r'^- "\[([ x-])\] (.+)"$')
_STATUS = re.compile(r"^status:\s*(\S+)\s*(#.*)?$")


@dataclass
class Plan:
    path: Path
    title: str = ""
    status: str = ""
    chunks: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def done(self) -> int:
        return sum(1 for mark, _ in self.chunks if mark == "x")

    @property
    def counted(self) -> int:
        """Chunks that are work: dropped ones (``[-]``) count as neither."""
        return sum(1 for mark, _ in self.chunks if mark != "-")

    @property
    def next_chunk(self) -> str:
        return next((text for mark, text in self.chunks if mark == " "), "")


def parse(path: Path) -> Plan:
    plan = Plan(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        plan.errors.append("no front-matter: the first line must be ---")
        return plan
    try:
        end = lines.index("---", 1)
    except ValueError:
        plan.errors.append("front-matter never closes with ---")
        return plan

    seen_status = seen_chunks = False
    in_chunks = False
    for number, raw in enumerate(lines[1:end], start=2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if in_chunks and (raw.startswith((" ", "\t")) or line.startswith("- ")):
            match = _CHUNK.match(line)
            if match is None:
                plan.errors.append(
                    f'line {number}: a chunk must read - "[x] …", "[ ] …" or "[-] …"'
                )
            else:
                plan.chunks.append((match.group(1), match.group(2).replace('\\"', '"')))
            continue
        in_chunks = False
        if line.startswith("status:"):
            seen_status = True
            match = _STATUS.match(line)
            value = match.group(1) if match else ""
            if value not in STATUSES:
                plan.errors.append(f"line {number}: status must be one of {', '.join(STATUSES)}")
            plan.status = value
        elif line == "chunks:":
            seen_chunks = in_chunks = True
        else:
            plan.errors.append(f"line {number}: unknown key {line.split(':', 1)[0]!r}")

    if not seen_status:
        plan.errors.append("missing status:")
    if not seen_chunks:
        plan.errors.append("missing chunks:")
    elif not plan.chunks:
        plan.errors.append("chunks: lists nothing")
    if plan.status == "done" and plan.next_chunk:
        plan.errors.append(f"status is done but a chunk is open: {plan.next_chunk!r}")

    plan.title = next(
        (line[2:].strip() for line in lines[end + 1 :] if line.startswith("# ")), path.stem
    )
    return plan


def plan_files(root: Path = PLANS) -> list[Path]:
    files = [*root.glob("*.md"), *(root / "done").glob("*.md")]
    return sorted(p for p in files if p.name != "README.md")


def _display(path: Path) -> str:
    return path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)


def render(plans: Sequence[Plan]) -> str:
    order = {status: i for i, status in enumerate(STATUSES)}
    rows = sorted(plans, key=lambda p: (order.get(p.status, len(order)), p.path.name))
    out = ["| Status | Plan | Chunks | Next |", "| --- | --- | ---: | --- |"]
    for plan in rows:
        status = plan.status or "?"
        out.append(
            f"| {status} | [{plan.title}]({_display(plan.path)}) "
            f"| {plan.done}/{plan.counted} | {plan.next_chunk} |"
        )
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="validate front-matter only")
    parser.add_argument("--plans", type=Path, default=PLANS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    plans = [parse(path) for path in plan_files(args.plans)]
    broken = [plan for plan in plans if plan.errors]
    if args.check:
        for plan in broken:
            for error in plan.errors:
                print(f"{_display(plan.path)}: {error}", file=sys.stderr)
        print(f"progress: {len(plans) - len(broken)} of {len(plans)} plans well-formed.")
        return 1 if broken else 0

    print(render(plans))
    if broken:
        print(f"\n{len(broken)} plan(s) malformed; run with --check.", file=sys.stderr)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
