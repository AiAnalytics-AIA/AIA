"""
NPC PANEL — dotaznik.py
Sekvenční dotazníkový engine nad stejným syntetickým vzorkem.

Každá otázka se routuje, tematicky klasifikuje a promptuje samostatně. Model
nevidí budoucí otázky. U uzavřených otázek může vracet pravděpodobnostní
distribuci; konkrétní syntetická odpověď se pak losuje externě se seedem.

Typy otázek: vyber | multi | skala | otevrena
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from pipeline import (
    DEFAULT_MODEL, RUNS_DIR, SEGMENTY, PANEL_PATH, Panel,
    _call_llm, _rozlozeni, generate_persona_text, sample_representative, resolve_panel_metadata,
    BLOCK_CELL_BUDGET,
)
from runtime_config import resolve_model, pricing, RELEASE, resolve_provider_model, provider_pricing, RUN_DEFAULTS
from manifest import build_manifest, save_manifest, sha256_file, sha256_json

TYPY = ("vyber", "multi", "skala", "otevrena")


@dataclass
class Otazka:
    id: str
    text: str
    typ: Literal["vyber", "multi", "skala", "otevrena"] = "vyber"
    kategorie: list[str] = field(default_factory=list)
    skala: tuple[int, int] = (1, 5)
    popisky_skaly: tuple[str, str] = ("rozhodne ne", "rozhodne ano")
    max_slov: int = 25
    povolit_nevim: bool = True
    filtr: str | None = None   # napr. "O1 == 'ano'" — kdo neprosel, ma None
    hypoteticka: bool = False  # "kdyby...", zvysene riziko kolapsu variance (viz QC)
    topics: list[str] = field(default_factory=list)  # explicitní metadata mají přednost před auto-routerem
    # Explicit, auditable survey-response mechanisms. No direction is guessed from stereotypes.
    response_process: dict[str, Any] = field(default_factory=dict)
    # Optional experimental framings: [{"id":"gain","text":"..."}, {"id":"loss","text":"..."}]
    variants: list[dict[str, str]] = field(default_factory=list)
    # Optional coding categories for an open verbatim. The model returns text + code
    # in the SAME structured response; no second LLM classification pass.
    kodovaci_kategorie: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.typ not in TYPY:
            raise ValueError(f"{self.id}: typ musi byt jeden z {TYPY}")
        if self.typ in ("vyber", "multi") and not self.kategorie:
            raise ValueError(f"{self.id}: typ '{self.typ}' vyzaduje kategorie.")

    @property
    def volby(self) -> list[str]:
        if self.typ in ("vyber", "multi"):
            return list(self.kategorie) + (
                ["Nevím / neodpovím"] if self.povolit_nevim else [])
        return []

    def zadani(self) -> str:
        r = [f"[{self.id}] {self.text}"]
        if self.typ in ("vyber", "multi"):
            r += [f"   {i+1}. {k}" for i, k in enumerate(self.volby)]
            r.append("   -> odpověz " + ("čísly možností, pole"
                                         if self.typ == "multi" else "číslem možnosti"))
        elif self.typ == "skala":
            a, b = self.skala
            r.append(f"   -> odpověz celým číslem {a}–{b} "
                     f"({a} = {self.popisky_skaly[0]}, {b} = {self.popisky_skaly[1]})"
                     + (", nebo null když nevíš" if self.povolit_nevim else ""))
        else:
            r.append(f"   -> odpověz vlastními slovy, max {self.max_slov} slov, "
                     "mluvenou češtinou")
        # Routing condition is executed by Python before prompting. The LLM
        # deliberately does not see the filter expression: if the question is
        # shown, eligibility has already been established.
        if self.hypoteticka:
            r.append("   -> HYPOTETICKÁ otázka: přemýšlej, jak by TENTO konkrétní "
                     "člověk reagoval, ne co je \"správná\" nebo statisticky "
                     "nejpravděpodobnější odpověď")
        return "\n".join(r)

    def schema(self) -> str:
        if self.typ == "vyber":
            return f'"{self.id}": <číslo 1-{len(self.volby)}>'
        if self.typ == "multi":
            return f'"{self.id}": [<čísla 1-{len(self.volby)}>]'
        if self.typ == "skala":
            return f'"{self.id}": <{self.skala[0]}-{self.skala[1]} nebo null>'
        return f'"{self.id}": "<text>"'


SYSTEM_DOT = """Jsi respondent v sekvenčním výzkumu konkrétní populace nebo audience.
Dostaneš profil konkrétního člověka, jeho dřívější odpovědi v TOMTO rozhovoru a právě
JEDNU aktuální otázku. Odpovídej jako tento člověk, nikoli jako průměrný Čech.

Pravidla:
- Používej jen informace v profilu a předchozí odpovědi; nevymýšlej další životní fakta.
- Předchozí odpovědi zachovej konzistentní, ale neopakuj je mechanicky.
- Nevidíš žádné budoucí otázky a nerozhoduješ o routingu dotazníku.
- Řádek „Jak odpovídá v dotaznících" popisuje response style, ne názory.
- U otevřené otázky piš krátkou mluvenou češtinou.
- Když vracíš pravděpodobnosti, vyjadřují nejistotu TOHOTO konkrétního respondenta;
  nesmíš je nahrazovat odhadem celé cílové populace.

Výsledek odešli pouze přes nástroj submit_survey_response."""

UZIV_DOT = """PROFIL PRO TUTO OTÁZKU:
{persona}

PŘEDCHOZÍ ODPOVĚDI V TOMTO ROZHOVORU:
{historie}

REÁLNÉ KOTVY (pokud jsou k dispozici):
{anchors}

AKTUÁLNÍ OTÁZKA:
{otazka}

{instrukce}"""


def _response_tool(o: Otazka, response_mode: str = "probability") -> dict:
    """Forced client-side tool schema: reliable structured response, no free JSON parsing."""
    if response_mode not in {"choice", "probability"}:
        raise ValueError("response_mode musi byt choice | probability")
    if response_mode == "probability" and o.typ == "vyber":
        k = len(o.volby)
        props = {"probabilities": {"type": "array", "minItems": k, "maxItems": k,
                                    "items": {"type": "number", "minimum": 0, "maximum": 1}}}
        req = ["probabilities"]
    elif response_mode == "probability" and o.typ == "skala":
        k = o.skala[1] - o.skala[0] + 1 + (1 if o.povolit_nevim else 0)
        props = {"probabilities": {"type": "array", "minItems": k, "maxItems": k,
                                    "items": {"type": "number", "minimum": 0, "maximum": 1}}}
        req = ["probabilities"]
    elif o.typ == "vyber":
        props = {"answer": {"type": "integer", "minimum": 1, "maximum": len(o.volby)}}
        req = ["answer"]
    elif o.typ == "multi":
        props = {"answer": {"type": "array", "uniqueItems": True,
                            "items": {"type": "integer", "minimum": 1,
                                      "maximum": len(o.volby)}}}
        req = ["answer"]
    elif o.typ == "skala":
        schema = {"type": "integer", "minimum": o.skala[0], "maximum": o.skala[1]}
        if o.povolit_nevim:
            schema = {"anyOf": [schema, {"type": "null"}]}
        props = {"answer": schema}
        req = ["answer"]
    else:
        props = {"answer": {"type": "string", "maxLength": 600}}
        req = ["answer"]
        if o.kodovaci_kategorie:
            props["category"] = {"type": "integer", "minimum": 1, "maximum": len(o.kodovaci_kategorie)}
            req.append("category")
    return {
        "name": "submit_survey_response",
        "description": "Submit the response of this synthetic survey respondent to the current question.",
        "input_schema": {"type": "object", "properties": props,
                         "required": req, "additionalProperties": False},
    }


def build_dotaznik_kw(persona: str, otazky: list[Otazka],
                      kontext_text: str = "", historie: str = "(žádné)",
                      response_mode: str = "probability", anchors_text: str = "") -> dict:
    """Build one-question request with forced structured tool output."""
    if len(otazky) != 1:
        raise ValueError("Produkční engine smí promptovat právě jednu otázku.")
    o = otazky[0]
    system_text = SYSTEM_DOT
    if kontext_text:
        system_text += "\n\n" + kontext_text
    if response_mode == "probability" and o.typ == "vyber":
        instr = (f"Vrať {len(o.volby)} pravděpodobností ve stejném pořadí jako možnosti. "
                 "Součet může být přibližně 1; runtime jej normalizuje. Nevybírej finální možnost.")
    elif response_mode == "probability" and o.typ == "skala":
        k = o.skala[1] - o.skala[0] + 1
        tail = " a poslední pro 'nevím'" if o.povolit_nevim else ""
        instr = (f"Vrať pravděpodobnosti pro hodnoty {o.skala[0]} až {o.skala[1]} "
                 f"({k} položek{tail}) ve vzestupném pořadí. Runtime odpověď vylosuje externě.")
    else:
        instr = "Vrať jedinou odpověď v poli answer podle schématu nástroje."
    return {
        "system": [{"type": "text", "text": system_text,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": UZIV_DOT.format(
            persona=persona, historie=historie, anchors=anchors_text or "(žádné)", otazka=o.zadani(), instrukce=instr)}],
        "tools": [_response_tool(o, response_mode)],
        "tool_choice": {"type": "tool", "name": "submit_survey_response"},
        "temperature": 0.0 if response_mode == "probability" else 1.0,
    }


SYSTEM_DOT_BLOCK = """Jsi respondent v sekvenčním výzkumu konkrétní populace nebo audience.
Dostaneš profil JEDNOHO konkrétního člověka, jeho dřívější odpovědi a krátký blok
aktuálních otázek. Odpovídej jako tento člověk, nikoli jako průměrný Čech.

Pravidla:
- Otázky řeš přesně v uvedeném pořadí. Odpověď na pozdější otázku nesmí zpětně
  změnit odpověď na dřívější otázku.
- Používej jen informace v profilu, kotvách a předchozích odpovědích; nevymýšlej
  další životní fakta ani populační distribuce.
- Jednotlivé respondenty nikdy neporovnávej a nepřenášej mezi nimi informace.
- Pravděpodobnosti popisují nejistotu tohoto respondenta, ne celé populace.
- Vrať přesně jeden strukturovaný objekt obsahující odpověď pro každé ID otázky.

Výsledek odešli pouze přes nástroj submit_survey_response_block."""


def _block_instruction(o: Otazka, response_mode: str) -> str:
    if response_mode == "probability" and o.typ == "vyber":
        return (f"Vrať {len(o.volby)} pravděpodobností ve stejném pořadí jako možnosti; "
                "runtime je normalizuje a finální odpověď vylosuje externě.")
    if response_mode == "probability" and o.typ == "skala":
        k = o.skala[1] - o.skala[0] + 1
        tail = " plus poslední pro 'nevím'" if o.povolit_nevim else ""
        return (f"Vrať pravděpodobnosti pro {k} hodnot od {o.skala[0]} do {o.skala[1]}"
                f"{tail} ve vzestupném pořadí.")
    return "Vrať jedinou odpověď v poli answer podle schématu."


def build_dotaznik_block_kw(
    persona: str,
    otazky: list[Otazka],
    *,
    historie: str = "(žádné)",
    response_mode: str = "probability",
    contexts: dict[str, str] | None = None,
    anchors: dict[str, str] | None = None,
) -> dict:
    """Build one respondent request for a short sequential question block.

    The persona and prior history occur once per block instead of once per question.
    Each question retains its own strict schema, context and optional evidence anchors.
    Filtered questions are deliberately excluded by the caller because their routing
    depends on answers that do not exist until the preceding block has been parsed.
    """
    if not (2 <= len(otazky) <= 8):
        raise ValueError("Respondentní blok musí obsahovat 2 až 8 otázek.")
    if any(o.filtr or o.typ == "otevrena" for o in otazky):
        raise ValueError("Filtrované a otevřené otázky musí zůstat mimo úsporný blok.")
    contexts = dict(contexts or {})
    anchors = dict(anchors or {})
    sections = []
    properties: dict[str, Any] = {}
    for pos, o in enumerate(otazky, 1):
        ctx = contexts.get(o.id) or "(žádný dodatečný kontext)"
        anc = anchors.get(o.id) or "(žádné)"
        sections.append(
            f"OTÁZKA {pos}/{len(otazky)}\n"
            f"Kontext: {ctx}\nKotvy: {anc}\n{o.zadani()}\n{_block_instruction(o, response_mode)}"
        )
        properties[o.id] = _response_tool(o, response_mode)["input_schema"]
    schema = {
        "type": "object",
        "properties": properties,
        "required": [o.id for o in otazky],
        "additionalProperties": False,
    }
    content = (
        "PROFIL RESPONDENTA PRO TENTO BLOK:\n" + persona +
        "\n\nPŘEDCHOZÍ ODPOVĚDI PŘED TÍMTO BLOKEM:\n" + historie +
        "\n\n" + "\n\n".join(sections)
    )
    return {
        "system": [{"type": "text", "text": SYSTEM_DOT_BLOCK,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": content}],
        "tools": [{
            "name": "submit_survey_response_block",
            "description": "Submit all answers for one synthetic respondent and this question block.",
            "input_schema": schema,
        }],
        "tool_choice": {"type": "tool", "name": "submit_survey_response_block"},
        "temperature": 0.0 if response_mode == "probability" else 1.0,
        "_npc_questions_per_case": len(otazky),
        "_npc_question_ids": [o.id for o in otazky],
    }


def _json_obj(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text or "", re.S)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}


def _entropy(probs: np.ndarray) -> float | None:
    if probs.size <= 1:
        return None
    p = probs[probs > 0]
    if not len(p):
        return None
    h = -float(np.sum(p * np.log(p)))
    return round(h / np.log(probs.size), 4)


def _parse_response(text: str, o: Otazka, response_mode: str,
                    rng: np.random.Generator, *, behavior_style=None, respondent=None,
                    dispersion_temperature: float = 1.0) -> tuple[Any, dict[str, Any]]:
    obj = _json_obj(text)
    meta: dict[str, Any] = {}
    if response_mode == "probability" and o.typ in {"vyber", "skala"}:
        raw = obj.get("probabilities")
        if not isinstance(raw, list):
            return None, {"parse_error": "missing_probabilities"}
        probs = np.asarray(raw, dtype=float)
        expected = (len(o.volby) if o.typ == "vyber" else
                    o.skala[1] - o.skala[0] + 1 + (1 if o.povolit_nevim else 0))
        if len(probs) != expected or not np.isfinite(probs).all():
            return None, {"parse_error": "invalid_probability_vector"}
        probs = np.clip(probs, 0, None)
        if probs.sum() <= 0:
            return None, {"parse_error": "zero_probability_mass"}
        probs = probs / probs.sum()
        raw_probs = probs.copy()
        from dispersion_calibration import temperature_scale
        probs = temperature_scale(probs, dispersion_temperature)
        base_probs = probs.copy()
        from behavior import adjust_probabilities
        probs, bmeta = adjust_probabilities(probs, o, behavior_style, respondent)
        idx = int(rng.choice(np.arange(expected), p=probs))
        meta = {"entropy": _entropy(probs), "max_prob": round(float(probs.max()), 4),
                "probabilities": [round(float(x), 6) for x in probs],
                "base_probabilities": [round(float(x), 6) for x in base_probs],
                "raw_probabilities": [round(float(x), 6) for x in raw_probs],
                "dispersion_temperature": round(float(dispersion_temperature), 4),
                "behavior_l1": bmeta.l1_shift, "behavior_applied": bmeta.applied}
        if o.typ == "vyber":
            return o.volby[idx], meta
        n_scale = o.skala[1] - o.skala[0] + 1
        if idx >= n_scale:
            return None, meta
        return o.skala[0] + idx, meta

    v = obj.get("answer")
    if o.typ == "vyber":
        try:
            i = int(v)
            return (o.volby[i - 1] if 1 <= i <= len(o.volby) else None), meta
        except (TypeError, ValueError):
            return None, {"parse_error": "invalid_choice"}
    if o.typ == "multi":
        vals = v if isinstance(v, list) else [v]
        out = []
        for x in vals:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if 1 <= i <= len(o.volby):
                out.append(o.volby[i - 1])
        return (list(dict.fromkeys(out)) or None), meta
    if o.typ == "skala":
        if v is None and o.povolit_nevim:
            return None, meta
        try:
            i = int(v)
            return (i if o.skala[0] <= i <= o.skala[1] else None), meta
        except (TypeError, ValueError):
            return None, {"parse_error": "invalid_scale"}
    txt=(str(v).strip()[:600] if v else None)
    if o.kodovaci_kategorie:
        try:
            ci=int(obj.get("category")); meta["coded_category"]=o.kodovaci_kategorie[ci-1] if 1<=ci<=len(o.kodovaci_kategorie) else None
        except (TypeError,ValueError): meta["coded_category"]=None
    return txt, meta

def _eval_filtr_node(node: ast.AST, odpovedi: dict[str, Any]) -> Any:
    """Bezpečný evaluator jednoduchých survey filtrů bez eval()."""
    if isinstance(node, ast.Expression):
        return _eval_filtr_node(node.body, odpovedi)
    if isinstance(node, ast.Name):
        return odpovedi.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_eval_filtr_node(x, odpovedi) for x in node.elts]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not bool(_eval_filtr_node(node.operand, odpovedi))
    if isinstance(node, ast.BoolOp):
        vals = [_eval_filtr_node(v, odpovedi) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Compare):
        left = _eval_filtr_node(node.left, odpovedi)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval_filtr_node(comp, odpovedi)
            if isinstance(op, ast.Eq): ok = left == right
            elif isinstance(op, ast.NotEq): ok = left != right
            elif isinstance(op, ast.In): ok = left in right
            elif isinstance(op, ast.NotIn): ok = left not in right
            elif isinstance(op, ast.Is): ok = left is right
            elif isinstance(op, ast.IsNot): ok = left is not right
            elif isinstance(op, ast.Gt): ok = left is not None and left > right
            elif isinstance(op, ast.GtE): ok = left is not None and left >= right
            elif isinstance(op, ast.Lt): ok = left is not None and left < right
            elif isinstance(op, ast.LtE): ok = left is not None and left <= right
            else: raise ValueError(f"Nepodporovaný operátor ve filtru: {ast.dump(op)}")
            if not ok:
                return False
            left = right
        return True
    raise ValueError(f"Nepodporovaný výraz ve filtru: {ast.dump(node)}")


def filtr_plati(expr: str | None, odpovedi: dict[str, Any]) -> bool:
    if not expr:
        return True
    # Same normalization as the linter, so a filter that passed the project check
    # cannot fail at runtime (and vice versa).
    from filter_syntax import repair_filter
    expr = repair_filter(expr, set(odpovedi.keys()))[0] or expr
    try:
        tree = ast.parse(expr, mode="eval")
        return bool(_eval_filtr_node(tree, odpovedi))
    except (SyntaxError, TypeError, ValueError) as e:
        raise ValueError(f"Neplatný filtr '{expr}': {e}") from e


def _historie_text(odpovedi: dict[str, Any], otazky_map: dict[str, Otazka],
                    max_polozek: int = 8) -> str:
    items = [(oid, val) for oid, val in odpovedi.items() if val is not None]
    if not items:
        return "(žádné)"
    radky = []
    for oid, val in items[-max_polozek:]:
        q = otazky_map.get(oid)
        txt = q.text if q else oid
        radky.append(f"- [{oid}] {txt} -> {val}")
    return "\n".join(radky)


def _parse_dotaznik(text: str, otazky: list[Otazka]) -> dict[str, Any]:
    raw = text if text.strip().startswith("{") else "{" + text
    try:
        obj = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception:
        obj = {}
    out: dict[str, Any] = {}
    for o in otazky:
        v = obj.get(o.id)
        if o.typ == "vyber":
            try:
                i = int(v)
                out[o.id] = o.volby[i - 1] if 1 <= i <= len(o.volby) else None
            except (TypeError, ValueError):
                out[o.id] = None
        elif o.typ == "multi":
            vals = v if isinstance(v, list) else [v]
            out[o.id] = [o.volby[int(i) - 1] for i in vals
                         if str(i).isdigit() and 1 <= int(i) <= len(o.volby)] or None
        elif o.typ == "skala":
            try:
                i = int(v)
                out[o.id] = i if o.skala[0] <= i <= o.skala[1] else None
            except (TypeError, ValueError):
                out[o.id] = None
        else:
            out[o.id] = str(v).strip()[:600] if v else None
    return out


def _mock_dotaznik(kw: dict, i: int, otazky: list[Otazka], seed: int = 0,
                   response_mode: str = "probability") -> str:
    o = otazky[0]
    h = hashlib.sha256((str(kw["messages"][0]["content"]) + str(seed) + str(i)).encode()).hexdigest()
    if response_mode == "probability" and o.typ in {"vyber", "skala"}:
        k = (len(o.volby) if o.typ == "vyber" else
             o.skala[1] - o.skala[0] + 1 + (1 if o.povolit_nevim else 0))
        vals = np.array([int(h[(j * 6) % 56:(j * 6) % 56 + 6], 16) + 1 for j in range(k)], dtype=float)
        vals = vals / vals.sum()
        return json.dumps({"probabilities": vals.tolist()}, ensure_ascii=False)
    if o.typ == "vyber":
        return json.dumps({"answer": int(h[:8], 16) % len(o.volby) + 1})
    if o.typ == "multi":
        a = int(h[:8], 16) % len(o.volby) + 1
        b = int(h[8:16], 16) % len(o.volby) + 1
        return json.dumps({"answer": sorted(set([a, b]))})
    if o.typ == "skala":
        a, b = o.skala
        return json.dumps({"answer": a + int(h[:8], 16) % (b - a + 1)})
    out={"answer":"[dry-run verbatim]"}
    if o.kodovaci_kategorie: out["category"]=int(h[8:16],16)%len(o.kodovaci_kategorie)+1
    return json.dumps(out,ensure_ascii=False)


# ---------------------------------------------------------------- behavioral / experimental helpers

def _variant_for(o: Otazka, case_id: str, seed: int | None) -> tuple[Otazka, str | None]:
    if not o.variants:
        return o, None
    variants = [v for v in o.variants if isinstance(v, dict) and v.get("text")]
    if not variants:
        return o, None
    h = hashlib.sha256(f"{case_id}|{o.id}|{seed or 0}|frame".encode()).hexdigest()
    v = variants[int(h[:12], 16) % len(variants)]
    vid = str(v.get("id") or f"v{variants.index(v)+1}")
    return replace(o, text=str(v["text"]), variants=[]), vid


# ---------------------------------------------------------------- beh

def run_dotaznik(
    otazky: list[Otazka] | list[dict],
    n: int = 500,
    filtry: dict[str, Any] | None = None,
    *,
    nazev: str = "pruzkum",
    panel: Panel | None = None,
    panel_path: str | Path | None = None,
    model: str = RUN_DEFAULTS["model"],
    mode: str = RUN_DEFAULTS["mode"],
    seed: int | None = None,
    workers: int = 8,
    ulozit: bool = True,
    tichy: bool = False,
    kontext_udalosti: "list | None" = None,
    posun_sila: float = 1.0,
    persona_mode: str = RUN_DEFAULTS["persona_mode"],
    persona_topic_allowlist: list[str] | None = None,
    panel_mode: str = "standard",
    ai_panel_profile: dict[str, Any] | None = None,
    response_mode: str = RUN_DEFAULTS["response_mode"],
    allow_own_estimates: bool = RUN_DEFAULTS["allow_own_estimates"],
    shuffle_persona: bool = False,
    context_sha256: str | None = None,
    run_dir: str | Path | None = None,
    resume_dir: str | Path | None = None,
    checkpoint: bool | None = None,
    selection_weights: pd.Series | np.ndarray | None = None,
    segment_meta: dict[str, Any] | None = None,
    anchor_config: dict[str, Any] | None = None,
    dispersion_config: dict[str, Any] | None = None,
    min_effective_n: float = 50.0,
    provider_policy: str = "fallback",
    budget_max_usd: float | None = None,
    progress_callback=None,
    cancel_check=None,
) -> dict:
    """Sekvenční questionnaire engine.

    Každá otázka se klasifikuje a promptuje samostatně. Respondent nevidí
    budoucí otázky; filtry vykonává kód, nikoli LLM. Tím se odstraňuje
    cross-question topic leakage a routing hallucination z v1.
    """
    policy = str(provider_policy or "fallback").lower()
    if policy in {"strict_openai","openai_only"}:
        provider = "openai"
    elif policy in {"strict_claude_code_subscription","claude_code_subscription_only"}:
        provider = "claude_code_subscription"
    else:
        provider = "anthropic"
    model = resolve_provider_model(provider, model)
    if response_mode not in {"choice", "probability"}:
        raise ValueError("response_mode musi byt choice | probability")
    if checkpoint is None:
        checkpoint = bool(ulozit or resume_dir)
    otazky = [o if isinstance(o, Otazka) else Otazka(**o) for o in otazky]
    if len({o.id for o in otazky}) != len(otazky):
        raise ValueError("ID otazek musi byt unikatni.")
    # Syntax filtrů validujeme ještě před jakýmkoli placeným voláním.
    for o in otazky:
        if o.filtr:
            ast.parse(o.filtr, mode="eval")

    from holdout_registry import assert_holdout_clean
    assert_holdout_clean()
    if panel is None:
        resolved_panel_path = Path(panel_path or PANEL_PATH)
        panel = Panel.load(resolved_panel_path)
    else:
        inferred = getattr(panel, "source_path", None)
        if panel_path is None and inferred is None and (ulozit or resume_dir):
            raise ValueError("In-memory Panel used with persisted run: pass panel_path so the manifest can bind to exact bytes.")
        resolved_panel_path = Path(panel_path or inferred or PANEL_PATH)
    run_id = (Path(resume_dir).name if resume_dir else
              time.strftime("%Y%m%d-%H%M%S") + "_" +
              hashlib.sha256(f"{nazev}|{seed}|{n}".encode()).hexdigest()[:8])
    work_dir = Path(resume_dir) if resume_dir else Path(run_dir or (RUNS_DIR / run_id))
    completed: set[str] = set()
    resume_progress: dict[str, Any] = {}
    prior_summary: dict[str, Any] = {}
    from persona_calibration import runtime_manifest as persona_calibration_manifest, resolve_effective_mode as resolve_calibrated_persona_mode
    persona_calibration_run = persona_calibration_manifest(persona_mode)
    brief_manifest = {"nazev": nazev, "n": n, "filtry": filtry or {},
                      "otazky": [o.__dict__ for o in otazky],
                      "persona_mode": persona_mode,
                      "panel_mode": panel_mode,
                      "ai_panel_profile_id": (ai_panel_profile or {}).get("profile_id", "") if panel_mode == "ai_panel" else "",
                      "persona_calibration_profile_hash": persona_calibration_run.get("profile_hash", "") if isinstance(persona_calibration_run, dict) else "",
                      "allow_own_estimates": bool(allow_own_estimates),
                      "shuffle_persona": bool(shuffle_persona),
                      "context_sha256": context_sha256 or "",
                      "segment": segment_meta or {},
                      "anchors": anchor_config or {},
                      "dispersion": dispersion_config or {},
                      "min_effective_n": float(min_effective_n),
                      "provider_policy": str(provider_policy),
                      "respondent_execution_mode": ("grouped_multiquestion_batch_v2" if provider=="claude_code_subscription" and mode!="dry" else "respondent_level")}
    sampling_audit: dict[str, Any] = {}
    if resume_dir:
        manifest_path = work_dir / "manifest.json"
        if not manifest_path.exists() or not (work_dir / "checkpoint.pkl").exists():
            raise FileNotFoundError("Resume dir neobsahuje manifest.json + checkpoint.pkl")
        old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sampling_audit = dict(old_manifest.get("representativeness") or {})
        if old_manifest.get("panel_sha256") != sha256_file(resolved_panel_path):
            raise RuntimeError("Panel se od checkpointu změnil; resume je zablokován.")
        if old_manifest.get("brief_sha256") != sha256_json(brief_manifest):
            # Checkpoints created by 17.8.7 v1 remain valid: the questionnaire,
            # panel and already journaled answers are unchanged; only the packing
            # of future provider calls is more efficient in v2.
            legacy_brief = dict(brief_manifest)
            legacy_brief["respondent_execution_mode"] = "grouped_question_batch_v1"
            if old_manifest.get("brief_sha256") != sha256_json(legacy_brief):
                raise RuntimeError("Brief/otázky se od checkpointu změnily; resume je zablokován.")
        for key, current in (("model", model), ("response_mode", response_mode),
                             ("seed", seed), ("context_sha256", context_sha256 or ""),
                             ("provider_policy", str(provider_policy))):
            if old_manifest.get(key) != current:
                raise RuntimeError(f"Resume parametr '{key}' se změnil; resume je zablokován.")
        old_budget=old_manifest.get("budget_max_usd")
        if old_budget is not None and budget_max_usd is not None and float(budget_max_usd)+1e-12<float(old_budget):
            raise RuntimeError("Resume budget lze pouze zvýšit nebo ponechat.")
        detail = pd.read_pickle(work_dir / "checkpoint.pkl")
        n = len(detail)
        cols = [c for c in panel.df.columns if c in detail.columns]
        vzorek = detail[cols + [c for c in ["_zdroj_index", "_persona_zdroj_index", "_sample_poradi", "synthetic_case_id"] if c in detail.columns]].copy()
        progress_path = work_dir / "progress.json"
        if progress_path.exists():
            resume_progress = json.loads(progress_path.read_text(encoding="utf-8"))
            completed = set(resume_progress.get("completed", []))
        summary_path = work_dir / "souhrn.json"
        if summary_path.exists():
            prior_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        vzorek = sample_representative(panel, n, filtry, seed, selection_weights=selection_weights).copy()
        sampling_audit = dict(vzorek.attrs.get("representativeness") or {})
        vzorek["synthetic_case_id"] = [f"{run_id}-{i+1:06d}" for i in range(len(vzorek))]
        if shuffle_persona:
            rng_persona = np.random.default_rng((seed or 0) + 771337)
            perm = rng_persona.permutation(vzorek["_zdroj_index"].to_numpy())
            # Avoid accidental fixed points where possible so shuffled really means shuffled.
            if len(perm) > 1:
                fixed = perm == vzorek["_zdroj_index"].to_numpy()
                if fixed.any():
                    perm = np.roll(perm, 1)
            vzorek["_persona_zdroj_index"] = perm
        else:
            vzorek["_persona_zdroj_index"] = vzorek["_zdroj_index"].to_numpy()
        detail = vzorek.copy()
        if ulozit or checkpoint:
            work_dir.mkdir(parents=True, exist_ok=True)
            mani = build_manifest(run_id=run_id, panel_path=resolved_panel_path,
                                  brief=brief_manifest, model=model, mode=mode, seed=seed,
                                  n=n, response_mode=response_mode,
                                  extra={"allow_own_estimates": bool(allow_own_estimates),
                                         "shuffle_persona": bool(shuffle_persona),
                                         "context_sha256": context_sha256 or "",
                                         "provider_policy": str(provider_policy),
                                         "budget_max_usd": budget_max_usd,
                                         "temperature": 0.0 if response_mode=="probability" else 1.0,
                                         "prompt_template_sha256": hashlib.sha256((SYSTEM_DOT+"\n---\n"+UZIV_DOT).encode("utf-8")).hexdigest(),
                                         "sample_id_sha256": sha256_json(vzorek["_zdroj_index"].astype(int).tolist()),
                                         "representativeness": sampling_audit})
            save_manifest(mani, work_dir / "manifest.json")

    from dispozice import odvod_temata
    from kontext import vyber_kontext, sestav_kontext_text, aplikuj_posun

    log = (lambda *a: None) if tichy else print
    odpovedi: list[dict[str, Any]] = [{} for _ in range(n)]
    chyby: list[list[str]] = [[] for _ in range(n)]
    # Allocate all per-question columns in one concat. Besides being faster for large
    # object batteries this prevents pandas DataFrame fragmentation warnings.
    init_cols: dict[str, Any] = {}
    for o in otazky:
        defaults = {
            o.id: None, f"_eligible_{o.id}": False, f"_chyba_{o.id}": None,
            f"_entropy_{o.id}": np.nan, f"_maxprob_{o.id}": np.nan,
            f"_probs_{o.id}": None, f"_probs_base_{o.id}": None, f"_probs_raw_{o.id}": None,
            f"_behavior_l1_{o.id}": np.nan, f"_behavior_{o.id}": None,
            f"_variant_{o.id}": None, f"_category_{o.id}": None,
            f"_persona_text_{o.id}": None, f"_provider_{o.id}": None,
            f"_provider_fallback_{o.id}": False, f"_fact_source_{o.id}": None,
            f"_fact_match_{o.id}": None,
            f"_language_qc_score_{o.id}": np.nan, f"_language_qc_flags_{o.id}": None,
        }
        for col, default in defaults.items():
            if col not in detail.columns:
                init_cols[col] = [default] * len(detail)
    if init_cols:
        detail = pd.concat([detail, pd.DataFrame(init_cols, index=detail.index)], axis=1)
    # 10.12 owner/audit export: persist the exact base persona and the exact
    # question-specific persona text used by the respondent engine. The safe
    # client export still uses an allowlist; the complete owner export retains
    # these columns for reproducibility and persona inspection.
    if "persona_text_base" not in detail.columns:
        base_personas = []
        for i in range(n):
            src = int(detail.iloc[i]["_persona_zdroj_index"])
            base_personas.append(generate_persona_text(
                panel.df.loc[src], panel.z.loc[src], panel.styly.loc[src], [],
                persona_mode=persona_mode, allow_own_estimates=allow_own_estimates))
        detail["persona_text_base"] = base_personas
    detail["persona_mode"] = persona_mode

    # Initial durable checkpoint BEFORE the first paid respondent call.
    # This is critical for first-question recovery: raw_journal_<qid>.jsonl may
    # already contain completed Claude batches even if the question itself did
    # not finish. Without checkpoint.pkl the workflow previously refused resume
    # and effectively discarded that durable journal after a worker/backend restart.
    if checkpoint:
        work_dir.mkdir(parents=True, exist_ok=True)
        cp_path=work_dir / "checkpoint.pkl"
        if not cp_path.exists():
            detail.to_pickle(cp_path)
        prog_path=work_dir / "progress.json"
        if not prog_path.exists():
            prog_path.write_text(json.dumps({
                "completed": [], "token_in": 0, "token_out": 0, "call_errors": 0,
                "provider_calls": 0,
                "fact_audit": {}, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "checkpoint_stage": "before_first_respondent_call"
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    if completed:
        for i in range(n):
            for oid in completed:
                if oid in detail.columns and pd.notna(detail.at[i, oid]):
                    odpovedi[i][oid] = detail.at[i, oid]

    otazky_map = {o.id: o for o in otazky}
    ti = int(resume_progress.get("token_in", 0))
    to = int(resume_progress.get("token_out", 0))
    call_errors = int(resume_progress.get("call_errors", 0))
    provider_call_count = int(resume_progress.get("provider_calls", 0))
    provider_usage_path=work_dir/"provider_usage.json"
    if provider_usage_path.exists():
        try: provider_call_count=max(provider_call_count,int(json.loads(provider_usage_path.read_text(encoding="utf-8")).get("provider_calls",0)))
        except Exception: pass
    def _record_provider_call() -> None:
        nonlocal provider_call_count
        provider_call_count += 1
        work_dir.mkdir(parents=True,exist_ok=True)
        tmp=provider_usage_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"provider_calls":provider_call_count,"updated_at":time.strftime("%Y-%m-%dT%H:%M:%S")},ensure_ascii=False),encoding="utf-8")
        tmp.replace(provider_usage_path)
    temata_meta: dict[str, list[str]] = dict(prior_summary.get("temata_po_otazkach", {}))
    kontext_meta: dict[str, list[dict[str, Any]]] = dict(prior_summary.get("kontext_pouzity", {}))
    anchor_meta: dict[str, dict[str, Any]] = dict(prior_summary.get("anchors", {}))
    anchor_cfg = dict(anchor_config or {})
    dispersion_cfg = dict(dispersion_config or {})
    anchor_bank = None
    if anchor_cfg.get("enabled"):
        from npc_ingest.response_bank import ResponseBank
        bank_path = anchor_cfg.get("registry_path", "data/ingest_registry.sqlite")
        try:
            anchor_bank = ResponseBank(bank_path)
        except Exception as e:
            if anchor_cfg.get("strict", False):
                raise
            log_msg = f"[anchors] banka není dostupná: {e}; běžím bez kotev"
            if not tichy: print(log_msg)
            anchor_bank = None
    # P0 factual contract is resolved before the first paid call. Unsupported
    # individual facts fail closed instead of being hallucinated by the persona.
    from factual_layer import classify_question, deterministic_answer, FACT_LAYER_VERSION
    fact_specs = {o.id: classify_question(o, set(panel.df.columns)) for o in otazky}
    unsupported = [(o.id, fact_specs[o.id].reason) for o in otazky if fact_specs[o.id].status == "UNSUPPORTED"]
    if unsupported and mode != "dry":
        msg = "; ".join(f"{qid}: {reason}" for qid, reason in unsupported[:8])
        raise RuntimeError("FACTUAL_LAYER_BLOCKED: " + msg)
    # Validate deterministic category mappings on the whole sampled base before any
    # paid question can run. This preserves fail-fast semantics even when a factual
    # question appears late in the questionnaire.
    if mode != "dry":
        for o in otazky:
            fs = fact_specs[o.id]
            if fs.status != "DIRECT": continue
            for src in vzorek["_zdroj_index"].astype(int).tolist():
                deterministic_answer(o, panel.df.loc[src], fs)
    legacy_calls=0;planned_calls=0;forecast_i=0
    legacy_cases=max(1,int(os.environ.get("NPC_RESPONDENT_BATCH_CASES","96") or 96))
    while forecast_i < len(otazky):
        fq=otazky[forecast_i]
        if fact_specs[fq.id].status=="DIRECT":
            forecast_i += 1; continue
        legacy_calls += (n+legacy_cases-1)//legacy_cases
        if provider=="claude_code_subscription" and mode!="dry" and not kontext_udalosti and not fq.filtr and fq.typ!="otevrena":
            group=[]
            for cand in otazky[forecast_i:forecast_i+max(1,min(8,int(os.environ.get("NPC_RESPONDENT_QUESTION_BLOCK_SIZE","6") or 6)))]:
                if cand.filtr or cand.typ=="otevrena" or fact_specs[cand.id].status=="DIRECT": break
                group.append(cand)
            if len(group)>=2:
                # The legacy comparison above must include every question absorbed
                # by this block, not only its first member.
                legacy_calls += (len(group)-1)*((n+legacy_cases-1)//legacy_cases)
                cap=max(16,BLOCK_CELL_BUDGET//len(group))
                planned_calls += (n+cap-1)//cap
                forecast_i += len(group); continue
        planned_calls += (n+legacy_cases-1)//legacy_cases
        forecast_i += 1
    call_forecast={"legacy_provider_calls":legacy_calls,"planned_provider_calls":planned_calls,
                   "estimated_reduction_pct":round(max(0.0,(1-planned_calls/max(1,legacy_calls))*100),1),
                   "respondents":n,"questions":len(otazky),"question_block_size":int(os.environ.get("NPC_RESPONDENT_QUESTION_BLOCK_SIZE","6") or 6)}
    if progress_callback is not None and provider=="claude_code_subscription" and mode!="dry":
        try: progress_callback({"phase":"respondent_cost_forecast",**call_forecast,"run_dir":str(work_dir),"execution_mode":"grouped_multiquestion_batch_v2"})
        except Exception: pass
    budget_guard = None
    if mode != "dry" and budget_max_usd is not None:
        from budget_guard import BudgetGuard
        budget_guard = BudgetGuard(budget_max_usd, model, provider=provider)
        if ti or to:
            budget_guard.charge(ti, to)
    fact_audit = {"version": FACT_LAYER_VERSION, "direct_questions": [], "unsupported_questions": [x[0] for x in unsupported],
                  "checked": 0, "matches": 0, "mismatches": 0}
    budget_exhausted = False
    t0 = time.time()

    question_block_size=max(1,min(8,int(os.environ.get("NPC_RESPONDENT_QUESTION_BLOCK_SIZE","6") or 6)))

    def _block_candidates(start_index: int) -> list[Otazka]:
        """Return a conservative consecutive block safe to answer in one turn."""
        if provider != "claude_code_subscription" or mode == "dry":
            return []
        if question_block_size < 2:
            return []
        # Explicit event overlays can alter the persona question by question. They
        # stay on the legacy single-question path rather than changing methodology.
        if kontext_udalosti:
            return []
        selected=[]
        for cand in otazky[start_index:start_index+question_block_size]:
            if cand.id in completed or cand.filtr or cand.typ == "otevrena":
                break
            if fact_specs[cand.id].status == "DIRECT":
                break
            selected.append(cand)
        return selected if len(selected) >= 2 else []

    def _journal_case_ids(path: Path) -> set[int]:
        found=set()
        if not path.exists():
            return found
        for line in path.read_text(encoding="utf-8").splitlines():
            try: found.add(int(json.loads(line)["local_j"]))
            except Exception: pass
        return found

    def _journal_uses_block_v2(path: Path) -> bool:
        if not path.exists(): return False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                result=json.loads(line).get("result") or {}
                return result.get("execution_mode")=="grouped_multiquestion_batch_v2"
            except Exception: pass
        return False

    def _prefetch_subscription_block(start_index: int, block: list[Otazka]) -> None:
        """Pay once for several questions and fan responses into legacy journals.

        Journals remain question/respondent-addressable, so an old v1 checkpoint can
        resume into v2 and every downstream parser continues to consume the exact
        same one-question response shape.
        """
        work_dir.mkdir(parents=True,exist_ok=True)
        from threading import Lock
        journal_lock=Lock()
        block_ids=[q.id for q in block]
        block_journal=work_dir/f"raw_block_{block_ids[0]}__{block_ids[-1]}.jsonl"
        journal_existing={qid:_journal_case_ids(work_dir/f"raw_journal_{qid}.jsonl") for qid in block_ids}

        def _fanout_result(original: int, result: dict, *, persona: str = "", persist_block: bool) -> None:
            try: payload=json.loads(str(result.get("text") or ""))
            except Exception as exc: raise RuntimeError(f"RESPONDENT_BLOCK_JSON_INVALID: {exc}") from exc
            if not isinstance(payload,dict) or any(not isinstance(payload.get(qid),dict) for qid in block_ids):
                raise RuntimeError("RESPONDENT_BLOCK_INCOMPLETE: "+",".join(qid for qid in block_ids if not isinstance(payload.get(qid),dict)))
            canonical=dict(result)
            canonical["execution_mode"]="grouped_multiquestion_batch_v2"
            canonical["question_block_ids"]=block_ids
            canonical["prompt_persona"]=persona or str(result.get("prompt_persona") or "")
            tin=int(result.get("tok_in") or 0);tout=int(result.get("tok_out") or 0);qn=len(block_ids)
            with journal_lock:
                # Canonical write comes first. If Windows/process termination lands
                # during fan-out, every missing per-question line is rebuilt locally
                # from this record on resume without another Claude call.
                if persist_block:
                    with block_journal.open("a",encoding="utf-8") as jf:
                        jf.write(json.dumps({"local_j":original,"result":canonical},ensure_ascii=False)+"\n")
                for pos,qid in enumerate(block_ids):
                    if original in journal_existing[qid]: continue
                    split_result=dict(canonical)
                    split_result["text"]=json.dumps(payload[qid],ensure_ascii=False)
                    split_result["tok_in"]=tin//qn+(1 if pos<tin%qn else 0)
                    split_result["tok_out"]=tout//qn+(1 if pos<tout%qn else 0)
                    path=work_dir/f"raw_journal_{qid}.jsonl"
                    with path.open("a",encoding="utf-8") as jf:
                        jf.write(json.dumps({"local_j":original,"result":split_result},ensure_ascii=False)+"\n")
                    journal_existing[qid].add(original)

        if block_journal.exists():
            for line in block_journal.read_text(encoding="utf-8").splitlines():
                try:
                    saved=json.loads(line);saved_result=saved.get("result") or {}
                    _fanout_result(int(saved["local_j"]),saved_result,
                                   persona=str(saved_result.get("prompt_persona") or ""),persist_block=False)
                except Exception: pass
        missing=[j for j in range(n) if j not in journal_existing[block_ids[0]]]
        if not missing: return

        block_topics: dict[str,list[str]]={}
        block_contexts: dict[str,str]={}
        variant_questions: dict[str,list[Otazka]]={}
        block_anchors: dict[str,list[str]]={}
        union_topics=[]
        for qo in block:
            if qo.topics:
                topics=list(dict.fromkeys(str(t).strip() for t in qo.topics if str(t).strip()))
            else:
                topics=odvod_temata(qo.text+" "+" ".join(qo.volby))
            if persona_topic_allowlist:
                allowed={str(x).strip().lower() for x in persona_topic_allowlist if str(x).strip()}
                topics=[t for t in topics if str(t).strip().lower() in allowed]
            block_topics[qo.id]=topics
            for topic in topics:
                if topic not in union_topics: union_topics.append(topic)
            # Event overlays are disabled for block mode above; retain the explicit
            # empty value so the actual prompt remains auditable.
            block_contexts[qo.id]=""
            variants=[]
            anchors_for_q=[]
            for local_j in range(n):
                case_id=str(detail.iloc[local_j]["synthetic_case_id"])
                qv,variant_id=_variant_for(qo,case_id,seed)
                variants.append(qv)
                if variant_id is not None:
                    detail.at[detail.index[local_j],f"_variant_{qo.id}"]=variant_id
                anchor_text=""
                if anchor_bank is not None:
                    from npc_ingest.response_bank import format_anchor_block
                    src=int(vzorek.iloc[local_j]["_persona_zdroj_index"])
                    prow=panel.df.loc[src]
                    persona_key={"pohlavi":prow.get("pohlavi"),"vek":prow.get("vek"),
                                 "vzdelani":prow.get("vzdelani"),"kraj":prow.get("kraj"),
                                 "trida":prow.get("trida_spolecenska")}
                    aa=anchor_bank.find_anchors(
                        persona_key,qv.text,k=int(anchor_cfg.get("k",8)),
                        topic=(topics[0] if topics else None),
                        current_year=int(anchor_cfg.get("current_year",2026)),
                        min_similarity=float(anchor_cfg.get("min_similarity",.18)))
                    anchor_text=format_anchor_block(aa)
                if str(panel_mode or "standard").lower()=="ai_panel" and ai_panel_profile:
                    try:
                        from reality_alignment import calibration_text
                        extra=calibration_text(ai_panel_profile,question_id=qo.id,topics=topics)
                        if extra: anchor_text=((anchor_text+"\n\n") if anchor_text else "")+extra
                    except Exception as exc:
                        log(f"[AI Panel] calibration overlay warning: {exc}")
                anchors_for_q.append(anchor_text)
            variant_questions[qo.id]=variants
            block_anchors[qo.id]=anchors_for_q

        personas=[]; histories=[]; kw_list=[]
        for local_j in missing:
            src=int(vzorek.iloc[local_j]["_persona_zdroj_index"])
            persona=generate_persona_text(
                panel.df.loc[src],panel.z.loc[src],panel.styly.loc[src],union_topics,
                persona_mode=persona_mode,allow_own_estimates=allow_own_estimates)
            history=_historie_text(odpovedi[local_j],otazky_map)
            personas.append(persona);histories.append(history)
            qs=[variant_questions[q.id][local_j] for q in block]
            kw_list.append(build_dotaznik_block_kw(
                persona,qs,historie=history,response_mode=response_mode,
                contexts=block_contexts,
                anchors={q.id:block_anchors[q.id][local_j] for q in block}))

        def _write_block_result(sub_j: int, result: dict) -> None:
            original=missing[sub_j]
            _fanout_result(original,result,persona=personas[sub_j],persist_block=True)

        def _block_progress(done_n,total_n):
            if progress_callback is not None:
                try: progress_callback({"phase":"respondent_block_progress","question_ids":block_ids,
                    "question_index":start_index+1,"question_total":len(otazky),
                    "respondent_completed":int(done_n),"respondent_total":int(total_n),
                    "completed_questions":len(completed),"run_dir":str(work_dir),
                    "execution_mode":"grouped_multiquestion_batch_v2"})
                except Exception: pass
        def _block_event(evt):
            if str((evt or {}).get("phase") or "") == "respondent_batch_start":
                _record_provider_call()
            if progress_callback is not None:
                try: progress_callback({**dict(evt or {}),"question_ids":block_ids,
                    "question_id":block_ids[0],"question_index":start_index+1,
                    "question_total":len(otazky),"completed_questions":len(completed),
                    "run_dir":str(work_dir),"execution_mode":"grouped_multiquestion_batch_v2"})
                except Exception: pass

        if progress_callback is not None:
            try: progress_callback({"phase":"respondent_question_block_start","question_ids":block_ids,
                "question_count":len(block_ids),"question_index":start_index+1,
                "question_total":len(otazky),"respondent_total":len(missing),
                "estimated_provider_calls":(len(missing)+max(1,BLOCK_CELL_BUDGET//len(block))-1)//max(1,BLOCK_CELL_BUDGET//len(block)),
                "execution_mode":"grouped_multiquestion_batch_v2","run_dir":str(work_dir)})
            except Exception: pass
        # max_tokens is a ceiling, not prepaid usage. Eighty tokens per closed
        # question leaves enough room for 15-item probability vectors plus JSON
        # keys without inviting truncation and an otherwise avoidable resume.
        max_tok=sum(80 if q.typ!="otevrena" else max(80,q.max_slov*3+30) for q in block)
        _call_llm(kw_list,model,mode,max_tokens=max_tok,workers=workers,
                  progress=_block_progress,on_result=_write_block_result,
                  provider_policy=provider_policy,budget_guard=budget_guard,
                  event_callback=_block_event,cancel_check=cancel_check)

    for qi, o in enumerate(otazky, 1):
        if cancel_check is not None and bool(cancel_check()):
            raise RuntimeError("JOB_CANCELLED")
        if progress_callback is not None:
            try: progress_callback({"phase":"question_start","question_id":o.id,"question_index":qi,"question_total":len(otazky),"completed":len(completed),"run_dir":str(work_dir),"provider":provider,"execution_mode":("grouped_multiquestion_batch_v2" if provider=="claude_code_subscription" and mode!="dry" else "respondent_level")})
            except Exception: pass
        if o.id in completed:
            log(f"[{o.id}] resume: již dokončeno — přeskakuji")
            continue
        if o.topics:
            temata = list(dict.fromkeys(str(t).strip() for t in o.topics if str(t).strip()))
            topic_source = "explicit"
        else:
            temata = odvod_temata(o.text + " " + " ".join(o.volby))
            topic_source = "auto" if temata else "core-only"
        if persona_topic_allowlist:
            allowed={str(x).strip().lower() for x in persona_topic_allowlist if str(x).strip()}
            filtered=[t for t in temata if str(t).strip().lower() in allowed]
            if temata and not filtered:
                topic_source += "+persona_allowlist_core_only"
            temata=filtered
        temata_meta[o.id] = {"topics": temata, "source": topic_source, "persona_topic_allowlist": list(persona_topic_allowlist or [])}

        # Vestavěný časový kontext se NIKDY nepřidává implicitně. Musí být
        # explicitně předán callerem; jinak by stárnoucí zpráva měnila survey.
        udalosti = [] if kontext_udalosti is None else kontext_udalosti
        kontext_bloky = vyber_kontext(temata, udalosti=udalosti)
        kontext_text = sestav_kontext_text(kontext_bloky)
        kontext_meta[o.id] = [
            {"id": b.id, "datum": b.datum, "zdroj": b.zdroj, "jistota": b.jistota}
            for b in kontext_bloky
        ]

        eligible = [i for i in range(n) if filtr_plati(o.filtr, odpovedi[i])]
        if not eligible:
            log(f"[{o.id}] routing: 0/{n} eligible — otázka přeskočena")
            continue
        detail.loc[eligible, f"_eligible_{o.id}"] = True

        qrows = vzorek.loc[eligible].copy()
        persona_src = qrows["_persona_zdroj_index"].astype(int).to_numpy()
        persona_rows = panel.df.loc[persona_src].copy().reset_index(drop=False)

        fspec = fact_specs[o.id]
        if fspec.status == "DIRECT":
            fact_audit["direct_questions"].append({"id": o.id, "field": fspec.field})
            for local_j, i in enumerate(eligible):
                # Facts follow the sampled respondent, never a shuffled persona source.
                src = int(vzorek.loc[i, "_zdroj_index"])
                row = panel.df.loc[src]
                val, meta = deterministic_answer(o, row, fspec)
                detail.at[i, o.id] = val
                detail.at[i, f"_provider_{o.id}"] = "deterministic_fact"
                detail.at[i, f"_provider_fallback_{o.id}"] = False
                detail.at[i, f"_fact_source_{o.id}"] = fspec.field
                detail.at[i, f"_fact_match_{o.id}"] = True
                odpovedi[i][o.id] = val
                fact_audit["checked"] += 1; fact_audit["matches"] += 1
            completed.add(o.id)
            if progress_callback is not None:
                try: progress_callback({"phase":"question_complete","question_id":o.id,"question_index":qi,"question_total":len(otazky),"completed":len(completed),"run_dir":str(work_dir)})
                except Exception: pass
            log(f"[{o.id}] deterministic fact: {fspec.field}; {len(eligible)}/{n} answers; 0 LLM calls")
            if checkpoint:
                work_dir.mkdir(parents=True, exist_ok=True)
                detail.to_pickle(work_dir / "checkpoint.pkl")
                (work_dir / "progress.json").write_text(json.dumps({
                    "completed": [x.id for x in otazky if x.id in completed], "token_in": ti, "token_out": to,
                    "call_errors": call_errors, "provider_calls": provider_call_count,
                    "fact_audit": fact_audit,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False, indent=2), encoding="utf-8")
            continue

        if kontext_bloky:
            persona_rows = aplikuj_posun(persona_rows, kontext_bloky, posun_sila)

        personas, histories = [], []
        for local_j, i in enumerate(eligible):
            row = persona_rows.iloc[local_j]
            src = int(persona_src[local_j])
            persona_text = generate_persona_text(
                row, panel.z.loc[src], panel.styly.loc[src], temata,
                persona_mode=persona_mode, allow_own_estimates=allow_own_estimates)
            personas.append(persona_text)
            detail.at[i, f"_persona_text_{o.id}"] = persona_text
            histories.append(_historie_text(odpovedi[i], otazky_map))

        max_tok = 50 if o.typ != "otevrena" else max(80, o.max_slov * 3 + 30)
        log(f"[{o.id}] {qi}/{len(otazky)}: {len(eligible)}/{n} eligible; "
            f"temata={','.join(temata) if temata else 'core-only'} ({topic_source})")
        prompt_questions = []
        for local_j, i in enumerate(eligible):
            case_id = str(detail.at[i, "synthetic_case_id"])
            qo, variant_id = _variant_for(o, case_id, seed)
            prompt_questions.append(qo)
            if variant_id is not None:
                detail.at[i, f"_variant_{o.id}"] = variant_id
        anchor_texts = ["" for _ in eligible]
        anchor_counts = []
        if anchor_bank is not None:
            from npc_ingest.response_bank import format_anchor_block
            for local_j, i in enumerate(eligible):
                row = persona_rows.iloc[local_j]
                persona_key = {
                    "pohlavi": row.get("pohlavi"), "vek": row.get("vek"),
                    "vzdelani": row.get("vzdelani"), "kraj": row.get("kraj"),
                    "trida": row.get("trida_spolecenska"),
                }
                aa = anchor_bank.find_anchors(
                    persona_key, prompt_questions[local_j].text,
                    k=int(anchor_cfg.get("k", 8)),
                    topic=(temata[0] if temata else None),
                    current_year=int(anchor_cfg.get("current_year", 2026)),
                    min_similarity=float(anchor_cfg.get("min_similarity", .18)),
                )
                anchor_texts[local_j] = format_anchor_block(aa)
                anchor_counts.append(len(aa))
        else:
            anchor_counts = [0 for _ in eligible]
        anchor_meta[o.id] = {
            "eligible": len(eligible), "with_anchor": int(sum(x > 0 for x in anchor_counts)),
            "coverage": round(float(sum(x > 0 for x in anchor_counts) / len(eligible)), 4) if eligible else 0.0,
            "mean_k": round(float(np.mean(anchor_counts)), 3) if anchor_counts else 0.0,
            "enabled": bool(anchor_cfg.get("enabled")),
        }
        if str(panel_mode or 'standard').lower() == 'ai_panel' and ai_panel_profile:
            try:
                from reality_alignment import calibration_text
                for _j,qo in enumerate(prompt_questions):
                    extra = calibration_text(ai_panel_profile, question_id=qo.id, topics=temata)
                    if extra:
                        anchor_texts[_j] = ((anchor_texts[_j] + '\n\n') if anchor_texts[_j] else '') + extra
            except Exception as _cal_exc:
                log(f"[AI Panel] calibration overlay warning: {_cal_exc}")
        journal_path = work_dir / f"raw_journal_{o.id}.jsonl"
        block=_block_candidates(qi-1)
        existing_journal=_journal_case_ids(journal_path)
        canonical_hint=(work_dir/f"raw_block_{block[0].id}__{block[-1].id}.jsonl") if block else None
        # A partial v1 journal resumes its current question on the legacy path;
        # mixing old one-question answers with a new block for the other half
        # would create an avoidable method split. A partial v2 block is safe to resume.
        if block and ((canonical_hint is not None and canonical_hint.exists()) or
                      (len(existing_journal) < len(eligible) and (not existing_journal or _journal_uses_block_v2(journal_path)))):
            _prefetch_subscription_block(qi-1,block)
        kw_list = [build_dotaznik_kw(p, [qo], kontext_text, h, response_mode=response_mode, anchors_text=a)
                   for p, h, qo, a in zip(personas, histories, prompt_questions, anchor_texts)]
        # Respondent-level raw journal: every completed paid call is durable before
        # parsing. A provider crash at 80% therefore does not throw away paid work;
        # resume sends only missing respondents for the current question.
        journal_rows: dict[int, dict] = {}
        if mode != "dry" and journal_path.exists():
            for line in journal_path.read_text(encoding="utf-8").splitlines():
                try:
                    item=json.loads(line); journal_rows[int(item["local_j"])]=item["result"]
                except Exception: pass
        missing=[j for j in range(len(kw_list)) if j not in journal_rows]
        syrove=[journal_rows.get(j) for j in range(len(kw_list))]
        if missing:
            if mode != "dry":
                work_dir.mkdir(parents=True, exist_ok=True)
                from threading import Lock
                journal_lock=Lock()
                def _journal_result(sub_j, result):
                    orig=missing[sub_j]
                    with journal_lock:
                        with journal_path.open("a",encoding="utf-8") as jf:
                            jf.write(json.dumps({"local_j":orig,"result":result},ensure_ascii=False)+"\n")
            else:
                _journal_result=None
            try:
                def _respondent_progress(done_n,total_n,oid=o.id,qidx=qi):
                    if not tichy: log(f"[{oid}] {done_n}/{total_n}")
                    if progress_callback is not None:
                        try: progress_callback({"phase":"respondent_progress","question_id":oid,"question_index":qidx,"question_total":len(otazky),"respondent_completed":int(done_n),"respondent_total":int(total_n),"completed_questions":len(completed),"run_dir":str(work_dir),"execution_mode":("grouped_multiquestion_batch_v2" if provider=="claude_code_subscription" and mode!="dry" else "respondent_level")})
                        except Exception: pass
                def _respondent_event(evt,oid=o.id,qidx=qi):
                    if str((evt or {}).get("phase") or "") == "respondent_batch_start":
                        _record_provider_call()
                    if progress_callback is not None:
                        try: progress_callback({**dict(evt or {}),"question_id":oid,"question_index":qidx,"question_total":len(otazky),"completed_questions":len(completed),"run_dir":str(work_dir)})
                        except Exception: pass
                if progress_callback is not None and provider=="claude_code_subscription" and mode!="dry":
                    try: progress_callback({"phase":"question_watchdog","question_id":o.id,"question_index":qi,"question_total":len(otazky),"respondent_total":len(missing),"batch_timeout_seconds":int(__import__('os').environ.get('NPC_RESPONDENT_BATCH_TIMEOUT_S','420') or 420),"question_timeout_seconds":int(__import__('os').environ.get('NPC_RESPONDENT_QUESTION_TIMEOUT_S','1800') or 1800),"policy":"batch timeout -> split; question watchdog -> automatic durable retry; completed cases stay checkpointed"})
                    except Exception: pass
                fresh = _call_llm(
                    [kw_list[j] for j in missing], model, mode, max_tokens=max_tok, workers=workers,
                    progress=_respondent_progress,
                    on_result=_journal_result, provider_policy=provider_policy, budget_guard=budget_guard,
                    event_callback=_respondent_event,cancel_check=cancel_check,
                    mock=lambda kw, j: _mock_dotaznik(
                        kw, j, [prompt_questions[missing[j]]], (seed or 0) + qi * 1009 + missing[j], response_mode=response_mode))
                for j,r in zip(missing,fresh): syrove[j]=r
            except Exception as exc:
                from budget_guard import BudgetExceeded
                if not isinstance(exc, BudgetExceeded): raise
                budget_exhausted=True
                # Recover every completed respondent from the durable journal and
                # explicitly mark the rest as budget-capped partial data.
                if journal_path.exists():
                    for line in journal_path.read_text(encoding="utf-8").splitlines():
                        try:
                            item=json.loads(line); syrove[int(item["local_j"])]=item["result"]
                        except Exception: pass
                for j in range(len(syrove)):
                    if syrove[j] is None:
                        syrove[j]={"text":"","tok_in":0,"tok_out":0,"chyba":"BUDGET_CAP","provider":"not_called","fallback_used":False}
        if any(r is None for r in syrove):
            raise RuntimeError(f"RESPONDENT_JOURNAL_INCOMPLETE: {o.id}")

        for local_j, r in enumerate(syrove):
            i = eligible[local_j]
            ti += r.get("tok_in", 0)
            to += r.get("tok_out", 0)
            if r.get("prompt_persona"):
                # For v2 blocks this is the exact union-topic persona that Claude
                # actually received, not the legacy per-question reconstruction.
                detail.at[i, f"_persona_text_{o.id}"] = str(r["prompt_persona"])
            detail.at[i, f"_provider_{o.id}"] = r.get("provider") or "unknown"
            detail.at[i, f"_provider_fallback_{o.id}"] = bool(r.get("fallback_used", False))
            if r["chyba"]:
                call_errors += 1
                msg = f"{o.id}: {r['chyba']}"
                chyby[i].append(msg)
                detail.at[i, f"_chyba_{o.id}"] = r["chyba"]
                continue
            rrng = np.random.default_rng((seed or 0) + qi * 1000003 + i * 9176)
            src = int(persona_src[local_j])
            topic_temps = dispersion_cfg.get("topic_temperatures") or {}
            dtemp = float(topic_temps.get((temata[0] if temata else "default"), dispersion_cfg.get("temperature", 1.0)))
            val, meta = _parse_response(
                r["text"], o, response_mode, rrng,
                behavior_style=panel.styly.loc[src], respondent=panel.df.loc[src],
                dispersion_temperature=dtemp)
            if meta.get("parse_error"):
                call_errors += 1
                err = meta["parse_error"]
                chyby[i].append(f"{o.id}: {err}")
                detail.at[i, f"_chyba_{o.id}"] = err
                continue
            detail.at[i, o.id] = val
            if meta.get("entropy") is not None:
                detail.at[i, f"_entropy_{o.id}"] = meta["entropy"]
            if meta.get("max_prob") is not None:
                detail.at[i, f"_maxprob_{o.id}"] = meta["max_prob"]
            if meta.get("probabilities") is not None:
                detail.at[i, f"_probs_{o.id}"] = json.dumps(meta["probabilities"])
            if meta.get("base_probabilities") is not None:
                detail.at[i, f"_probs_base_{o.id}"] = json.dumps(meta["base_probabilities"])
            if meta.get("raw_probabilities") is not None:
                detail.at[i, f"_probs_raw_{o.id}"] = json.dumps(meta["raw_probabilities"])
            if "coded_category" in meta:
                detail.at[i, f"_category_{o.id}"] = meta.get("coded_category")
            if meta.get("behavior_l1") is not None:
                detail.at[i, f"_behavior_l1_{o.id}"] = meta["behavior_l1"]
            if meta.get("behavior_applied") is not None:
                detail.at[i, f"_behavior_{o.id}"] = json.dumps(meta["behavior_applied"], ensure_ascii=False)
            # Czech language/discourse QC is a screening layer, never a
            # validity label. Apply it only to actual live open-ended text.
            if o.typ == "otevrena" and mode != "dry":
                try:
                    from npc_tools.npc_lint import zkontroluj
                    qc = zkontroluj(str(val or ""), kraj=str(panel.df.loc[src].get("kraj", "") or ""))
                    detail.at[i, f"_language_qc_score_{o.id}"] = int(qc.get("skore", 0) or 0)
                    detail.at[i, f"_language_qc_flags_{o.id}"] = " | ".join(
                        f"{x[0]}: {x[1]}" for x in qc.get("nalezy", []))
                except Exception as e:
                    detail.at[i, f"_language_qc_flags_{o.id}"] = f"QC_ERROR: {type(e).__name__}"
            odpovedi[i][o.id] = val

        completed.add(o.id)
        if progress_callback is not None:
            try: progress_callback({"phase":"question_complete","question_id":o.id,"question_index":qi,"question_total":len(otazky),"completed":len(completed),"run_dir":str(work_dir)})
            except Exception: pass
        if checkpoint:
            work_dir.mkdir(parents=True, exist_ok=True)
            detail.to_pickle(work_dir / "checkpoint.pkl")
            (work_dir / "progress.json").write_text(
                json.dumps({"completed": [x.id for x in otazky if x.id in completed],
                            "token_in": ti, "token_out": to,
                            "call_errors": call_errors,"provider_calls":provider_call_count,
                            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                           ensure_ascii=False, indent=2), encoding="utf-8")
        if mode != "dry" and 'journal_path' in locals() and journal_path.exists() and not budget_exhausted:
            journal_path.unlink(missing_ok=True)
            for canonical_block in work_dir.glob(f"raw_block_*__{o.id}.jsonl"):
                canonical_block.unlink(missing_ok=True)
        if budget_exhausted:
            log(f"[{o.id}] hard budget cap reached — run preserved as partial")
            break

    trvani = time.time() - t0
    if anchor_bank is not None:
        try:
            anchor_bank.close()
        except Exception:
            pass
    # Rebuild row-level error summary from persistent per-question columns so
    # resume does not erase failures recorded before the restart.
    error_cols = [f"_chyba_{o.id}" for o in otazky if f"_chyba_{o.id}" in detail.columns]
    def _row_errors(row):
        vals = [f"{c.removeprefix('_chyba_')}: {row[c]}" for c in error_cols
                if pd.notna(row[c]) and str(row[c]).strip()]
        return " | ".join(vals) if vals else None
    detail["_chyba"] = detail.apply(_row_errors, axis=1)
    call_errors = int(sum(detail[c].notna().sum() for c in error_cols))

    ci, co = provider_pricing(provider, model)
    panel_meta = resolve_panel_metadata(resolved_panel_path)
    vysledky = {
        "nazev": nazev, "n_dotazano": n,
        "n_chyb": int(detail["_chyba"].notna().sum()),
        "n_chyb_call": call_errors,
        "otazky": [{"id": o.id, "text": o.text, "typ": o.typ,
                    "volby": o.volby, "filtr": o.filtr} for o in otazky],
        "filtry": filtry or {}, "model": model, "provider": provider, "mode": mode, "seed": seed,
        "release": RELEASE, "run_id": run_id, "response_mode": response_mode,
        "panel_mode": str(panel_mode or "standard"), "ai_panel_profile_id": (ai_panel_profile or {}).get("profile_id", "") if str(panel_mode or "standard").lower()=="ai_panel" else "",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "panel_path": str(resolved_panel_path), "panel_sha256": sha256_file(resolved_panel_path),
        "panel_version": panel_meta.get("panel_version", ""),
        "target_hash": panel_meta.get("target_hash", ""),
        "panel_registry_managed": bool(panel_meta.get("registry_managed", False)),
        "parent_panel_version": panel_meta.get("parent_version", ""),
        "model_request_temperature": 0.0 if response_mode=="probability" else 1.0,
        "prompt_template_sha256": hashlib.sha256((SYSTEM_DOT+"\n---\n"+UZIV_DOT).encode("utf-8")).hexdigest(),
        "sample_id_sha256": sha256_json(vzorek["_zdroj_index"].astype(int).tolist()),
        "execution": ("grouped-multiquestion-v2" if provider=="claude_code_subscription" and mode!="dry" else "sequential-per-question"),
        "provider_calls": provider_call_count, "persona_mode": persona_mode,
        "provider_call_forecast": call_forecast,
        "persona_calibration": {**persona_calibration_run, "effective_by_question": {
            qid: resolve_calibrated_persona_mode(persona_mode, meta.get("topics") if isinstance(meta, dict) else [])[1]
            for qid, meta in temata_meta.items()
        }},
        "allow_own_estimates": bool(allow_own_estimates),
        "shuffle_persona": bool(shuffle_persona),
        "context_sha256": context_sha256 or "",
        "sampling": "representative_balanced_without_replacement" + ("_targeted" if selection_weights is not None else ""),
        "representativeness": sampling_audit,
        "segment": segment_meta or {},
        "temata_po_otazkach": temata_meta,
        "kontext_pouzity": kontext_meta,
        "anchors": anchor_meta,
        "dispersion_config": dispersion_cfg,
        "min_effective_n": float(min_effective_n),
        "provider_policy": str(provider_policy),
        "run_status": "PARTIAL_BUDGET_CAP" if budget_exhausted else ("INVALID_DRY_RUN" if mode=="dry" else "COMPLETE"),
        "factual_layer": fact_audit,
        "budget": (budget_guard.snapshot() if budget_guard is not None else {"max_usd": budget_max_usd, "spent_usd": 0.0 if mode=="dry" else None}),
        "trvani_s": round(trvani, 1),
        "naklady_usd": round(ti / 1e6 * ci + to / 1e6 * co, 4),
        "tokeny": {"in": ti, "out": to},
        "vysledky": {o.id: agreguj_otazku(detail, o, min_cell=int(min_effective_n)) for o in otazky},
        "detail": detail,
    }

    if ulozit:
        work_dir.mkdir(parents=True, exist_ok=True)
        detail.to_csv(work_dir / "detail_internal.csv", index=False)
        with open(work_dir / "souhrn.json", "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in vysledky.items() if k != "detail"},
                      f, ensure_ascii=False, indent=2, default=str)
        vysledky["run_dir"] = str(work_dir)
        log(f"[ulozeno] {work_dir}")
    return vysledky


# ---------------------------------------------------------------- agregace

def agreguj_otazku(detail: pd.DataFrame, o: Otazka, min_cell: int = 50) -> dict:
    """Weighted, interval-first aggregation with effective-n suppression.

    10.13 rule: a client-facing number is meaningful only together with its interval
    and evidence context. Segment cells below the Kish effective-n threshold are
    removed rather than greyed out.
    """
    from uncertainty import (
        clean_weights, kish_effective_n, bootstrap_weighted_distribution,
        bootstrap_weighted_mean, weighted_mean, weighted_distribution, weighted_quantile,
        weighted_variance, n_guard, donor_support, donor_ids, cluster_bootstrap_binary,
    )
    elig_col = f"_eligible_{o.id}"
    base = detail[detail[elig_col].fillna(False)] if elig_col in detail.columns else detail
    s = base[o.id]
    ok = base[s.notna()].copy()
    w = clean_weights(ok)
    from dispozice import odvod_temata
    topics = odvod_temata(getattr(o, "text", ""))
    support = donor_support(ok, topics) if len(ok) else donor_support(ok, topics)
    donor_col = support.get("donor_column", "core_donor_id")
    donors = donor_ids(ok, donor_col) if len(ok) else pd.Series(dtype=object)
    from fidelity import evidence_rating
    out: dict[str, Any] = {
        "typ": o.typ, "n_eligible": len(base),
        "n_filtered": int(len(detail) - len(base)),
        "n_platnych": len(ok), "n_chybi": int(s.isna().sum()),
        "effective_n": support.get("effective_n_combined", round(kish_effective_n(w), 1)),
        "effective_n_kish": support.get("effective_n_kish", round(kish_effective_n(w), 1)),
        "n_unique_core_donors": support.get("n_unique_core_donors", 0),
        "donor_layer": support.get("donor_layer", "core"),
        "n_unique_layer_donors": support.get("n_unique_layer_donors", 0),
        "max_donor_share": support.get("max_donor_share", 0.0),
        "support_status": support.get("support_status", "SUPPRESS"),
        "n_guard_threshold": 25.0,
        "indicative_threshold": 50.0,
        "uncertainty_note": (
            "95% interval = vážený bootstrap přes reálné donor clustery příslušné vrstvy. "
            "n_unique_layer_donors <25 se nereportuje; 25–49 je INDIKATIVNÍ. "
            "Interval není důkaz externí prediktivní validity."
        ),
        "evidence": evidence_rating(getattr(o, "text", ""), o.typ),
    }

    if o.typ == "vyber":
        ci = bootstrap_weighted_distribution(ok[o.id], o.volby, w, reps=400, seed=20260816, donors=donors) if len(ok) else {}
        out["celkem_pct"] = {k: float(v["estimate"]) for k, v in ci.items()}
        out["intervaly_95"] = {k: {"low": v["low"], "high": v["high"]} for k, v in ci.items()}
    elif o.typ == "multi":
        denom = float(w.sum()) if len(w) else 0.0
        pct, intervals = {}, {}
        lists = ok[o.id].tolist()
        for ii, choice in enumerate(o.volby):
            hit = np.array([choice in (lst or []) for lst in lists], dtype=float)
            point = 100.0 * float(np.dot(hit, w)) / denom if denom > 0 else 0.0
            pct[choice] = round(point, 1)
            bci = cluster_bootstrap_binary(hit, w, donors, reps=350, seed=20260816 + ii) if len(ok) else None
            intervals[choice] = {"low":round(100.0*float(bci["low"]),1),"high":round(100.0*float(bci["high"]),1)} if bci else {"low":0.0,"high":0.0}
        out["celkem_pct"] = pct; out["intervaly_95"] = intervals
        out["pozn"] = "více odpovědí, součet > 100 %"
    elif o.typ == "skala":
        v = pd.to_numeric(ok[o.id], errors="coerce").to_numpy(float)
        ci = bootstrap_weighted_mean(v, w, reps=400, seed=20260816, donors=donors) if len(v) else None
        var = weighted_variance(v, w)
        top_hit = (v >= o.skala[1] - 1).astype(float) if len(v) else np.array([])
        top_ci = bootstrap_weighted_mean(top_hit, w, reps=400, seed=20260818, donors=donors) if len(v) else None
        out.update({
            "prumer": round(float(ci["estimate"]), 2) if ci else None,
            "prumer_interval_95": {"low": round(float(ci["low"]),2), "high":round(float(ci["high"]),2)} if ci else None,
            "median": weighted_quantile(v, w, .5) if len(v) else None,
            "sd": round(float(var ** .5), 2) if var is not None else None,
            "rozlozeni": {str(k): int(x) for k, x in pd.Series(v).value_counts().sort_index().items()},
            "top2box_pct": round(100.0*float(top_ci["estimate"]),1) if top_ci else None,
            "top2box_interval_95": {"low":round(100.0*float(top_ci["low"]),1),"high":round(100.0*float(top_ci["high"]),1)} if top_ci else None,
        })
    else:
        out["verbatimy"] = ok[o.id].tolist()[:200]
        ccol=f"_category_{o.id}"
        if o.kodovaci_kategorie and ccol in ok.columns:
            ci=bootstrap_weighted_distribution(ok[ccol].dropna(),o.kodovaci_kategorie,clean_weights(ok[ok[ccol].notna()]),reps=300,seed=20260819)
            out["coded_pct"]={k:float(v["estimate"]) for k,v in ci.items()}
            out["coded_intervaly_95"]={k:{"low":v["low"],"high":v["high"]} for k,v in ci.items()}
            out["coding_note"]="Kategorie vznikla v témž structured outputu jako verbatim; bez druhého LLM průchodu."
        out["pozn"] = f"{len(ok)} syntetických ilustračních odpovědí"
        return out

    probs_col = f"_probs_{o.id}"
    if probs_col in base.columns and base[probs_col].notna().any():
        mats, mw = [], []
        for ix, raw in base[probs_col].dropna().items():
            try:
                arr = np.asarray(json.loads(raw), dtype=float)
                if np.isfinite(arr).all() and arr.sum() > 0:
                    mats.append(arr / arr.sum())
                    if "_analysis_weight" in base.columns:
                        mw.append(float(pd.to_numeric(base.loc[ix, "_analysis_weight"], errors="coerce") or 1.0))
                    else: mw.append(1.0)
            except Exception:
                pass
        if mats:
            M = np.vstack(mats); mw=np.asarray(mw,float); mw=np.where(np.isfinite(mw)&(mw>0),mw,1.0)
            meanp = np.average(M, axis=0, weights=mw)
            if o.typ == "vyber" and len(meanp) == len(o.volby):
                out["expected_pct"] = {k: round(float(100 * meanp[i]), 1) for i, k in enumerate(o.volby)}
                eci = {}
                for ii, k in enumerate(o.volby):
                    prob_idx = list(base[probs_col].dropna().index)[:len(M)]
                    prob_donors = donor_ids(base.loc[prob_idx], donor_col)
                    bci = bootstrap_weighted_mean(M[:, ii], mw, reps=300, seed=20260830 + ii, donors=prob_donors)
                    eci[k] = {"low": round(100*float(bci["low"]),1), "high": round(100*float(bci["high"]),1)}
                out["expected_intervaly_95"] = eci
            elif o.typ == "skala":
                nscale = o.skala[1] - o.skala[0] + 1
                if len(meanp) >= nscale:
                    mass = meanp[:nscale]
                    if mass.sum() > 0:
                        vals = np.arange(o.skala[0], o.skala[1] + 1, dtype=float)
                        out["expected_mean"] = round(float(np.dot(vals, mass) / mass.sum()), 3)
                        if o.povolit_nevim and len(meanp) > nscale:
                            out["expected_nevim_pct"] = round(float(100 * meanp[nscale]), 1)

    ep, mp = f"_entropy_{o.id}", f"_maxprob_{o.id}"
    if ep in base.columns and base[ep].notna().any():
        ev = pd.to_numeric(base[ep], errors="coerce").dropna()
        mv = pd.to_numeric(base[mp], errors="coerce").dropna()
        out["mean_response_entropy"] = round(float(ev.mean()), 3) if len(ev) else None
        out["mean_max_probability"] = round(float(mv.mean()), 3) if len(mv) else None

    vcol = f"_variant_{o.id}"
    if vcol in ok.columns and ok[vcol].notna().any():
        tab = {}
        for vid, grp in ok.groupby(vcol):
            guard=n_guard(grp,min_cell,topics)
            if not guard["allowed"]:
                gw=clean_weights(grp)
                rec={"n":len(grp),"suppressed":True,"reason":"méně než 25 unikátních donorů relevantní vrstvy","effective_n":guard["effective_n"],"n_unique_core_donors":guard["n_unique_core_donors"],"donor_layer":guard["donor_layer"],"n_unique_layer_donors":guard["n_unique_layer_donors"],"max_donor_share":guard["max_donor_share"],"support_status":guard["support_status"]}
                # Internal-only values preserve experiment diagnostics; client renderers must suppress them.
                if o.typ == "skala":
                    x=pd.to_numeric(grp[o.id],errors="coerce").to_numpy(float)
                    rec["_internal_mean"]=weighted_mean(x,gw)
                elif o.typ == "vyber":
                    rec["_internal_pct"]=weighted_distribution(grp[o.id],o.volby,gw)
                tab[str(vid)]=rec; continue
            gw=clean_weights(grp)
            if o.typ == "skala":
                x = pd.to_numeric(grp[o.id], errors="coerce").to_numpy(float)
                gdon=donor_ids(grp,guard["donor_column"]); gci=bootstrap_weighted_mean(x,gw,reps=250,seed=20260820,donors=gdon)
                tab[str(vid)]={"n":len(grp),"effective_n":guard["effective_n"],"n_unique_core_donors":guard["n_unique_core_donors"],"donor_layer":guard["donor_layer"],"n_unique_layer_donors":guard["n_unique_layer_donors"],"max_donor_share":guard["max_donor_share"],"support_status":guard["support_status"],"prumer":round(float(gci["estimate"]),2),"interval_95":{"low":round(float(gci["low"]),2),"high":round(float(gci["high"]),2)}}
            elif o.typ == "vyber":
                gdon=donor_ids(grp,guard["donor_column"]); gci=bootstrap_weighted_distribution(grp[o.id],o.volby,gw,reps=250,seed=20260821,donors=gdon)
                tab[str(vid)]={"n":len(grp),"effective_n":guard["effective_n"],"n_unique_core_donors":guard["n_unique_core_donors"],"donor_layer":guard["donor_layer"],"n_unique_layer_donors":guard["n_unique_layer_donors"],"max_donor_share":guard["max_donor_share"],"support_status":guard["support_status"],**{k:float(v["estimate"]) for k,v in gci.items()},"intervaly_95":{k:{"low":v["low"],"high":v["high"]} for k,v in gci.items()}}
        if tab: out["podle_varianty"] = tab

    for seg in SEGMENTY:
        if seg not in detail.columns:
            continue
        tab, male = {}, []
        for hod, grp in ok.groupby(seg):
            guard=n_guard(grp,min_cell,topics)
            if not guard["allowed"]:
                tab[str(hod)]={"n":len(grp),"suppressed":True,"reason":"méně než 25 unikátních donorů relevantní vrstvy","effective_n":guard["effective_n"],"n_unique_core_donors":guard["n_unique_core_donors"],"donor_layer":guard["donor_layer"],"n_unique_layer_donors":guard["n_unique_layer_donors"],"max_donor_share":guard["max_donor_share"],"support_status":guard["support_status"]}; male.append(str(hod)); continue
            gw=clean_weights(grp)
            if o.typ == "skala":
                x=pd.to_numeric(grp[o.id],errors="coerce").to_numpy(float); gdon=donor_ids(grp,guard["donor_column"]); gci=bootstrap_weighted_mean(x,gw,reps=220,seed=20260822,donors=gdon)
                tab[str(hod)]={"n":len(grp),"effective_n":guard["effective_n"],"n_unique_core_donors":guard["n_unique_core_donors"],"donor_layer":guard["donor_layer"],"n_unique_layer_donors":guard["n_unique_layer_donors"],"max_donor_share":guard["max_donor_share"],"support_status":guard["support_status"],"prumer":round(float(gci["estimate"]),2),"interval_95":{"low":round(float(gci["low"]),2),"high":round(float(gci["high"]),2)}}
            elif o.typ == "multi":
                denom=float(gw.sum()); vals={}; ints={}; gdon=donor_ids(grp,guard["donor_column"])
                for ii, choice in enumerate(o.volby):
                    hit=np.array([choice in (lst or []) for lst in grp[o.id]],float); vals[choice]=round(100*float(np.dot(hit,gw))/denom,1) if denom else 0.0
                    bci=cluster_bootstrap_binary(hit,gw,gdon,reps=220,seed=20260824+ii)
                    ints[choice]={"low":round(100*float(bci["low"]),1),"high":round(100*float(bci["high"]),1)} if bci else {"low":0.0,"high":0.0}
                tab[str(hod)]={"n":len(grp),"effective_n":guard["effective_n"],"n_unique_core_donors":guard["n_unique_core_donors"],"donor_layer":guard["donor_layer"],"n_unique_layer_donors":guard["n_unique_layer_donors"],"max_donor_share":guard["max_donor_share"],"support_status":guard["support_status"],**vals,"intervaly_95":ints}
            else:
                gdon=donor_ids(grp,guard["donor_column"]); gci=bootstrap_weighted_distribution(grp[o.id],o.volby,gw,reps=220,seed=20260823,donors=gdon)
                tab[str(hod)]={"n":len(grp),"effective_n":guard["effective_n"],"n_unique_core_donors":guard["n_unique_core_donors"],"donor_layer":guard["donor_layer"],"n_unique_layer_donors":guard["n_unique_layer_donors"],"max_donor_share":guard["max_donor_share"],"support_status":guard["support_status"],**{k:float(v["estimate"]) for k,v in gci.items()},"intervaly_95":{k:{"low":v["low"],"high":v["high"]} for k,v in gci.items()}}
        out[f"podle_{seg}"] = tab
        if male: out.setdefault("varovani", []).append(f"{seg}: buňky pod effective n<{min_cell} jsou skryté: {', '.join(male)}")
    return out


def tabulka_dotaznik(v: dict) -> str:
    r = [f"=== {v['nazev']} ===",
         f"n={v['n_dotazano']}  chyb={v['n_chyb']}  {v['trvani_s']} s  "
         f"${v['naklady_usd']}  ({v['model']}, {v['mode']})", ""]
    for o in v["otazky"]:
        a = v["vysledky"][o["id"]]
        r.append(f"[{o['id']}] {o['text']}   (n={a['n_platnych']})")
        if a["typ"] == "skala":
            r.append(f"    průměr {a['prumer']}  medián {a['median']}  "
                     f"top-2-box {a['top2box_pct']} %")
        elif a["typ"] == "otevrena":
            for x in a["verbatimy"][:5]:
                r.append(f"    · {x}")
        else:
            for k, p in sorted(a["celkem_pct"].items(), key=lambda x: -x[1]):
                r.append(f"    {p:5.1f} %  {k}")
        for w in a.get("varovani", []):
            r.append(f"    ! {w}")
        r.append("")
    return "\n".join(r)
