"""17.9.9 regressions.

1. A research-flavoured legacy action started on a simulation project must not die with
   ``KeyError: 'RESEARCH_DESIGN'`` (observed live in JOB-1f8e9b7ce7054dc2, 17.9.8).
2. Respondent batches must not split recursively on provider/transport failures, which
   turned one dropped connection into dozens of paid Claude calls.
"""
import pytest


def test_resolve_stage_maps_research_stage_into_simulation_pipeline():
    from project_pipeline import resolve_stage, SIMULATION_STAGES, RESEARCH_STAGES
    sim_ids = [x[0] for x in SIMULATION_STAGES]
    res_ids = [x[0] for x in RESEARCH_STAGES]
    assert "RESEARCH_DESIGN" not in sim_ids
    assert resolve_stage("simulation", "RESEARCH_DESIGN") in sim_ids
    assert resolve_stage("research", "WORLDS") in res_ids
    assert resolve_stage("simulation", "WORLDS") == "WORLDS"
    assert resolve_stage("research", "RESEARCH_DESIGN") == "RESEARCH_DESIGN"


def test_resolve_stage_never_raises_on_unknown_input():
    from project_pipeline import resolve_stage, SIMULATION_STAGES
    sim_ids = [x[0] for x in SIMULATION_STAGES]
    assert resolve_stage("simulation", None) in sim_ids
    assert resolve_stage("simulation", "TOTALLY_UNKNOWN") in sim_ids
    assert resolve_stage("simulation", "", default="ALSO_UNKNOWN") in sim_ids


def test_set_stage_on_simulation_project_survives_research_stage_id(tmp_path):
    from project_store import ProjectStore
    st = ProjectStore(tmp_path / "project_store.sqlite")
    try:
        created = st.create_project(project_type="simulation", title="Sim",
                                    project={"schema_version": "simulation-project-v1"})
        pid = created["project_id"]
        rev = int(created["revision"])
        # This is the exact 17.9.8 crash path.
        st.set_stage(pid, rev, "RESEARCH_DESIGN", "RUNNING", current_job_id="JOB-TEST")
        running = [s for s in st.stages(pid, rev) if s["status"] == "RUNNING"]
        assert len(running) == 1
        assert running[0]["stage_type"] in {x["stage_type"] for x in st.stages(pid, rev)}
    finally:
        st.close()


def _split_safe_probe(monkeypatch, exc, cases=96, depth=0):
    """Drive one respondent batch failure through the real runner and count calls."""
    import pipeline
    calls = []

    def boom(**kw):
        calls.append(len(kw["messages"][0]["content"]))
        raise exc

    monkeypatch.setattr("ai_router.call_structured", boom)
    monkeypatch.setattr("ai_router.classify_provider_exception", lambda e: "OTHER")
    kw_list = [{
        "system": "s",
        "messages": [{"role": "user", "content": f"case {i}"}],
        "tools": [{"name": "t", "input_schema": {"type": "object"}}],
    } for i in range(cases)]
    with pytest.raises(RuntimeError):
        pipeline._claude_subscription_grouped_responses(kw_list, "sonnet", max_tokens=80)
    return calls


def test_connection_errors_do_not_fan_out_into_extra_paid_calls(monkeypatch):
    calls = _split_safe_probe(monkeypatch, RuntimeError("Connection reset by peer"))
    assert len(calls) == 1, f"connection failure split into {len(calls)} paid calls"


def test_auth_errors_do_not_fan_out_into_extra_paid_calls(monkeypatch):
    calls = _split_safe_probe(monkeypatch, RuntimeError("authentication failed"))
    assert len(calls) == 1


def test_oversized_payload_still_splits_but_is_depth_capped(monkeypatch):
    calls = _split_safe_probe(monkeypatch, RuntimeError("input_too_large: context length"))
    # depth cap 3 -> at most 1 + 2 + 4 + 8 attempts, never a 96->1 cascade.
    assert 1 < len(calls) <= 15
