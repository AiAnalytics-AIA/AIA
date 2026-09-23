"""The image set is declared in three places; they must agree.

``deploy-develop.yml`` builds and pushes the images, ``deploy/develop/
docker-compose.yml`` pulls them on the host, and ``infra/develop/main.tf``
creates the ECR repositories **and** grants the deploy role's push, both from
``local.images``. When the workflow grew a fourth image (``aia-legacy-panel``,
ADR 0011) the Terraform list did not, so the build succeeded and the push was
refused with 403 on the first real deploy (OI-41).

Terraform does not run in CI (``infra/develop/README.md`` § Apply), so this is
the only check that fires before an operator applies. It reads the files as
text, without a YAML or HCL parser, and expects nothing outside the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "deploy-develop.yml"
COMPOSE = REPO / "deploy" / "develop" / "docker-compose.yml"
TERRAFORM = REPO / "infra" / "develop" / "main.tf"

# `${{ env.REGISTRY }}/aia-api:${{ env.SHA }}` in the workflow's `tags:` blocks.
_WORKFLOW_IMAGE = re.compile(r"\$\{\{\s*env\.REGISTRY\s*\}\}/([a-z0-9-]+):")
# `${AIA_IMAGE_REGISTRY}/aia-api:${AIA_IMAGE_TAG}` in the compose file.
_COMPOSE_IMAGE = re.compile(r"\$\{AIA_IMAGE_REGISTRY\}/([a-z0-9-]+):")
# `images = ["aia-api", ...]` in the Terraform locals block.
_TERRAFORM_IMAGES = re.compile(r"^\s*images\s*=\s*\[([^\]]*)\]", re.MULTILINE)


def _workflow_images() -> set[str]:
    return set(_WORKFLOW_IMAGE.findall(WORKFLOW.read_text(encoding="utf-8")))


def _compose_images() -> set[str]:
    return set(_COMPOSE_IMAGE.findall(COMPOSE.read_text(encoding="utf-8")))


def _terraform_images() -> set[str]:
    matches = _TERRAFORM_IMAGES.findall(TERRAFORM.read_text(encoding="utf-8"))
    assert len(matches) == 1, f"expected one `images = [...]` in {TERRAFORM}, found {len(matches)}"
    return set(re.findall(r'"([^"]+)"', matches[0]))


def test_the_three_declarations_name_at_least_one_image() -> None:
    # Guards the regexes: an edit that changes the quoting or the variable name
    # must fail loudly rather than turn the comparison below into {} == {}.
    assert _workflow_images(), f"no `env.REGISTRY` image tags found in {WORKFLOW}"
    assert _compose_images(), f"no `AIA_IMAGE_REGISTRY` images found in {COMPOSE}"
    assert _terraform_images(), f"no images in `local.images` in {TERRAFORM}"


def test_terraform_creates_and_grants_every_image_the_workflow_pushes() -> None:
    # An image the workflow pushes without a Terraform entry has no repository
    # and no push grant: ECR refuses the first layer with 403 (OI-41).
    missing = _workflow_images() - _terraform_images()
    assert not missing, f"pushed by the workflow, absent from local.images: {sorted(missing)}"


def test_the_workflow_builds_every_image_the_host_pulls() -> None:
    # An image the compose file pulls without a build step fails the deploy at
    # `compose pull` with "manifest unknown", after the other images were pushed.
    missing = _compose_images() - _workflow_images()
    assert not missing, f"pulled by the compose file, never built by the deploy: {sorted(missing)}"


def test_no_declaration_carries_an_image_the_others_dropped() -> None:
    # The reverse direction: a repository or a build step nobody deploys is a
    # leftover, and the next reader will wonder whether it is still meant.
    workflow, compose, terraform = _workflow_images(), _compose_images(), _terraform_images()
    assert workflow == compose == terraform, {
        "workflow": sorted(workflow),
        "compose": sorted(compose),
        "terraform": sorted(terraform),
    }
