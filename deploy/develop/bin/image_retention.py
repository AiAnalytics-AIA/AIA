#!/usr/bin/env python3
"""Local release image retention. No registry, container or volume deletion.

Standalone preflight is a dry run unless --apply is given. deploy.sh opts in
before pulling, and records successful releases only after its smoke test.
Python's stdlib and the host's Docker CLI are the only dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

KEEP_SUCCESSFUL = 4
MIN_FREE = 8 * 1024**3
MAX_USED = 85
AGE = timedelta(hours=48)
SHA = re.compile(r"[0-9a-f]{7,40}")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}")


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=120)


def history(path: Path) -> list[str]:
    if not path.exists():
        if path.is_symlink():
            raise ValueError("broken successful-release history; refusing image cleanup")
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("invalid successful-release history; refusing image cleanup")
    releases = data.get("releases")
    if not isinstance(releases, list) or any(
        not isinstance(s, str) or SHA.fullmatch(s) is None for s in releases
    ):
        raise ValueError("invalid successful-release SHA; refusing image cleanup")
    return list(dict.fromkeys(releases))[:KEEP_SUCCESSFUL]


def record(path: Path, sha: str, previous: str) -> None:
    for value in (sha, previous):
        if value and SHA.fullmatch(value) is None:
            raise ValueError("invalid release SHA")
    if not sha:
        raise ValueError("missing successful release SHA")
    releases = list(dict.fromkeys([sha, *([previous] if previous else []), *history(path)]))
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as file:
            temporary = file.name
            json.dump({"schema": 1, "releases": releases[:KEEP_SUCCESSFUL]}, file)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def inventory() -> tuple[list[dict[str, Any]], set[str]]:
    containers = command("docker", "ps", "--all", "--quiet").split()
    used: set[str] = set()
    for offset in range(0, len(containers), 64):
        container_batch = containers[offset : offset + 64]
        references = command(
            "docker", "inspect", "--format", "{{.Image}}", *container_batch
        ).split()
        if len(references) != len(container_batch):
            raise ValueError("incomplete container image inventory; refusing image cleanup")
        used.update(references)
    if any(IMAGE_ID.fullmatch(i) is None for i in used):
        raise ValueError("invalid container image inventory; refusing image cleanup")
    ids = list(
        dict.fromkeys(command("docker", "image", "ls", "--all", "--quiet", "--no-trunc").split())
    )
    images: list[dict[str, Any]] = []
    for offset in range(0, len(ids), 64):
        inspected = json.loads(command("docker", "image", "inspect", *ids[offset : offset + 64]))
        if not isinstance(inspected, list):
            raise ValueError("invalid Docker image inventory")
        images.extend(inspected)
    return images, used


def candidates(
    images: list[dict[str, Any]],
    used: set[str],
    registry: str,
    protected: list[str],
    now: datetime,
) -> list[dict[str, Any]]:
    if not registry or any(SHA.fullmatch(s) is None for s in protected):
        raise ValueError("missing registry or invalid protected release SHA")
    tag_pattern = re.compile(
        rf"{re.escape(registry.rstrip('/'))}/aia-(?:api|worker|web):([0-9a-f]{{40}})"
    )
    selected = []
    for image in images:
        if not isinstance(image, dict) or IMAGE_ID.fullmatch(image.get("Id", "")) is None:
            raise ValueError("invalid Docker image identity; refusing image cleanup")
        if image["Id"] in used:
            continue
        tags = image.get("RepoTags")
        if not isinstance(tags, list) or len(tags) != 1 or not isinstance(tags[0], str):
            continue  # A dangling or unknown image has no proven AIA ownership.
        matches = [tag_pattern.fullmatch(tag) for tag in tags]
        if not all(matches):
            continue  # Even one unrelated/floating alias protects the whole image.
        if any(m and any(m[1].startswith(s) for s in protected) for m in matches):
            continue
        try:
            created = datetime.fromisoformat(image["Created"].replace("Z", "+00:00"))
            if created.tzinfo is None or now - created < AGE:
                continue
        except (KeyError, TypeError, ValueError):
            continue  # Age cannot be established: keep it.
        selected.append(image)
    return selected


def check_disks(paths: list[Path]) -> None:
    checked: set[int] = set()
    for path in paths:
        if not path.exists():
            continue
        device = path.stat().st_dev
        if device in checked:
            continue
        checked.add(device)
        usage = shutil.disk_usage(path)
        # Free, not total-minus-used, accounts for filesystem-reserved blocks.
        available_total = usage.used + usage.free
        percent = 100 * usage.used / available_total if available_total else 100
        print(
            f"disk {path}: {usage.free / 1024**3:.1f} GiB available, {percent:.1f}% used",
            flush=True,
        )
        if usage.free < MIN_FREE or percent > MAX_USED:
            raise ValueError(
                f"insufficient deployment space on {path}: need at least 8 GiB free "
                "and usage no higher than 85%; no images were downloaded and no services "
                "were replaced. Review retained images or grow this filesystem "
                "(deploy/develop/README.md: Disk retention and Resize)."
            )
    if not checked:
        raise ValueError("no deployment filesystem could be checked")


def preflight(
    registry: str, state: Path, protected: list[str], apply: bool, deploy_dir: Path
) -> None:
    successes = history(state)
    retained = [*protected, *successes]
    images, used = inventory()
    selected = candidates(images, used, registry, retained, datetime.now(UTC))
    if len(successes) < KEEP_SUCCESSFUL:
        # A pre-policy host may hold older valid rollback images absent from our
        # ledger. Do not infer successful releases from image creation dates.
        print(
            "rollback history warming up: keep all images until four releases are recorded",
            flush=True,
        )
        selected = []
    docker_root = Path(command("docker", "info", "--format", "{{.DockerRootDir}}").strip())
    if not docker_root.is_absolute() or not docker_root.exists():
        raise ValueError("Docker storage filesystem could not be located; refusing deployment")
    print(
        f"image retention: {'apply' if apply else 'dry-run'}; {len(selected)} obsolete images; "
        f"{len(used)} container-referenced images protected; "
        f"releases {', '.join(retained) or 'none'}",
        flush=True,
    )
    for image in selected:
        print(
            f"{'remove' if apply else 'would remove'} {image['Id']} "
            f"({', '.join(image['RepoTags'])})",
            flush=True,
        )
        if apply:
            # Never force: Docker also refuses an image referenced by a container
            # created after the inventory. Delete its immutable ID, not a tag
            # that could move between inspection and deletion. Shared images
            # are retained; without --force Docker protects a newly added alias.
            command("docker", "image", "rm", "--no-prune", image["Id"])
    check_disks([Path("/"), docker_root, Path("/var/lib/containerd"), deploy_dir])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    before = sub.add_parser("preflight")
    before.add_argument("--registry", required=True)
    before.add_argument("--state-file", type=Path, required=True)
    before.add_argument("--protect", action="append", default=[])
    before.add_argument("--deploy-dir", type=Path, default=Path("/opt/aia/develop"))
    before.add_argument("--apply", action="store_true")
    after = sub.add_parser("record")
    after.add_argument("--state-file", type=Path, required=True)
    after.add_argument("--sha", required=True)
    after.add_argument("--previous", default="")
    args = parser.parse_args()
    try:
        if args.action == "record":
            record(args.state_file, args.sha, args.previous)
        else:
            preflight(args.registry, args.state_file, args.protect, args.apply, args.deploy_dir)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: deployment image/disk preflight: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
