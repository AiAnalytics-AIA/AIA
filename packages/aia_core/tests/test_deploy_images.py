"""The image sets are declared in five places; they must agree.

The product: ``deploy-develop.yml`` builds and pushes its images and
``deploy/develop/docker-compose.yml`` pulls them on the host. The 18.6.6
reference (ADR 0018 decision 5): ``reference-unit.yml`` builds the unit's image
and ``deploy/reference/docker-compose.yml`` pulls it. ``infra/develop/main.tf``
creates the ECR repositories **and** grants the deploy role's push, both from
``local.images``, for every image either workflow pushes. When the workflow grew
a fourth image (``aia-legacy-panel``, ADR 0011) the Terraform list did not, so
the build succeeded and the push was refused with 403 on the first real deploy
(OI-41).

Terraform does not run in CI (``infra/develop/README.md`` § Apply), so this is
the only check that fires before an operator applies. It reads the files as
text, without a YAML or HCL parser, and expects nothing outside the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"
PRODUCT_WORKFLOW = WORKFLOWS / "deploy-develop.yml"
REFERENCE_WORKFLOW = WORKFLOWS / "reference-unit.yml"
PRODUCT_COMPOSE = REPO / "deploy" / "develop" / "docker-compose.yml"
REFERENCE_COMPOSE = REPO / "deploy" / "reference" / "docker-compose.yml"
TERRAFORM = REPO / "infra" / "develop" / "main.tf"
UNIT_IMAGE = "aia-legacy-panel"

# `${{ env.REGISTRY }}/aia-api:${{ env.SHA }}` in a workflow's `tags:` blocks.
_WORKFLOW_IMAGE = re.compile(r"\$\{\{\s*env\.REGISTRY\s*\}\}/([a-z0-9-]+):")
# `${AIA_IMAGE_REGISTRY}/aia-api:${AIA_IMAGE_TAG}` in a compose file, with or
# without a `:?message` requirement on the registry.
_COMPOSE_IMAGE = re.compile(r"\$\{AIA_IMAGE_REGISTRY(?::\?[^}]*)?\}/([a-z0-9-]+):")
# `images = ["aia-api", ...]` in the Terraform locals block.
_TERRAFORM_IMAGES = re.compile(r"^\s*images\s*=\s*\[([^\]]*)\]", re.MULTILINE)


def _images(path: Path, pattern: re.Pattern[str]) -> set[str]:
    return set(pattern.findall(path.read_text(encoding="utf-8")))


def _terraform_images() -> set[str]:
    matches = _TERRAFORM_IMAGES.findall(TERRAFORM.read_text(encoding="utf-8"))
    assert len(matches) == 1, f"expected one `images = [...]` in {TERRAFORM}, found {len(matches)}"
    return set(re.findall(r'"([^"]+)"', matches[0]))


def _pushed() -> set[str]:
    return _images(PRODUCT_WORKFLOW, _WORKFLOW_IMAGE) | _images(REFERENCE_WORKFLOW, _WORKFLOW_IMAGE)


def test_every_declaration_names_at_least_one_image() -> None:
    # Guards the regexes: an edit that changes the quoting or the variable name
    # must fail loudly rather than turn the comparisons below into {} == {}.
    for path in (PRODUCT_WORKFLOW, REFERENCE_WORKFLOW):
        assert _images(path, _WORKFLOW_IMAGE), f"no `env.REGISTRY` image tags found in {path}"
    for path in (PRODUCT_COMPOSE, REFERENCE_COMPOSE):
        assert _images(path, _COMPOSE_IMAGE), f"no `AIA_IMAGE_REGISTRY` images found in {path}"
    assert _terraform_images(), f"no images in `local.images` in {TERRAFORM}"


def test_terraform_creates_and_grants_every_image_a_workflow_pushes() -> None:
    # An image a workflow pushes without a Terraform entry has no repository
    # and no push grant: ECR refuses the first layer with 403 (OI-41).
    missing = _pushed() - _terraform_images()
    assert not missing, f"pushed by a workflow, absent from local.images: {sorted(missing)}"


def test_each_host_stack_pulls_only_what_its_workflow_builds() -> None:
    # An image a compose file pulls without a build step fails at `compose pull`
    # with "manifest unknown", after the other images were pushed.
    for compose, workflow in (
        (PRODUCT_COMPOSE, PRODUCT_WORKFLOW),
        (REFERENCE_COMPOSE, REFERENCE_WORKFLOW),
    ):
        missing = _images(compose, _COMPOSE_IMAGE) - _images(workflow, _WORKFLOW_IMAGE)
        assert not missing, (
            f"pulled by {compose.name}, never built by {workflow.name}: {sorted(missing)}"
        )


def test_no_repository_or_build_step_is_a_leftover() -> None:
    # The reverse direction: a repository or a build step nobody deploys is a
    # leftover, and the next reader will wonder whether it is still meant.
    pulled = _images(PRODUCT_COMPOSE, _COMPOSE_IMAGE) | _images(REFERENCE_COMPOSE, _COMPOSE_IMAGE)
    assert _terraform_images() == _pushed() == pulled, {
        "terraform": sorted(_terraform_images()),
        "pushed": sorted(_pushed()),
        "pulled": sorted(pulled),
    }


def test_the_product_neither_builds_nor_pulls_the_18_6_6_unit() -> None:
    # ADR 0018 decision 5: the product deployment has no unit image. The unit's
    # repository stays (Terraform unchanged), for the reference workflow alone.
    assert UNIT_IMAGE not in _images(PRODUCT_WORKFLOW, _WORKFLOW_IMAGE)
    assert UNIT_IMAGE not in _images(PRODUCT_COMPOSE, _COMPOSE_IMAGE)
    assert _images(REFERENCE_WORKFLOW, _WORKFLOW_IMAGE) == {UNIT_IMAGE}
    assert _images(REFERENCE_COMPOSE, _COMPOSE_IMAGE) == {UNIT_IMAGE}
