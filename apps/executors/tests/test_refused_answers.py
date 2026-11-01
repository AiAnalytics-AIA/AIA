"""Keeping a refused answer never changes what a step fails with (schema-repair chunk 5)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, cast

import pytest
from aia_core.domain.ai_contracts import (
    AgentDefinition,
    Message,
    ModelCallFailed,
    ModelRequest,
)
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.licence import DataLineage
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import FailureClass
from aia_executors.ai_step import StepModelCaller
from aia_worker.executor import StopExecution
from pydantic import BaseModel, ConfigDict


class _Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[str]


REQUEST = ModelRequest(
    agent=AgentDefinition(
        agent_id="design-agent",
        version="1",
        capability=ModelCapability.CRITIC,
        prompt_id="design",
        prompt_version="2",
        output_contract=_Answer,
        max_output_tokens=1000,
    ),
    policy_version="test-v1",
    data_classification=DataClass.CLASS_B_DERIVED_CLIENT,
    data_lineage=DataLineage.none(),
    system="Answer.",
    messages=(Message(role="user", content="Go."),),
)
REFUSED = ModelCallFailed(
    "structured output failed validation",
    failure=FailureClass.SCHEMA_VIOLATION,
    reason="structured_output_invalid",
    violations=("items: Input should be a valid array, received string",),
    rejected_output='{"items":"[]"}',
)


class _Repository:
    def __init__(self, kept: list[Any], fail: BaseException | None) -> None:
        self._kept, self._fail = kept, fail

    def put_json(self, *, payload: Any, **kwargs: Any) -> None:
        if self._fail is not None:
            raise self._fail
        self._kept.append((payload, kwargs))


class _Context:
    step = SimpleNamespace(
        run_id="R",
        step_id="S",
        attempt_id="A",
        project_id="P",
        project_revision=1,
        stage_type="design",
    )

    @contextmanager
    def transaction(self) -> Iterator[tuple[Any, Any]]:
        yield object(), object()


def _caller(kept: list[Any], fail: BaseException | None = None) -> StepModelCaller:
    return StepModelCaller(
        gateway=cast(Any, None),
        context=cast(Any, _Context()),
        runtime_version="t",
        provider=Provider.AWS_BEDROCK,
        reservation_usd=1.0,
        refused_answers=lambda session: cast(Any, _Repository(kept, fail)),
    )


def test_the_refused_answer_is_kept_on_the_steps_own_project_with_its_class() -> None:
    kept: list[Any] = []
    _caller(kept)._keep_refused(REQUEST, REFUSED)
    ((payload, where),) = kept
    assert (payload["data_class"], payload["rejected_output"]) == (
        "CLASS_B_DERIVED_CLIENT",
        '{"items":"[]"}',
    )
    assert (where["project_id"], where["artifact_type"], where["produced_by_job_id"]) == (
        "P",
        "refused_answer",
        "A",
    )


def test_a_failure_to_keep_it_is_logged_and_the_step_keeps_its_own_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _caller([], RuntimeError("store down"))._keep_refused(REQUEST, REFUSED)  # does not raise
    assert "refused answer not kept" in caplog.text
    assert '{"items":"[]"}' not in caplog.text  # the answer is never logged


def test_a_lost_lease_while_keeping_it_still_stops_the_step() -> None:
    with pytest.raises(StopExecution):
        _caller([], StopExecution("lease lost"))._keep_refused(REQUEST, REFUSED)


def test_a_caller_with_no_home_keeps_nothing() -> None:
    caller = StepModelCaller(
        gateway=cast(Any, None),
        context=cast(Any, _Context()),
        runtime_version="t",
        provider=Provider.AWS_BEDROCK,
        reservation_usd=1.0,
        refused_answers=None,
    )
    caller._keep_refused(REQUEST, REFUSED)  # nothing to write to, nothing raised
