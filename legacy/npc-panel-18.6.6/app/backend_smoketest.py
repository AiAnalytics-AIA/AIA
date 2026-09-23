#!/usr/bin/env python3
"""Short local HTTP smoke test for the NPC backend. No AI/network calls."""
from __future__ import annotations
import json, threading, urllib.request
from http.server import ThreadingHTTPServer
import ui_server
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def main()->int:
    ui=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    if 'function renderMessages()' not in ui: raise RuntimeError('UI postrádá renderMessages()')
    print('UI_RENDER_MESSAGES_SMOKE_PASS')
    srv=ThreadingHTTPServer(('127.0.0.1',0),ui_server.Handler)
    port=int(srv.server_address[1]); th=threading.Thread(target=srv.serve_forever,daemon=True); th.start()
    try:
        base=f'http://127.0.0.1:{port}'
        for path in ('/health','/api/bootstrap'):
            with urllib.request.urlopen(base+path,timeout=30) as r:
                body=r.read()
                if r.status!=200: raise RuntimeError(f'{path}: HTTP {r.status}')
                obj=json.loads(body)
                if path=='/health' and obj.get('status')!='ok': raise RuntimeError('health není ok')
                if path=='/api/bootstrap' and not (obj.get('panel') and obj.get('empty_project')): raise RuntimeError('bootstrap contract není kompletní')
        print('BACKEND_HTTP_SMOKE_PASS')
        return 0
    finally:
        srv.shutdown(); srv.server_close(); th.join(timeout=3)
if __name__=='__main__': raise SystemExit(main())
