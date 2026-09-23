from pathlib import Path
import claude_code_provider as provider
import claude_code_setup as setup


def test_cli_uses_safe_mode_and_no_mcp_config(tmp_path):
    cmd=provider._base_cli_command('claude',system_file=str(tmp_path/'system.txt'),model='haiku',schema=None)
    assert '--safe-mode' in cmd
    assert '--mcp-config' not in cmd
    assert '--strict-mcp-config' not in cmd
    assert '--disallowedTools' in cmd and 'mcp__*' in cmd
    assert cmd[cmd.index('--output-format')+1]=='stream-json'


def test_research_cli_exposes_only_web_tools(tmp_path):
    cmd=provider._base_cli_command('claude',system_file=str(tmp_path/'system.txt'),model='sonnet',schema=None,research=True,max_turns=4)
    assert '--safe-mode' in cmd
    assert cmd[cmd.index('--tools')+1]=='WebSearch,WebFetch'
    assert cmd[cmd.index('--allowedTools')+1]=='WebSearch,WebFetch'
    assert '--mcp-config' not in cmd


def test_subscription_environment_disables_claude_ai_mcp(monkeypatch):
    monkeypatch.setenv('PATH','C:/Windows')
    env=setup.subscription_env()
    assert env['CLAUDE_CODE_SAFE_MODE']=='1'
    assert env['ENABLE_CLAUDEAI_MCP_SERVERS']=='false'


def test_stale_lock_file_never_blocks_when_no_os_lock(monkeypatch,tmp_path):
    lp=tmp_path/'subscription.lock'; lp.write_text('999999 0\n',encoding='utf-8')
    monkeypatch.setattr(provider,'LOCK_PATH',lp)
    slot=provider._acquire_slot(timeout=.5)
    assert slot is not None
    provider._lock_release(slot)


def test_launcher_refuses_cross_release_server_on_same_port():
    s=Path('launcher_bootstrap.py').read_text(encoding='utf-8')
    assert '_port_8766_health' in s
    assert 'Port 8766 už používá běžící NPC Panel' in s
    assert 'Zavřete staré černé runtime okno' in s
