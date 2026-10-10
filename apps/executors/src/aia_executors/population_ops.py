"""``python -m aia_executors.population_ops <command> --as <email>``: operate the population.

The population core (import, companions, establish, promote LIVE) was built and
tested with nothing outside it calling it (plan ``population-operations.md`` P1).
This is its one operator surface, beside ``seed`` and ``legacy_workspace``:

* ``status``     the dataset's versions, its populations and their promotion history
* ``import``     validate a bundle under the contract and register it as a new version
* ``attach``     record a version's companion set
* ``establish``  create the STATIC or LIVE population over a version
* ``promote``    move a LIVE population to another version, naming the one it expects

Every command but ``status`` acts as a named person (``--as``): an active AIA user
whom ``AIA_POPULATION_OPERATORS`` names. That key -- a JSON object of verified user
id to permissions, ``{"<user id>": ["POPULATION_ESTABLISH", "POPULATION_PROMOTE"]}``
-- is the trusted deployment configuration ``PopulationAuthority`` issues from, read
here and nowhere else. Unset or empty, nobody may operate the population, which is
the right state for a deployment that has not deliberately named someone.

Reads ``DATABASE_URL`` and ``AIA_POPULATION_ASSET_ROOT`` (the directory every
``--panel``, ``--dictionary`` and companion location is relative to). Judges every
bundle against the Czech import contract. Prints ids and outcomes as JSON, never data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, TextIO

from aia_core.application.population import PopulationRuntime
from aia_core.application.population_authority import (
    PopulationAuthority,
    PopulationOperatorConfig,
)
from aia_core.application.scope import AuthenticatedPrincipal
from aia_core.domain.population import (
    PopulationError,
    PopulationImportContract,
    PopulationKind,
)
from aia_core.domain.population.authority import (
    PopulationOperatorContext,
    PopulationPermission,
)
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.population_source import (
    FilesystemPopulationSource,
    PopulationAssetSource,
)
from aia_core.infrastructure.tables import UserRow
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ._db import engine_from_env

__all__ = [
    "ASSET_ROOT_KEY",
    "OPERATORS_KEY",
    "OperatorConfigError",
    "OperatorRefused",
    "main",
    "operator_config",
    "run",
]

OPERATORS_KEY: Final = "AIA_POPULATION_OPERATORS"
ASSET_ROOT_KEY: Final = "AIA_POPULATION_ASSET_ROOT"

#: The organization an operator's principal names. Population operation is platform
#: administration: the authority reads only the verified user id, and no tenant's
#: organization confers or limits it.
_PLATFORM: Final = "platform"


class OperatorConfigError(ValueError):
    """``AIA_POPULATION_OPERATORS`` does not read; the command does not start."""


class OperatorRefused(Exception):
    """The command cannot act: no such person, or the configuration does not name them."""


def operator_config(env: Mapping[str, str]) -> PopulationOperatorConfig:
    """The operators ``AIA_POPULATION_OPERATORS`` names. Unset or blank: nobody.

    A value that is not a JSON object of user id to a list of permission names, an
    empty id, or a permission AIA does not have stops the command naming the key:
    a typo must never quietly leave an operator out or in.
    """
    raw = env.get(OPERATORS_KEY, "").strip()
    if not raw:
        return PopulationOperatorConfig()
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OperatorConfigError(f"{OPERATORS_KEY} is not JSON: {exc.msg}") from None
    if not isinstance(document, dict):
        raise OperatorConfigError(f"{OPERATORS_KEY} must be an object of user id to permissions")
    known = {p.value for p in PopulationPermission}
    for user_id, names in document.items():
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise OperatorConfigError(f"{OPERATORS_KEY}: {user_id!r} needs a list of permissions")
        unknown = sorted(set(names) - known)
        if unknown:
            raise OperatorConfigError(
                f"{OPERATORS_KEY}: {user_id!r} names {', '.join(unknown)}, "
                f"not one of {', '.join(sorted(known))}"
            )
    try:
        return PopulationOperatorConfig.from_names(document)
    except ValueError as exc:
        raise OperatorConfigError(f"{OPERATORS_KEY}: {exc}") from None


@dataclass(frozen=True, slots=True)
class _Actor:
    user_id: str
    email: str


def _actor(session: Session, email: str) -> _Actor:
    address = email.strip().lower()
    row = session.scalar(select(UserRow).where(UserRow.email == address))
    if row is None or not row.is_active:
        raise OperatorRefused(f"no active AIA user {email!r}; the command acts as a person")
    return _Actor(user_id=row.user_id, email=address)


def _operator(
    session: Session, authority: PopulationAuthority, email: str
) -> PopulationOperatorContext:
    actor = _actor(session, email)
    try:
        return authority.operator_context(
            AuthenticatedPrincipal(user_id=actor.user_id, organization_id=_PLATFORM, email=email)
        )
    except PopulationError as exc:
        raise OperatorRefused(f"{exc} ({OPERATORS_KEY} names who may)") from None


def _companions(pairs: Sequence[str] | None) -> dict[str, str] | None:
    if pairs is None:
        return None
    parsed: dict[str, str] = {}
    for pair in pairs:
        asset_id, sep, location = pair.partition("=")
        if not sep or not asset_id or not location:
            raise OperatorRefused(f"--companion {pair!r} is not ASSET_ID=LOCATION")
        if asset_id in parsed:
            raise OperatorRefused(f"--companion names {asset_id} twice")
        parsed[asset_id] = location
    return parsed


def _status(session: Session, contract: PopulationImportContract) -> dict[str, Any]:
    registry = PopulationRegistryRepository(session)
    dataset = contract.dataset_id
    return {
        "dataset_id": dataset,
        "contract_id": contract.contract_id,
        "versions": [
            {
                "version_id": v.version_id,
                "label": v.label,
                "content_sha256": v.content_sha256,
                "parent_version_id": v.parent_version_id,
                "imported_by": v.imported_by,
                "imported_at": v.imported_at.isoformat(),
                "companions": registry.companion_set(v.version_id) is not None,
            }
            for v in sorted(registry.versions(dataset).values(), key=lambda v: v.imported_at)
        ],
        "populations": [
            {
                "population_id": p.population_id,
                "kind": p.kind.value,
                "current_version_id": p.current_version_id,
            }
            for p in registry.populations(dataset)
        ],
        "history": [
            {
                "population_id": r.population_id,
                "from_version_id": r.from_version_id,
                "to_version_id": r.to_version_id,
                "actor_id": r.actor_id,
                "reason": r.reason,
                "at": r.promoted_at.isoformat(),
            }
            for r in registry.promotions(dataset)
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m aia_executors.population_ops",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="versions, populations and history; acts as no one")

    def acting(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--as", dest="actor", required=True, help="the operator's AIA email")
        return sub

    imp = acting("import", "register a bundle as a new version; never promotes")
    imp.add_argument("--label", required=True)
    imp.add_argument("--panel", required=True, help="panel location under the asset root")
    imp.add_argument("--dictionary", required=True, help="dictionary location")
    imp.add_argument("--provenance", required=True, help="where the bundle came from")
    imp.add_argument("--parent", help="the version this one derives from")
    imp.add_argument(
        "--companion", action="append", help="ASSET_ID=LOCATION, repeatable; validated with it"
    )

    att = acting("attach", "record a version's companion set")
    att.add_argument("--version", required=True)
    att.add_argument("--companion", action="append", required=True, help="ASSET_ID=LOCATION")

    est = acting("establish", "create a population over a version; once per population")
    est.add_argument("--population", required=True)
    est.add_argument("--kind", required=True, choices=[k.value for k in PopulationKind])
    est.add_argument("--version", required=True)
    est.add_argument("--reason", required=True)

    pro = acting("promote", "move a LIVE population, naming the version it is on now")
    pro.add_argument("--population", required=True)
    pro.add_argument("--to", dest="target", required=True)
    pro.add_argument("--expected", required=True, help="the version LIVE must be on now")
    pro.add_argument("--reason", required=True)
    return parser


def run(
    argv: Sequence[str],
    *,
    sessions: sessionmaker[Session],
    config: PopulationOperatorConfig,
    source: PopulationAssetSource,
    contract: PopulationImportContract = CZ_SYNTHETIC_V17,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    """Run one command. 0 done, 2 refused (nothing written), 3 the population refused it.

    Each command is one transaction: refused, it commits nothing.
    """
    args = _parser().parse_args(list(argv))
    authority = PopulationAuthority(config)
    with sessions() as session:
        try:
            if args.command == "status":
                result: dict[str, Any] = _status(session, contract)
            else:
                operator = _operator(session, authority, args.actor)
                runtime = PopulationRuntime(session, contract=contract, source=source)
                result = _act(args, runtime, operator)
                session.commit()
        except OperatorRefused as exc:
            session.rollback()
            print(str(exc), file=err)
            return 2
        except PopulationError as exc:
            session.rollback()
            failures = getattr(exc, "failures", ())
            print(f"{type(exc).__name__}: {exc}", file=err)
            for failure in failures:
                print(f"  {failure}", file=err)
            return 3
    print(json.dumps(result, indent=2, sort_keys=True), file=out)
    return 0


def _act(
    args: argparse.Namespace, runtime: PopulationRuntime, operator: PopulationOperatorContext
) -> dict[str, Any]:
    actor = operator.actor_id
    if args.command == "import":
        version = runtime.import_version(
            label=args.label,
            panel_location=args.panel,
            dictionary_location=args.dictionary,
            provenance=args.provenance,
            imported_by=actor,
            parent_version_id=args.parent,
            companion_locations=_companions(args.companion),
        )
        return {
            "version_id": version.version_id,
            "label": version.label,
            "content_sha256": version.content_sha256,
            "parent_version_id": version.parent_version_id,
            "status": runtime.version_status(version.version_id).value,
        }
    if args.command == "attach":
        companions = _companions(args.companion) or {}
        runtime.attach_companions(
            version_id=args.version, companion_locations=companions, attached_by=actor
        )
        return {
            "version_id": args.version,
            "companions": sorted(companions),
            "status": runtime.version_status(args.version).value,
        }
    if args.command == "establish":
        population = runtime.establish(
            operator=operator,
            population_id=args.population,
            kind=PopulationKind(args.kind),
            version_id=args.version,
            reason=args.reason,
        )
    else:
        population = runtime.promote_live(
            operator=operator,
            population_id=args.population,
            target_version_id=args.target,
            expected_current_version_id=args.expected,
            reason=args.reason,
        )
    return {
        "population_id": population.population_id,
        "kind": population.kind.value,
        "current_version_id": population.current_version_id,
        "actor_id": actor,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        config = operator_config(os.environ)
    except OperatorConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    root = os.environ.get(ASSET_ROOT_KEY, "").strip()
    if not root:
        print(f"{ASSET_ROOT_KEY} is required: the directory bundles are read from", file=sys.stderr)
        return 2
    engine, sessions = engine_from_env()
    try:
        return run(
            sys.argv[1:] if argv is None else argv,
            sessions=sessions,
            config=config,
            source=FilesystemPopulationSource(root),
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
