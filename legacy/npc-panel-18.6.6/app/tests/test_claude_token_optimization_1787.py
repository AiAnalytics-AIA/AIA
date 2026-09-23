import json

import pytest


def _questions(count):
    return [{
        "id": f"Q{i+1:02d}", "text": f"Jak hodnotíte tvrzení číslo {i+1}?",
        "typ": "vyber", "kategorie": ["Souhlasím", "Nesouhlasím"],
        "povolit_nevim": False,
    } for i in range(count)]


def _fake_block_answer(call_log):
    def fake(**kw):
        payload=json.loads(kw["messages"][0]["content"])
        call_log.append(len(payload["cases"]))
        schema=kw["schema"]["properties"]["responses"]["items"]["properties"]["response"]
        rows=[]
        for case in payload["cases"]:
            def one(qschema):
                props=qschema["properties"]
                if "probabilities" in props:
                    n=props["probabilities"]["minItems"]
                    return {"probabilities":[1/n]*n}
                answer=props.get("answer") or {}
                return {"answer":"test" if answer.get("type")=="string" else 1}
            if "probabilities" in schema["properties"] or "answer" in schema["properties"]:
                response=one(schema)
            else:
                response={qid:one(qschema) for qid,qschema in schema["properties"].items()}
            rows.append({"case_id":case["case_id"],"response":response})
        return {"data":{"responses":rows},"tok_in":900,"tok_out":300,"model":"sonnet"}
    return fake


def test_question_block_schema_repeats_persona_only_once():
    from dotaznik import Otazka, build_dotaznik_block_kw
    qs=[Otazka(**q) for q in _questions(6)]
    kw=build_dotaznik_block_kw("UNIQUE PERSONA",qs,historie="UNIQUE HISTORY")
    prompt=kw["messages"][0]["content"]
    assert prompt.count("UNIQUE PERSONA")==1
    assert prompt.count("UNIQUE HISTORY")==1
    assert kw["_npc_questions_per_case"]==6
    schema=kw["tools"][0]["input_schema"]
    assert list(schema["properties"])==[q.id for q in qs]
    assert schema["additionalProperties"] is False


def test_exact_112_by_45_uses_15_subscription_calls(monkeypatch,tmp_path):
    import ai_router,claude_code_provider
    from dotaznik import run_dotaznik
    calls=[]
    monkeypatch.setattr(claude_code_provider,"health",lambda:{"ok":True})
    monkeypatch.setattr(ai_router,"call_structured",_fake_block_answer(calls))
    out=run_dotaznik(
        _questions(45),n=112,mode="sync",workers=1,ulozit=False,tichy=True,
        seed=1787,response_mode="probability",provider_policy="strict_claude_code_subscription",
        model="sonnet",checkpoint=False,run_dir=tmp_path/"run")
    assert calls==[56]*14+[112]
    assert out["provider_calls"]==15
    assert out["n_chyb"]==0
    assert all(out["detail"][q["id"]].notna().sum()==112 for q in _questions(45))


def test_partial_v2_block_resumes_only_missing_half(monkeypatch,tmp_path):
    import ai_router,claude_code_provider
    from dotaznik import run_dotaznik
    monkeypatch.setattr(claude_code_provider,"health",lambda:{"ok":True})
    base=dict(otazky=_questions(6),n=112,mode="sync",workers=1,ulozit=False,tichy=True,
              seed=1787,response_mode="probability",provider_policy="strict_claude_code_subscription",
              model="sonnet",checkpoint=True)
    run=tmp_path/"run";initial=[]
    good=_fake_block_answer([])
    def fail_second(**kw):
        initial.append(len(json.loads(kw["messages"][0]["content"])["cases"]))
        if len(initial)==2:
            raise RuntimeError("You've hit your individual spend limit; session limit resets")
        return good(**kw)
    monkeypatch.setattr(ai_router,"call_structured",fail_second)
    with pytest.raises(RuntimeError,match="spend limit"):
        run_dotaznik(run_dir=run,**base)
    assert all(len((run/f"raw_journal_Q{i:02d}.jsonl").read_text(encoding="utf-8").splitlines())==56 for i in range(1,7))
    # Canonical block journal must repair a process termination during local
    # fan-out without spending another provider call for the lost derived line.
    q6=run/"raw_journal_Q06.jsonl"
    lines=q6.read_text(encoding="utf-8").splitlines()
    q6.write_text("\n".join(lines[:-1])+"\n",encoding="utf-8")
    assert len(q6.read_text(encoding="utf-8").splitlines())==55
    resumed=[]
    monkeypatch.setattr(ai_router,"call_structured",_fake_block_answer(resumed))
    out=run_dotaznik(resume_dir=run,**base)
    assert resumed==[56]
    assert out["provider_calls"]==3
    assert out["n_chyb"]==0


def test_optimized_and_legacy_pipelines_are_mechanically_identical(monkeypatch,tmp_path):
    import ai_router,claude_code_provider
    from dotaznik import run_dotaznik
    monkeypatch.setattr(claude_code_provider,"health",lambda:{"ok":True})
    base=dict(otazky=_questions(12),n=48,mode="sync",workers=1,ulozit=False,tichy=True,
              seed=99,response_mode="probability",provider_policy="strict_claude_code_subscription",
              model="sonnet",checkpoint=False)
    legacy_calls=[]
    monkeypatch.setenv("NPC_RESPONDENT_QUESTION_BLOCK_SIZE","1")
    monkeypatch.setattr(ai_router,"call_structured",_fake_block_answer(legacy_calls))
    legacy=run_dotaznik(run_dir=tmp_path/"legacy",**base)
    optimized_calls=[]
    monkeypatch.setenv("NPC_RESPONDENT_QUESTION_BLOCK_SIZE","6")
    monkeypatch.setattr(ai_router,"call_structured",_fake_block_answer(optimized_calls))
    optimized=run_dotaznik(run_dir=tmp_path/"optimized",**base)
    assert len(legacy_calls)==12 and len(optimized_calls)==2
    for q in _questions(12):
        qid=q["id"]
        assert legacy["detail"][qid].tolist()==optimized["detail"][qid].tolist()
        assert legacy["detail"][f"_probs_{qid}"].tolist()==optimized["detail"][f"_probs_{qid}"].tolist()


def test_respondent_schema_error_never_launches_paid_repair(monkeypatch):
    import claude_code_provider as provider
    calls=[]
    def invalid(**kw):
        calls.append(1)
        return {"text":"not json","structured_output":None,"tok_in":10,"tok_out":2}
    monkeypatch.setattr(provider,"_invoke",invalid)
    monkeypatch.setattr(provider,"_with_retry",lambda fn:fn())
    with pytest.raises(RuntimeError,match="no paid repair call was made"):
        provider.structured_call(system="x",messages=[{"role":"user","content":"y"}],
            schema={"type":"object"},schema_name="npc_respondent_batch")
    assert calls==[1]
