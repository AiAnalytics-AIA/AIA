from pathlib import Path


def test_worker_binds_provider_progress_context():
    s=Path('worker_job.py').read_text(encoding='utf-8')
    assert 'bind_runtime(progress, cancel)' in s
    assert 'reset_runtime(_ai_runtime_tokens)' in s


def test_worker_cancel_kills_process_tree():
    s=Path('worker_daemon.py').read_text(encoding='utf-8')
    assert "taskkill','/PID'" in s
    assert "'/T'" in s
    assert 'os.killpg' in s
    assert '_spawn_worker' in s


def test_ui_distinguishes_worker_heartbeat_from_provider_stage():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert "provider: '+t.provider_stage" in s
    assert "hard stop '+fmtTime(t.hard_seconds)" in s
    assert " · worker '+hb" in s


def test_claude_version_gate_is_compatibility_based_not_patch_pinned():
    s=Path('claude_code_setup.py').read_text(encoding='utf-8')
    assert 'return ver >= (2,1,221)' not in s
    assert 'return ver >= (2,1,0)' in s
