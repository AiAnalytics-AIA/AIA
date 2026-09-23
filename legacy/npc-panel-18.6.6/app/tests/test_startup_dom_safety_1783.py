from pathlib import Path


def ui(): return Path('ui_app.html').read_text(encoding='utf-8')


def test_removed_partner_nodes_are_optional_everywhere():
    s=ui()
    assert 'id="claudeState"' not in s
    assert 'id="messages"' not in s
    assert 'id="promptchips"' not in s
    assert 'id="chatInput"' not in s
    assert "$('#promptchips').innerHTML=" not in s
    assert "let box=$('#promptchips');if(!box)return;" in s
    assert "if($('#promptchips'))renderPromptChips()" in s
    assert "if($('#chatInput'))$('#chatInput').addEventListener" in s


def test_active_render_messages_and_chat_have_null_guards():
    s=ui()
    assert "const box=$('#messages');\n  if(!box)return;" in s or "let box=$('#messages');if(!box)return;" in s
    assert "if(!$('#chatInput'))return;return _sendClaude1773()" in s
    assert "if(cs)cs.textContent='Claude Code · jediný AI runtime'" in s


def test_boot_has_named_stages_and_safe_release_target():
    s=ui()
    assert "let BOOT_STAGE_1783='start'" in s
    for stage in ('backend discovery','bootstrap data','Claude status','local state','shell','home render','ready'):
        assert f"bootStage1783('{stage}')" in s
    assert "rel=$('#release');if(rel)rel.textContent=" in s
    assert "<b>Fáze:</b> '+E(BOOT_STAGE_1783)" in s


def test_permanent_shell_dom_contract_exists():
    s=ui()
    for dom_id in ('release','keyState','coreState','steps','view','pageTitle','pageSub','progress','progressTitle','progressText','progressMeta','toast'):
        assert f'id="{dom_id}"' in s, dom_id
