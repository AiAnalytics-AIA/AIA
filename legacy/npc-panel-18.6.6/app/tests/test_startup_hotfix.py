from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def test_a0_launcher_is_visible_and_does_not_use_hanging_install_manager():
    s=(ROOT/'A0_NPC_PANEL_START.bat').read_text(encoding='utf-8',errors='replace').lower()
    assert 'launcher_bootstrap.py --noninteractive-claude' in s
    assert 'pause >nul' in s
    assert all(f'[{n}/5]' in s for n in range(1,6))
    # Commands, not explanatory copy.
    assert not re.search(r'(?mi)^\s*py(?:\.exe)?\s',s)
    assert not re.search(r'(?mi)^\s*winget(?:\.exe)?\s',s)
    assert 'a1_npc_panel_instalovat_python.bat' in s


def test_detector_never_executes_py_launcher_or_windows_store_alias():
    bat=(ROOT/'DETECT_PYTHON.bat').read_text(encoding='utf-8',errors='replace').lower()
    ps=(ROOT/'WINDOWS_FIND_PYTHON.ps1').read_text(encoding='utf-8',errors='replace').lower()
    assert 'windows_find_python.ps1' in bat
    assert not re.search(r'(?mi)^\s*py(?:\.exe)?\s',bat)
    assert 'windowsapps' in ps
    assert 'waitforexit(5000)' in ps
    assert "'python.exe','python3.exe'" in ps


def test_python_installer_is_direct_official_and_integrity_checked():
    s=(ROOT/'A1_NPC_PANEL_INSTALOVAT_PYTHON.bat').read_text(encoding='utf-8',errors='replace').lower()
    assert 'https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe' in s
    assert 'edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403' in s
    assert 'get-filehash -algorithm sha256' in s
    assert '/passive' in s and 'installallusers=0' in s and 'include_pip=1' in s
    assert '%localappdata%\\npcpanel\\python313' in s
    assert not re.search(r'(?mi)^\s*winget(?:\.exe)?\s',s)
    assert not re.search(r'(?mi)^\s*py(?:\.exe)?\s+install',s)


def test_bootstrap_waits_for_health_before_browser_open():
    s=(ROOT/'launcher_bootstrap.py').read_text(encoding='utf-8')
    assert "'--no-open'" in s
    assert "url=_live_server_url()" in s
    assert "NPC Panel READY:" in s
    assert "webbrowser.open(url,new=2)" in s


def test_normal_start_does_not_spawn_claude_setup_window_by_default():
    s=(ROOT/'launcher_bootstrap.py').read_text(encoding='utf-8')
    assert "NPC_AUTO_CLAUDE_SETUP" in s
    assert "spawn_claude_setup(interactive=True)" in s
