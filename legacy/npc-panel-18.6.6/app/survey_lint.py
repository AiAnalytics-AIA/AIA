"""Static questionnaire validation before any paid LLM calls."""
from __future__ import annotations

import ast
import re

from filter_syntax import filter_error, repair_filter
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class Finding:
    level: str  # ERROR | WARNING | INFO
    where: str
    message: str


def _names(expr: str) -> set[str]:
    tree = ast.parse(expr, mode="eval")
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def lint_questions(questions: list[dict[str, Any]]) -> dict[str, Any]:
    out: list[Finding] = []
    seen: list[str] = []
    ids = [str(q.get("id", "")) for q in questions]
    if not questions:
        out.append(Finding("ERROR", "dotaznik", "Dotazník nemá žádnou otázku."))
    if len(ids) != len(set(ids)):
        out.append(Finding("ERROR", "dotaznik", "ID otázek nejsou unikátní."))

    for pos, q in enumerate(questions, 1):
        qid = str(q.get("id") or f"#{pos}")
        text = str(q.get("text") or "").strip()
        typ = q.get("typ", "vyber")
        if not text:
            out.append(Finding("ERROR", qid, "Chybí text otázky."))
        if len(text) > 500:
            out.append(Finding("WARNING", qid, "Otázka je velmi dlouhá (>500 znaků)."))
        if typ not in {"vyber", "multi", "skala", "otevrena"}:
            out.append(Finding("ERROR", qid, f"Neznámý typ otázky: {typ}"))
        if typ in {"vyber", "multi"}:
            cats = [str(x).strip() for x in q.get("kategorie", [])]
            if len(cats) < 2:
                out.append(Finding("ERROR", qid, "Uzavřená otázka potřebuje alespoň 2 kategorie."))
            if len(cats) != len(set(c.lower() for c in cats)):
                out.append(Finding("ERROR", qid, "Kategorie obsahují duplicity."))
            if any(not c for c in cats):
                out.append(Finding("ERROR", qid, "Kategorie nesmí být prázdná."))
        if typ == "skala":
            scale = q.get("skala", [1, 5])
            if not isinstance(scale, (list, tuple)) or len(scale) != 2 or scale[0] >= scale[1]:
                out.append(Finding("ERROR", qid, "Neplatná škála; očekávám [min,max]."))

        # v15 methodological contract. Standard constructs carry machine-readable
        # metadata from the Instrument Library; these checks run before paid calls.
        meta = q.get("metadata") or {}
        level = str(meta.get("measurement_level") or "").lower()
        if level == "nominal" and typ == "skala":
            out.append(Finding("ERROR", qid, "Nominální/kategoriální konstrukt nesmí být měřen číselnou škálou."))
        if bool(meta.get("sensitive")) and not bool(q.get("povolit_nevim")):
            out.append(Finding("ERROR", qid, "Citlivá otázka musí umožnit 'nevím / nechci odpovědět'."))
        if bool(meta.get("requires_dk")) and not bool(q.get("povolit_nevim")):
            out.append(Finding("ERROR", qid, "Instrument vyžaduje možnost 'nevím'."))
        if bool(meta.get("battery_randomization_required")) and not bool(meta.get("randomized")):
            out.append(Finding("ERROR", qid, "Baterie vyžaduje randomizaci pořadí položek."))
        if bool(meta.get("filter_required")) and not q.get("filtr"):
            out.append(Finding("ERROR", qid, "Podmíněný instrument vyžaduje předřazený filtr/routing."))
        if bool(meta.get("standard_instrument")) and not str(meta.get("instrument_id") or "").strip():
            out.append(Finding("ERROR", qid, "Standardní instrument nemá instrument_id; nelze ověřit jeho verzi."))

        expr = q.get("filtr")
        if expr:
            # Filters are authored by AI/users in mixed syntax. Normalize first so a
            # cosmetic difference cannot block the whole run, and report the repaired
            # expression when the user still has to fix something.
            repaired, note = repair_filter(expr, set(seen))
            err = filter_error(expr, set(seen))
            if err:
                out.append(Finding("ERROR", qid, err))
            else:
                try:
                    refs = _names(repaired)
                    future = refs - set(seen)
                    if future:
                        out.append(Finding("ERROR", qid,
                                           "Filtr odkazuje na neexistující/budoucí otázku: "
                                           + ", ".join(sorted(future))
                                           + ". Filtr smí odkazovat jen na otázky položené dříve."))
                    elif note:
                        out.append(Finding("INFO", qid, note))
                except SyntaxError as e:
                    out.append(Finding("ERROR", qid, f"Neplatná syntaxe filtru: {e.msg}"))

        low = text.lower()
        if re.search(r"\bsouhlasíte,?\s+že\b|\bnemyslíte si,?\s+že\b", low):
            out.append(Finding("WARNING", qid, "Možná navádějící formulace otázky."))
        if any(x in low for x in [" a zároveň ", " nebo zároveň "]):
            out.append(Finding("WARNING", qid, "Možná dvojitá (double-barrelled) otázka."))
        if low.count("?") > 1:
            out.append(Finding("WARNING", qid, "Otázka obsahuje více otazníků."))
        seen.append(qid)

    errors = [asdict(x) for x in out if x.level == "ERROR"]
    warnings = [asdict(x) for x in out if x.level == "WARNING"]
    infos = [asdict(x) for x in out if x.level == "INFO"]
    return {"ok": not errors, "errors": errors, "warnings": warnings, "info": infos,
            "n_questions": len(questions)}


def format_lint(result: dict[str, Any]) -> str:
    lines = [f"=== LINT DOTAZNÍKU: {'OK' if result['ok'] else 'ERROR'} ==="]
    for group in ("errors", "warnings", "info"):
        for x in result[group]:
            lines.append(f"[{x['level']:7}] {x['where']}: {x['message']}")
    if not result["errors"] and not result["warnings"]:
        lines.append("Bez nálezů.")
    return "\n".join(lines)
