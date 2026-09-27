"""Claude Code-only actionable diagnostics for NPC Panel.

Normal product AI uses the user's Claude Code subscription only.  Diagnostics must
therefore test that exact runtime instead of asking for unrelated API keys.
"""
from __future__ import annotations
from typing import Any


def explain_router_failure(exc: Exception | str, provider: str | None = None) -> dict[str, Any]:
    text=str(exc or '')
    low=text.lower()
    if 'auth_unverified' in low or 'authentication' in low or 'not logged' in low or 'přihl' in low:
        kind='AUTHENTICATION'; action='Otevřete AI nastavení, spusťte Instalace / přihlásit a znovu ověřte Claude Code.'
    elif 'limit' in low or 'quota' in low or 'usage cap' in low or 'rate limit' in low:
        kind='QUOTA'; action='Claude Code narazil na usage/capacity limit. Projekt zůstává uložený; pokračujte později od stejného kroku.'
    elif 'schema' in low or 'json' in low:
        kind='SCHEMA'; action='NPC automaticky zkouší same-Claude JSON recovery. Pokud selže i ta, vytvořte diagnostický ZIP a pošlete jej k opravě.'
    elif 'timeout' in low or 'connection' in low or 'unavailable' in low or '503' in low or '502' in low:
        kind='TRANSPORT'; action='Zkontrolujte internet/VPN/firewall a spusťte Diagnostiku AI. Projekt zůstává uložený.'
    elif 'update_required' in low or 'starší' in low:
        kind='UPDATE_REQUIRED'; action='Aktualizujte Claude Code stable build a znovu spusťte test.'
    elif 'není nainstal' in low or 'not found' in low:
        kind='MISSING'; action='Nainstalujte Claude Code pomocí tlačítka v AI nastavení.'
    else:
        kind='OTHER'; action='Spusťte Diagnostiku AI a vytvořte diagnostický ZIP. Projekt zůstává uložený.'
    return {
        'kind':kind,
        'message':f'Claude Code nedokončil AI krok. {text[:700]}\n\nCo s tím: {action}',
        'detail':text[:1200],
        'next_action':action,
        'providers':{'claude_code_subscription':kind},
    }


def full_report(*, live: bool = True) -> dict[str, Any]:
    """Test the exact Claude Code subscription path used by every product AI step."""
    from claude_code_setup import executable, version, auth_status
    from claude_code_provider import health
    exe=executable()
    try: ver=version() if exe else ''
    except Exception as exc: ver=''; version_error=str(exc)[:500]
    else: version_error=''
    try: auth=auth_status(force=True)
    except TypeError: auth=auth_status()
    except Exception as exc: auth={'subscription_verified':False,'kind':'AUTH_ERROR','message':str(exc)}
    try: h=health()
    except Exception as exc: h={'ok':False,'kind':'HEALTH_ERROR','message':str(exc)}
    report:dict[str,Any]={
        'provider':'claude_code_subscription',
        'executable':exe or '',
        'version':ver,
        'version_error':version_error,
        'auth':auth,
        'health':h,
        'subscription_verified':bool(auth.get('subscription_verified')),
        'problems':[],
    }
    if not exe: report['problems'].append('Claude Code CLI není nainstalovaný.')
    if exe and not auth.get('subscription_verified'):
        report['problems'].append(str(auth.get('message') or 'Claude Code subscription přihlášení není ověřené.'))
    if exe and auth.get('subscription_verified') and not h.get('ok'):
        report['problems'].append(str(h.get('message') or 'Claude Code health check selhal.'))
    if live and exe and auth.get('subscription_verified') and h.get('ok'):
        try:
            from ai_router import roundtrip_test
            report['roundtrip']=roundtrip_test(prefer='claude_code_subscription')
        except Exception as exc:
            report['roundtrip']={'ok':False,'provider':'claude_code_subscription','message':str(exc)}
        if not report['roundtrip'].get('ok'):
            report['problems'].append('Strukturovaný Claude roundtrip selhal: '+str(report['roundtrip'].get('message') or '')[:500])
    report['ok']=bool(report.get('roundtrip',{}).get('ok')) if live else bool(exe and auth.get('subscription_verified') and h.get('ok'))
    if report['ok']:
        rt=report.get('roundtrip') or {}
        report['message']='Claude Code funguje end-to-end pro strukturované AI kroky.'+(f" Model: {rt.get('model')}." if rt.get('model') else '')
    else:
        report['message']=report['problems'][0] if report['problems'] else 'Claude Code runtime není připravený.'
    return report
