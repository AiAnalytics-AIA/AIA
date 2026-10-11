"""A methodology version: a module's specification and formulas, edited and named (ADR 0023).

Plan ``methodology-tab.md`` A3. A version is what the methodologist proposes for one editable
method module: the code preset it starts from, the whole specification (ADR 0023 decision 3:
a run pins a whole specification, so an edit is a whole specification) and an expression
for any slot it replaces. :func:`validate_version` is the only way to one, and it fails closed:

* the module must be editable (the reference map is not: edited, it would stop being the
  reference, ADR 0023 decision 4);
* the specification must validate as the base preset's own type, under the module's own
  validator (for the Sociomap, ``require_supported``), every problem reported at once;
* each replaced formula must name a slot of the module, compile in it and keep the slot's
  properties on its grid (:mod:`.expressions`);
* the version's name is ``<base>+e<number>`` and is written into the specification by
  :func:`named`, so an edited map can never be mistaken for the code's preset.

:func:`version_payload` is what is stored and pinned; :func:`payload_sha256` its digest over the
canonical JSON. Nothing here reads or writes storage.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from .catalogue import MethodModule, Preset
from .expressions import ExpressionRefused, check_properties, compile_formula

__all__ = [
    "VERSION_CONTRACT",
    "MethodologyVersionInvalid",
    "ValidatedVersion",
    "named",
    "payload_sha256",
    "validate_version",
    "version_payload",
]

#: The shape of a stored version's payload; a reader refuses any other.
VERSION_CONTRACT: Final = "aia-methodology-version-1"
_MAX_EXPRESSIONS: Final = 64


class MethodologyVersionInvalid(ValueError):
    """The proposed version is not one this module accepts. ``problems`` names each reason."""

    def __init__(self, problems: Mapping[str, str]) -> None:
        self.problems = dict(problems)
        detail = "; ".join(f"{k}: {v}" for k, v in sorted(self.problems.items()))
        super().__init__(f"the methodology version is refused: {detail}")


@dataclass(frozen=True, slots=True)
class ValidatedVersion:
    """A version every rule accepted: its module, base preset, specification and formulas."""

    module_id: str
    base_preset: str
    spec: BaseModel
    formulas: Mapping[str, str]  # slot id -> expression, only the slots this version replaces


def named(base_preset: str, number: int) -> str:
    """The name an edited version carries: the preset it came from, and its number."""
    if number < 1:
        raise ValueError("a version number counts from 1")
    return f"{base_preset}+e{number}"


def _preset(module: MethodModule, name: str) -> Preset | None:
    return next((p for p in module.presets if p.name == name), None)


def validate_version(
    module: MethodModule,
    *,
    base_preset: str,
    spec: Mapping[str, Any],
    formulas: Mapping[str, str],
    version_name: str,
) -> ValidatedVersion:
    """Every rule a version must keep, all problems at once; the validated version if none.

    ``spec`` is the whole specification as JSON data. Its ``methodology_version``, if it has
    one, is replaced by ``version_name`` before it is validated: the store names a version,
    not its author.
    """
    problems: dict[str, str] = {}
    if not module.editable:
        raise MethodologyVersionInvalid(
            {"module": f"{module.id} is shown, not edited (ADR 0023 decision 4)"}
        )
    preset = _preset(module, base_preset)
    if preset is None:
        raise MethodologyVersionInvalid(
            {"base_preset": f"{module.id} has no preset {base_preset!r}"}
        )
    validated_spec: BaseModel | None = None
    try:
        validated_spec = type(preset.spec).model_validate(
            {**dict(spec), "methodology_version": version_name}
        )
    except ValidationError as exc:
        for error in exc.errors():
            where = ".".join(str(p) for p in error["loc"]) or "spec"
            problems[f"spec.{where}"] = error["msg"]
    if validated_spec is not None:
        try:
            preset.validate(validated_spec)
        except Exception as exc:  # the module's own validator, reported as it says it
            unsupported = getattr(exc, "unsupported", None)
            if isinstance(unsupported, Mapping):
                for where, why in unsupported.items():
                    problems[f"spec.{where}"] = str(why)
            else:
                problems["spec"] = str(exc)

    slots = {f.slot.id: f for f in module.formulas}
    if len(formulas) > _MAX_EXPRESSIONS:
        problems["formulas"] = f"at most {_MAX_EXPRESSIONS} replaced formulas"
    for slot_id, expression in formulas.items():
        builtin = slots.get(slot_id)
        if builtin is None:
            problems[f"formula.{slot_id}"] = f"{module.id} has no slot {slot_id!r}"
            continue
        try:
            compiled = compile_formula(builtin.slot, expression)
        except ExpressionRefused as exc:
            problems[f"formula.{slot_id}"] = f"{exc.code}: {exc}"
            continue
        for prop, why in check_properties(compiled).items():
            problems[f"formula.{slot_id}.{prop}"] = why

    if problems or validated_spec is None:
        raise MethodologyVersionInvalid(problems)
    return ValidatedVersion(
        module_id=module.id,
        base_preset=base_preset,
        spec=validated_spec,
        formulas={k: v.strip() for k, v in sorted(formulas.items())},
    )


def version_payload(version: ValidatedVersion) -> dict[str, Any]:
    """What is stored and pinned: plain JSON, its contract named."""
    return {
        "contract": VERSION_CONTRACT,
        "module_id": version.module_id,
        "base_preset": version.base_preset,
        "spec": version.spec.model_dump(mode="json"),
        "formulas": dict(version.formulas),
    }


def payload_sha256(payload: Mapping[str, Any]) -> str:
    """SHA256 of the payload's canonical JSON (sorted keys, no whitespace)."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
