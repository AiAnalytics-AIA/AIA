#!/usr/bin/env python3
"""Check that a source-only commit cannot rebuild the Python images' dependency layer.

    python3 tools/dockerfile_layers.py [deploy/docker/python.Dockerfile]

Every deploy used to add about 1 GB to the develop host (.planning/plans/
image-build-layers.md): the dependency install read the packages' sources, and a
per-commit build argument sat above the venv copy. Stdlib only; reads the
Dockerfile as text. What it asserts:

* The ``deps`` stage reads nothing from the build context but ``pyproject.toml``
  files: no other COPY or ADD from the context, no bind mount.
* The ``runtime`` stage, which every target builds on, copies nothing from the build
  context and declares no per-commit argument (``AIA_BUILD_SHA``,
  ``AIA_BUILD_TIME``).
* In each target, a per-commit argument is declared only after the target's last
  RUN, COPY or ADD: a build argument is in every later RUN's environment, so one
  declared earlier makes that RUN, and every layer after it, new on every commit.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent.parent / "deploy/docker/python.Dockerfile"
PER_COMMIT = frozenset({"AIA_BUILD_SHA", "AIA_BUILD_TIME"})
TARGETS = ("api", "worker")
LAYER = frozenset({"RUN", "COPY", "ADD"})


@dataclass
class Stage:
    name: str
    base: str
    instructions: list[tuple[str, str]] = field(default_factory=list)


def parse(text: str) -> dict[str, Stage]:
    """The stages by name, each with its instructions as (KEYWORD, arguments)."""
    logical: list[str] = []
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not current and (not line or line.startswith("#")):
            continue
        if current and line.startswith("#"):
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        logical.append(current + line)
        current = ""
    stages: dict[str, Stage] = {}
    stage: Stage | None = None
    for line in logical:
        keyword, _, args = line.partition(" ")
        keyword = keyword.upper()
        if keyword == "FROM":
            match = re.match(r"(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", args.strip(), re.I)
            if match is None:
                raise ValueError(f"unreadable FROM: {line}")
            name = match.group(2) or f"stage{len(stages)}"
            stage = Stage(name=name, base=match.group(1))
            stages[name] = stage
        elif stage is not None:
            stage.instructions.append((keyword, args.strip()))
    return stages


def _context_sources(keyword: str, args: str) -> list[str]:
    """The build-context paths a COPY or ADD reads; none when it copies from a stage."""
    words = args.split()
    if any(w.startswith("--from=") for w in words):
        return []
    paths = [w for w in words if not w.startswith("--")]
    return paths[:-1]


def _declared_args(args: str) -> set[str]:
    return {word.split("=", 1)[0] for word in args.split()}


def check(text: str) -> list[str]:
    """Every rule the Dockerfile breaks, in words; empty when it keeps them all."""
    stages = parse(text)
    problems: list[str] = []
    for required in ("deps", "runtime", *TARGETS):
        if required not in stages:
            problems.append(f"no stage named {required!r}")
    if problems:
        return problems

    for keyword, args in stages["deps"].instructions:
        if keyword in ("COPY", "ADD"):
            for source in _context_sources(keyword, args):
                if not source.endswith("pyproject.toml"):
                    problems.append(f"deps reads {source!r} from the build context")
        if keyword == "RUN" and "--mount=" in args:
            problems.append("deps mounts something into a RUN")

    for keyword, args in stages["runtime"].instructions:
        if keyword in ("COPY", "ADD") and _context_sources(keyword, args):
            problems.append(f"runtime copies from the build context: {keyword} {args}")
        if keyword == "ARG" and _declared_args(args) & PER_COMMIT:
            problems.append(f"runtime declares a per-commit argument: ARG {args}")

    for target in TARGETS:
        stage = stages[target]
        if stage.base != "runtime":
            problems.append(f"{target} is not built on runtime")
        last_layer = max(
            (i for i, (keyword, _) in enumerate(stage.instructions) if keyword in LAYER),
            default=-1,
        )
        for i, (keyword, args) in enumerate(stage.instructions):
            if keyword == "ARG" and _declared_args(args) & PER_COMMIT and i < last_layer:
                problems.append(f"{target} declares ARG {args} before a layer")
    return problems


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    problems = check(path.read_text(encoding="utf-8"))
    for problem in problems:
        print(f"{path}: {problem}", file=sys.stderr)
    if not problems:
        print(f"{path}: a source-only change leaves the dependency layer as it is")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
