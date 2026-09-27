import json
from pathlib import Path
from unittest.mock import patch

import ai_router
import research_copilot


class E400(Exception):
    status_code=400


def test_openai_invalid_model_400_is_model_not_schema():
    e=E400("Invalid model 'opus': model is not available for this project")
    assert ai_router.classify_provider_exception(e)=="MODEL"


def test_wrapped_provider_kind_survives_outer_router():
    assert ai_router.classify_provider_exception(RuntimeError("[MODEL] OpenAI nedokončil požadavek"))=="MODEL"
    assert ai_router.classify_provider_exception(RuntimeError("[SCHEMA] OpenAI nedokončil požadavek"))=="SCHEMA"


import pytest as _pytest
from edition_config import allowed_providers as _ap

def test_openai_is_an_explicit_supported_live_provider_without_silent_fallback():
    project={"schema_version":1,"title":"X","goal":"Zjistit reakci trhu","decision_use":"","briefing":{},"research_plan":{},"audience":{"strategy":"population","description":"ČR 18+","filters":{},"segment":{},"product_description":"","success_definition":"","discovery_note":""},"n":300,"persona_mode":"calibrated","model":"gpt-5.6-sol","research_context":False,"sections":[],"discovery":{},"notes":[],"run_policy":{"provider":"openai"}}
    with patch('ai_router.call_structured',side_effect=RuntimeError("openai: [MODEL] invalid model")):
        r=research_copilot.chat('Doplň projekt',project=project,model='gpt-5.6-sol',provider='openai')
    assert r['_ai']['provider']=='openai'
    assert r['_ai']['failed'] is True
    assert r['_ai']['fallback_used'] is False
    assert r['has_changes'] is False
    assert 'local_fallback' not in json.dumps(r,ensure_ascii=False)
    assert 'openai' in _ap()


def test_ui_sends_explicit_provider_and_does_not_label_failed_as_fallback():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert 'provider:aiProvider()' in s
    assert "r._ai.failed?' · FAILED'" in s


def test_long_claude_transport_uses_stdin_and_system_prompt_file():
    s=Path('claude_code_provider.py').read_text(encoding='utf-8')
    assert '--system-prompt-file' in s
    assert 'p.stdin.write(stdin_text)' in s and 'p.stdin.close()' in s
    assert 'env=env' in s
    # previous bug: large prompt/context must never be inserted into env
    assert 'NPC_PROMPT' not in s


def test_claude_research_150k_payload_never_enters_environment(monkeypatch):
    import claude_code_setup as setup
    monkeypatch.setenv('NPC_ACCIDENTAL_HUGE_CONTEXT','X'*150_000)
    env=setup.subscription_env()
    assert 'NPC_ACCIDENTAL_HUGE_CONTEXT' not in env
    src=Path('claude_code_provider.py').read_text(encoding='utf-8')
    assert 'p.stdin.write(stdin_text)' in src
    assert '--system-prompt-file' in src

def test_old_openai_sdk_attribute_error_is_explicit():
    e=AttributeError("'OpenAI' object has no attribute 'responses'")
    assert ai_router.classify_provider_exception(e)=="SDK_OUTDATED"
