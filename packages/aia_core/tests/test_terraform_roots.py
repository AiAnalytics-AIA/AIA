"""What one Terraform root may own, so one root's destroy cannot reach another's.

Production shares develop's AWS account (ADR 0031). The account's GitHub OIDC provider is one per
account and every deploy role trusts it, so it belongs to `infra/account/` alone, under
`prevent_destroy`; while develop's root declared it, destroying develop would have removed
production's deploy trust (`infra/develop/github.tf:8-31 @ 854c209`). A production bucket holds a
client's data, so it is never `force_destroy` (ADR 0031, "What enforces it").

Terraform does not run in CI's tests, so this reads the files as text, as `test_deploy_images.py`
does, and expects nothing outside the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
INFRA = REPO / "infra"
ACCOUNT = INFRA / "account"
# What a mistaken destroy of the account root must not take: every environment's deploy trust and
# the account's audit trail with its logs.
GUARDED = (
    "aws_iam_openid_connect_provider.github",
    "aws_cloudtrail.account",
    "aws_s3_bucket.cloudtrail",
)

_OIDC_PROVIDER = re.compile(r'^\s*resource\s+"aws_iam_openid_connect_provider"', re.MULTILINE)
_FORCE_DESTROY_TRUE = re.compile(r"^\s*force_destroy\s*=\s*true\b", re.MULTILINE)


def _roots() -> list[Path]:
    return sorted(p.parent for p in INFRA.glob("*/versions.tf"))


def _text(root: Path) -> str:
    return "\n".join(f.read_text(encoding="utf-8") for f in sorted(root.glob("*.tf")))


def test_the_roots_are_found() -> None:
    # Guards the glob: a moved file must fail here, not turn the checks below into nothing.
    names = {root.name for root in _roots()}
    assert {"account", "develop"} <= names, names


def test_only_the_account_root_declares_the_github_oidc_provider() -> None:
    owners = [root.name for root in _roots() if _OIDC_PROVIDER.search(_text(root))]
    assert owners == ["account"], (
        "the account's GitHub OIDC provider is owned by infra/account alone (ADR 0031 §2); "
        f"declared in: {owners}"
    )


def test_the_account_root_keeps_what_it_owns_from_a_destroy() -> None:
    text = _text(ACCOUNT)
    for resource in GUARDED:
        block = _block(text, resource)
        assert re.search(r"prevent_destroy\s*=\s*true", block), f"{resource} lacks prevent_destroy"


def test_no_production_bucket_is_force_destroy() -> None:
    production = INFRA / "production"
    if not production.exists():
        return
    assert not _FORCE_DESTROY_TRUE.search(_text(production)), (
        "infra/production holds client data: no force_destroy = true (ADR 0031 §2)"
    )


def _block(text: str, resource: str) -> str:
    """One resource block's text, from its header to its matching closing brace."""
    kind, name = resource.split(".")
    header = re.search(rf'^resource\s+"{kind}"\s+"{name}"\s*\{{', text, re.MULTILINE)
    assert header, f"{resource} is not declared in infra/account"
    depth = 0
    for i in range(header.end() - 1, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[header.start() : i + 1]
    raise AssertionError(f"{resource}: unbalanced braces")
