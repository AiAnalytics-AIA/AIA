"""Starting a respondent system's confirmation run (panel-grounded-respondents 7e3).

A validation runs as a research Study of its own. Its confirmation run is made from the Study's
stored preregistration (``HoldoutRepository``) and the item bank that preregistration pins.
The caller states nothing else that decides the verdict.

:meth:`ValidationRuns.start` refuses, before anything is written:

- a Study with no preregistration (``holdout_preregistration_missing``);
- a bank that is not the preregistered one, or an item code would answer as a fact
  (:func:`~aia_core.domain.holdout.run.validation_specification`);
- LIVE not established, or a respondent system that is no longer the preregistered one: any
  component this code pins, or the population the run would record
  (``holdout_system_stale``). The model binding is the gateway's and is checked by the arm step;
- a system another Study of the organization has started confirming
  (``holdout_system_confirmation_started``). A database constraint holds the same rule when two
  starts race;
- a ceiling that cannot be worked out (``holdout_cost_unknown``), or one above the ceiling the
  preregistration recorded (``holdout_cost_above_preregistration``);
- a ceiling at or above the Study's spend limit that the person has not confirmed
  (:class:`~aia_core.application.research.CostConfirmationRequired`), as a research run's start
  asks. The yes is recorded in the approval ledger with the run.

The Study's budget is the hard cap, as for any run: every request reserves against it, and a
step that would pass it waits for a person (``AWAITING_BUDGET``), never cut part-way.

There is no retry of a confirmation run. Its steps retry on their own, and every request is
journaled, so a retry never pays twice. A run that ends, pass or fail, is the result.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.holdout.bank import ItemBank
from ..domain.holdout.preregistration import HoldoutRefused, Preregistration
from ..domain.holdout.run import (
    VALIDATION_PROJECT_OWNER,
    VALIDATION_WORKFLOW,
    arm_node_key,
    preregistered_blocks,
    shuffle_seed,
    system_mismatch,
    validation_cost_ceiling,
    validation_requests,
    validation_specification,
    validation_steps,
)
from ..domain.panel_source import PANEL_SOURCE, pinned_components
from ..domain.pipeline import ProjectType
from ..domain.population import CZ_LIVE, PopulationImportContract
from ..domain.population.czech import CZ_SYNTHETIC_V17
from ..domain.scope import Permission, StudyContext
from ..infrastructure.holdout_repository import HoldoutRepository
from ..infrastructure.repositories import ProjectRepository
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.workflow_repository import WorkflowRepository
from .population import live_binding
from .research import CostConfirmationRequired
from .workflows import StartedRun

__all__ = ["ValidationRuns"]


def _refused(message: str, reason: str) -> HoldoutRefused:
    return HoldoutRefused(message, reason=reason)


def _block_exclusions(preregistration: Preregistration) -> dict[str, list[str]]:
    """Each confirmation item mapped to every field its block's respondents are not given."""
    out: dict[str, list[str]] = {}
    for block in preregistration.document["blocks"]:
        fields = sorted(
            {str(x["field"]) for x in block["excluded"]} | {str(s) for s in block["signals"]}
        )
        for item in block["items"]:
            out[str(item)] = fields
    return out


@dataclass(frozen=True, slots=True)
class ValidationRuns:
    """The confirmation run of the validation Study in scope. The caller owns the transaction."""

    session: Session
    scope: StudyContext
    #: The population the run records: the Czech LIVE in every composition, another only in
    #: tests over a fictional contract.
    population_contract: PopulationImportContract = CZ_SYNTHETIC_V17
    population_id: str = CZ_LIVE

    def _holdout(self) -> HoldoutRepository:
        return HoldoutRepository(self.session, self.scope)

    def _project(self, preregistration_sha256: str) -> tuple[str, int]:
        """The Study's validation project, created on first use; seen by no generic route."""
        projects = ProjectRepository(self.session, self.scope, owner=VALIDATION_PROJECT_OWNER)
        found = projects.list_projects(limit=1).items
        if found:
            project = projects.get(found[0].project_id)
            return project.project_id, project.current_revision
        project, _ = projects.create(
            title="Respondent system validation",
            project_type=ProjectType.RESEARCH,
            content={"preregistration_sha256": preregistration_sha256},
            created_by=self.scope.actor_id,
            reason=VALIDATION_WORKFLOW,
        )
        return project.project_id, project.current_revision

    def start(
        self,
        *,
        bank: ItemBank,
        reservation_usd: float | None,
        confirm_cost_usd: float | None = None,
    ) -> StartedRun:
        """Start the Study's confirmation run, or find the one it started.

        ``reservation_usd`` is what the worker reserves per fieldwork request, as the API reads
        it from the same settings; ``None`` is unknown, never zero. Needs ``RUN_WORKFLOW`` on an
        open Study.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        holdout = self._holdout()
        stored = holdout.preregistration()
        if stored is None:
            raise _refused(
                "the Study has no preregistration; nothing is confirmed without one",
                "holdout_preregistration_missing",
            )
        prereg = stored.preregistration
        key = f"{VALIDATION_WORKFLOW}:{stored.sha256}"
        workflows = WorkflowRepository(self.session, self.scope)
        existing = workflows.find_run_by_idempotency_key(key)
        if existing is not None:
            run = workflows.get_run(existing)
            return StartedRun(
                run_id=existing,
                project_id=run["project_id"],
                project_revision=run["project_revision"],
                workflow_type=VALIDATION_WORKFLOW,
                created=False,
                run=run,
            )

        spec = validation_specification(bank, prereg)
        population = live_binding(
            self.session, contract=self.population_contract, population_id=self.population_id
        )
        if population is None:
            raise _refused(
                f"{self.population_id} is not established; there is nothing to sample",
                "holdout_population_missing",
            )
        stale = system_mismatch(prereg, pinned_components(population.version_id))
        if stale:
            raise _refused(
                f"the respondent system is not the one preregistered: {', '.join(stale)}",
                "holdout_system_stale",
            )
        if holdout.system_confirmed_elsewhere(stored.respondent_system_fingerprint):
            raise _refused(
                "this respondent system's confirmation has already started in another Study",
                "holdout_system_confirmation_started",
            )

        ceiling = validation_cost_ceiling(prereg, reservation_usd)
        if ceiling is None:
            raise _refused(
                "the fieldwork reservation is unknown, so the run's ceiling is",
                "holdout_cost_unknown",
            )
        recorded = float(prereg.document["cost_ceiling_usd"])
        if ceiling > recorded:
            raise _refused(
                f"the run can cost up to {ceiling:.2f}, above the {recorded:.2f} preregistered",
                "holdout_cost_above_preregistration",
            )
        limit = ScopeRepository(self.session).get_study(self.scope).spend_confirm_usd
        confirmation: tuple[float, float] | None = None
        if limit is not None and ceiling >= limit:
            if confirm_cost_usd is None or confirm_cost_usd < ceiling:
                raise CostConfirmationRequired(ceiling_usd=ceiling, limit_usd=limit)
            confirmation = (ceiling, limit)

        project_id, revision = self._project(stored.sha256)
        steps = validation_steps(prereg)
        run_id = workflows.create_run(
            project_id=project_id,
            project_revision=revision,
            workflow_type=VALIDATION_WORKFLOW,
            steps=steps,
            idempotency_key=key,
            metadata={
                "preregistration_sha256": stored.sha256,
                "respondent_system_fingerprint": stored.respondent_system_fingerprint,
                "persona_source": PANEL_SOURCE,
                "requests": validation_requests(prereg),
                "cost_ceiling_usd": ceiling,
                "population": {
                    "population_id": population.population_id,
                    "version_id": population.version_id,
                    "version_label": population.version_label,
                    "read_by_fieldwork": True,
                },
            },
            step_inputs=self._step_inputs(stored.sha256, prereg, spec.model_dump(mode="json")),
            fingerprints={s.node_key: stored.sha256 for s in steps},
            population=population,
        )
        holdout.record_confirmation(run_id=run_id, preregistration_sha256=stored.sha256)
        if confirmation is not None:
            assert confirm_cost_usd is not None
            workflows.record_spend_confirmation(
                run_id,
                ceiling_usd=confirmation[0],
                limit_usd=confirmation[1],
                confirmed_usd=confirm_cost_usd,
            )
        return StartedRun(
            run_id=run_id,
            project_id=project_id,
            project_revision=revision,
            workflow_type=VALIDATION_WORKFLOW,
            created=True,
            run=workflows.get_run(run_id),
        )

    @staticmethod
    def _step_inputs(
        sha256: str, prereg: Preregistration, specification: Mapping[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Every step's input: all it needs, from the preregistration, nothing it re-chooses."""
        document = prereg.document
        blocks = [list(b) for b in preregistered_blocks(prereg)]
        exclusions = _block_exclusions(prereg)
        binding = document["respondent_system"]["components"]["model_binding"]
        inputs: dict[str, dict[str, Any]] = {
            "sample": {
                "preregistration_sha256": sha256,
                "n": document["n"],
                "sample_seed": document["sample_seed"],
            },
            "score": {"preregistration_sha256": sha256, "preregistration": dict(document)},
        }
        for arm in document["model_arms"]:
            for k, seed in enumerate(document["replicate_seeds"], start=1):
                inputs[arm_node_key(arm, k)] = {
                    "preregistration_sha256": sha256,
                    "arm": arm,
                    "replicate": k,
                    "seed": seed,
                    **({"shuffle_seed": shuffle_seed(seed)} if arm == "S" else {}),
                    "specification": dict(specification),
                    "blocks": blocks,
                    "exclusions": exclusions,
                    "model_binding": binding,
                }
        return inputs

    def run(self) -> dict[str, Any] | None:
        """The Study's confirmation run, found through the Study, or ``None`` before it starts."""
        confirmation = self._holdout().confirmation()
        if confirmation is None:
            return None
        return WorkflowRepository(self.session, self.scope).get_run(confirmation.run_id)
