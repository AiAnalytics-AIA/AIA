from pathlib import Path


def ui():
    return Path('ui_app.html').read_text(encoding='utf-8')


def test_removed_claude_state_is_not_required_by_active_update_state():
    s=ui()
    assert 'id="claudeState"' not in s
    marker="updateState=function(){let ok=aiProviderReady('claude_code_subscription')"
    start=s.index(marker)
    end=s.index('\n',start)
    fn=s[start:end]
    assert "if(cs)cs.textContent='Claude Code · jediný AI runtime'" in fn
    assert "$('#claudeState').textContent" not in fn


def test_boot_error_screen_distinguishes_frontend_from_backend_failure():
    s=ui()
    assert "boot().catch(async e=>" in s
    assert "online=!!(await discoverBackend())" in s
    assert "NPC rozhraní se nepodařilo inicializovat" in s
    assert "Backend odpovídá. Chyba vznikla při inicializaci rozhraní ve fázi" in s


def test_boot_dom_targets_exist_or_are_guarded():
    s=ui()
    for dom_id in ('release','keyState','coreState','steps','view','pageTitle','pageSub','progress','progressText','progressMeta','toast'):
        assert f'id="{dom_id}"' in s, dom_id
