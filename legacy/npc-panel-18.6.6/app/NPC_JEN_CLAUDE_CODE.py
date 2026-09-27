#!/usr/bin/env python3
"""NPC Panel — rezim JEN CLAUDE CODE.

Vyradi celou dvouprovideovou vetev (Anthropic API, OpenAI API, placeny fallback,
schvalovaci fronta, rezervace rozpoctu) a nechá jediny motor: Claude Code
predplatne. Vyzkumne funkce zustavaji beze zmeny — research, generovani
respondentu, analyza, reality alignment, verifikace, klientsky report.

PROC
----
Nejcastejsi tichy pad: kdyz Claude Code cokoli odmitne, ``_request_paid_fallback``
job NEZABIJE, ale odparkuje do stavu WAITING_CAPACITY a zalozi schvaleni
placeneho API. Navenek to vypada, ze se beh proste zastavil a nic nehlasi.
V rezimu jen-Claude-Code neni na co prepinat, takze job misto toho spadne
s konkretni chybou, kterou je videt v UI i v logu.

CO SE MENI
----------
1) provider_auth.normalize_ai_provider  — cokoli mapuje na claude_code_subscription
2) provider_auth.get_ai_provider        — vzdy claude_code_subscription
3) provider_auth.provider_key_ready     — pouze zdravi Claude Code CLI
4) edition_config.allowed_providers     — jediny povoleny provider
5) ai_router._provider_order            — zadne prepinani na API
6) worker_job._request_paid_fallback    — misto schvalovaci fronty srozumitelny pad

Pouziti:
    python NPC_JEN_CLAUDE_CODE.py            # ukaze, co zmeni
    python NPC_JEN_CLAUDE_CODE.py --oprav
    python NPC_JEN_CLAUDE_CODE.py --vrat
"""
from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARK = "NPC JEN CLAUDE CODE"
SUFFIX = ".npcbak_cconly"

AUTH = ROOT / "provider_auth.py"
EDITION = ROOT / "edition_config.py"
ROUTER = ROOT / "ai_router.py"
WORKER = ROOT / "worker_job.py"
FILES = (AUTH, EDITION, ROUTER, WORKER)


NEW_NORMALIZE = '''def normalize_ai_provider(value: str | None, *, default: str = "claude_code_subscription") -> str:
    """NPC JEN CLAUDE CODE: jediny motor je Claude Code predplatne.

    Puvodne se sem propadal default 'anthropic', takze kazde volani, ktere
    neposlalo provider explicitne, skoncilo na placenem API a bez klice selhalo.
    """
    return "claude_code_subscription"


def get_ai_provider() -> str:
    """NPC JEN CLAUDE CODE: globalni provider je fixni."""
    return "claude_code_subscription"


def provider_key_ready(provider: str | None = None) -> bool:
    """NPC JEN CLAUDE CODE: pripravenost = zdrave Claude Code CLI."""
    try:
        from claude_code_provider import health
        return bool(health().get("ok"))
    except Exception:
        return False
'''

NEW_EDITION = '''def allowed_providers()->set[str]:
    # NPC JEN CLAUDE CODE: zadne API varianty se uz nikde nenabizeji.
    return {'claude_code_subscription'}
'''

NEW_ORDER = '''def _provider_order(prefer: str) -> list[str]:
    # NPC JEN CLAUDE CODE: zadne prepinani na placene API, za zadnych okolnosti.
    return ['claude_code_subscription']
'''

NEW_FALLBACK = '''def _request_paid_fallback(store: JobStore, job_id: str, kind: str, reason: str, *, estimates: dict[str, float] | None = None) -> None:
    """NPC JEN CLAUDE CODE: misto schvalovaci fronty srozumitelny pad.

    Puvodne se job odparkoval do WAITING_CAPACITY a cekal na schvaleni placeneho
    API. V rezimu jen-Claude-Code neni na co prepinat, takze cekani bylo trvale
    a navenek vypadalo jako 'nic se nedeje'. Ted job spadne s konkretni pricinou.
    """
    store.event(job_id, 'CLAUDE_CODE_FAILED',
                'Claude Code selhal a placeny fallback je v tomto rezimu vypnuty.',
                {'stage': kind, 'reason': str(reason)[:1800]}, 'ERROR')
    raise RuntimeError(f'CLAUDE_CODE_NEDOSTUPNY [{kind}]: {str(reason)[:1200]}')
'''


class Patcher:
    def __init__(self) -> None:
        self.buf: dict[Path, str] = {}
        self.notes: list[tuple[str, str]] = []

    def load(self, p: Path) -> str:
        if p not in self.buf:
            self.buf[p] = p.read_text(encoding="utf-8")
        return self.buf[p]

    def region(self, p: Path, label: str, start: str, end: str, new: str) -> None:
        src = self.load(p)
        i = src.find(start)
        if i < 0:
            self.notes.append(("OK" if MARK in src else "FAIL",
                               f"{label}: {'uz nasazeno' if MARK in src else 'usek nenalezen'}"))
            return
        j = src.find(end, i + len(start))
        if j < 0:
            self.notes.append(("FAIL", f"{label}: konec useku nenalezen"))
            return
        self.buf[p] = src[:i] + new + src[j:]
        self.notes.append(("OK", f"{label} ({p.name})"))


def build(pt: Patcher) -> None:
    pt.region(AUTH, "1+2+3  provider vzdy Claude Code",
              "def normalize_ai_provider(", "\ndef anthropic_key_kind(", NEW_NORMALIZE + "\n")
    pt.region(EDITION, "4  povoleny jediny provider",
              "def allowed_providers()", "\ndef build_version()", NEW_EDITION)
    pt.region(ROUTER, "5  zadne prepinani na API",
              "def _provider_order(prefer: str)", "\ndef ", NEW_ORDER)
    pt.region(WORKER, "6  pad misto schvalovaci fronty",
              "def _request_paid_fallback(", "\ndef _reserve_stage_if_paid(", NEW_FALLBACK + "\n")


def write(pt: Patcher) -> bool:
    for p, src in pt.buf.items():
        try:
            ast.parse(src)
        except SyntaxError as exc:
            print(f"[FAIL] {p.name} by se nenacetl: {exc}")
            return False
    for p, src in pt.buf.items():
        bak = p.with_suffix(p.suffix + SUFFIX)
        if not bak.exists():
            shutil.copyfile(p, bak)
        p.write_text(src, encoding="utf-8")
    return True


def verify() -> bool:
    import subprocess
    code = (
        "import sys;sys.path.insert(0,r'%s');"
        "from provider_auth import get_ai_provider,normalize_ai_provider;"
        "from edition_config import allowed_providers;"
        "from ai_router import _provider_order;"
        "assert get_ai_provider()=='claude_code_subscription';"
        "assert normalize_ai_provider('openai')=='claude_code_subscription';"
        "assert normalize_ai_provider(None)=='claude_code_subscription';"
        "assert allowed_providers()=={'claude_code_subscription'};"
        "assert _provider_order('anthropic')==['claude_code_subscription'];"
        "import worker_job;"
        "print('provider:',get_ai_provider(),'| povolene:',allowed_providers(),"
        "'| poradi:',_provider_order('openai'))" % str(ROOT)
    )
    p = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=240)
    print((p.stdout or "").strip())
    if p.returncode:
        print((p.stderr or "").strip()[-1200:])
    return p.returncode == 0


def restore() -> int:
    n = 0
    for p in FILES:
        bak = p.with_suffix(p.suffix + SUFFIX)
        if bak.is_file():
            shutil.copyfile(bak, p)
            print("[OK]   obnoveno:", p.name)
            n += 1
    if not n:
        print("[FAIL] zadna zaloha nenalezena")
    return n


def main() -> int:
    args = set(sys.argv[1:])
    print("NPC Panel — rezim JEN CLAUDE CODE")
    print("slozka:", ROOT)
    print()
    if "--vrat" in args:
        return 0 if restore() else 1
    for p in FILES:
        if not p.is_file():
            print("[FAIL] nenalezen:", p.name)
            return 1
    already = [p.name for p in FILES if MARK in p.read_text(encoding="utf-8")]
    if len(already) == len(FILES):
        print("[OK]   Rezim uz je nasazeny, nic nemenim.")
        return 0
    if already:
        print("[FAIL] Nasazeno jen castecne (" + ", ".join(already) + "). Nejdriv --vrat.")
        return 1
    pt = Patcher()
    build(pt)
    for lvl, msg in pt.notes:
        print(f"[{lvl:4s}] {msg}")
    if any(l == "FAIL" for l, _ in pt.notes):
        print("\n[FAIL] Cast useku nesedi, nic nenasazuji.")
        return 1
    print()
    if "--oprav" not in args:
        print("Nic nezmeneno. Spustte s --oprav (nebo JEN_CLAUDE_CODE.bat).")
        return 0
    if not write(pt):
        return 1
    print("[OK]   soubory zapsany, zalohy *" + SUFFIX)
    print()
    if not verify():
        print("[FAIL] kontrola selhala — vracim zalohy")
        restore()
        return 1
    print()
    print("Zavrete bezici NPC runtime okno a spustte START_NPC.bat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
