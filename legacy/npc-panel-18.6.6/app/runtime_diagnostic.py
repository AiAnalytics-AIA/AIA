#!/usr/bin/env python3
"""Tiny startup diagnostic that survives an incomplete NPC distribution.

Uses only the Python standard library. START_NPC.bat runs it before importing the
application. If a critical runtime file is missing, it can open a local diagnostic
page instead of crashing with ModuleNotFoundError.
"""
from __future__ import annotations
import argparse, html, json, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REQUIRED=[
    "ui_server.py","ui_app.html","prototype_server.py","validation_gate.py",
    "validation_status.py","core_joint.py","run_store.py","provider_auth.py",
    "runtime_config.py","ai_router.py","pipeline.py","dotaznik.py","research_project.py",
    "audience_registry.py","audience_profile.py","instrument_library.py","project_intake.py",
    "scenario_compiler.py","donor_fusion.py","anchor_registry.py","INSTRUMENT_LIBRARY_v1.json",
    "DONOR_BLOCK_REGISTRY.json","VALIDATION_ANCHORS.json","PRODUCT_POLICY.json",
    "FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz","DATA_PROVENANCE_REGISTRY_v17.csv",
    "PERSONA_SIGNAL_CATALOG_v17.csv","BUILTIN_SUBPANELS_v17.json",
    "CORE_JOINT_STATUS.json","CALIBRATION_REGISTRY.csv",
]
OPTIONAL=["source_materials"]


def diagnose(import_smoke=False):
    missing=[x for x in REQUIRED if not (ROOT/x).exists()]
    import_error=""
    bootstrap_error=""
    if import_smoke and not missing:
        try:
            mod=__import__("ui_server")
            b=mod.bootstrap()
            if not isinstance(b,dict) or not b.get("panel") or not b.get("empty_project"):
                raise RuntimeError("bootstrap() nevrátil platný produktový kontrakt")
        except Exception as exc:
            import_error=f"{type(exc).__name__}: {exc}"
            bootstrap_error=import_error
    return {
        "ok": not missing and sys.version_info >= (3,11) and not import_error,
        "python": sys.version.split()[0],
        "python_ok": sys.version_info >= (3,11),
        "root": str(ROOT),
        "missing_required": missing,
        "missing_optional": [x for x in OPTIONAL if not (ROOT/x).exists()],
        "import_error": import_error,
        "bootstrap_error": bootstrap_error,
    }

def page(d):
    miss="".join(f"<li><code>{html.escape(x)}</code></li>" for x in d["missing_required"]) or "<li>žádné</li>"
    opt="".join(f"<li><code>{html.escape(x)}</code></li>" for x in d["missing_optional"]) or "<li>žádné</li>"
    action=("Runtime je kompletní. Zavřete tuto stránku a spusťte START_NPC.bat znovu."
            if not d["missing_required"] else
            "Distribuce je neúplná. Použijte opravený PART 1 nebo doplňte uvedené soubory do stejné složky. PART 2 jsou pouze zdrojová data a nesmí být nutný k importu serveru.")
    return f'''<!doctype html><html lang="cs"><meta charset="utf-8"><title>NPC startup diagnostika</title>
<style>body{{font:16px system-ui;max-width:900px;margin:50px auto;padding:0 20px;background:#12161a;color:#e4e9ed}}code{{color:#fff}}.card{{background:#191f25;border:1px solid #38434e;padding:22px;margin:16px 0}}h1{{font-size:28px}}.bad{{color:#ff9c8b}}.ok{{color:#8fe0ac}}</style>
<h1>NPC Panel — startup diagnostika</h1><div class="card"><b class="{'ok' if d['ok'] else 'bad'}">{'RUNTIME OK' if d['ok'] else 'RUNTIME NENÍ KOMPLETNÍ'}</b><p>{html.escape(action)}</p></div>
<div class="card"><h2>Chybějící kritické soubory</h2><ul>{miss}</ul><p><b>Import:</b> <code>{html.escape(d.get("import_error") or "OK")}</code></p></div>
<div class="card"><h2>Volitelné / archivní vrstvy</h2><ul>{opt}</ul><p>Tyto položky nesmí bránit startu UI.</p></div>
<div class="card"><p>Python: <code>{html.escape(d['python'])}</code> · kořen: <code>{html.escape(d['root'])}</code></p></div></html>'''.encode('utf-8')

def serve(d, host='127.0.0.1', port=8766):
    data=page(d)
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def log_message(self,*a): pass
    srv=None
    for p in range(port,port+10):
        try: srv=ThreadingHTTPServer((host,p),H);port=p;break
        except OSError: pass
    if srv is None:
        print("[NPC] Diagnostickou stránku se nepodařilo spustit; viz chyby výše.")
        return 2
    url=f'http://{host}:{port}'
    print('[NPC] Diagnostika:',url)
    threading.Timer(.4,lambda:webbrowser.open(url)).start()
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:srv.server_close()
    return 1

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--json',action='store_true');ap.add_argument('--serve-on-error',action='store_true');ap.add_argument('--import-smoke',action='store_true');a=ap.parse_args()
    d=diagnose(import_smoke=a.import_smoke)
    if a.json: print(json.dumps(d,ensure_ascii=False,indent=2))
    else:
        print('[NPC] Startup preflight:', 'OK' if d['ok'] else 'FAIL')
        if not d['python_ok']: print('[NPC] Python 3.11+ je vyžadován; nalezen:',d['python'])
        for x in d['missing_required']: print('[NPC] CHYBÍ:',x)
        if d.get('import_error'): print('[NPC] IMPORT ERROR:',d['import_error'])
        if d['missing_optional']: print('[NPC] Pozn.: volitelná/source vrstva není kompletní:',', '.join(d['missing_optional']))
    if d['ok']: return 0
    return serve(d) if a.serve_on_error else 1
if __name__=='__main__': raise SystemExit(main())
