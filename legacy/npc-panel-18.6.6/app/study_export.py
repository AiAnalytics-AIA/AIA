"""Standardní tří-souborový export studie: XLSX + DOCX + HTML mapa."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import pandas as pd


def export_xlsx(path: str | Path, data: pd.DataFrame, labels: list[dict[str,str]], meta: dict[str,Any]) -> Path:
    # Runtime dependency already exists in project. This function deliberately
    # writes exactly the contract from the supplied template: data/labels/meta.
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    wb=Workbook(); ws=wb.active; ws.title="data"
    def excel_value(v):
        if v is None: return None
        try:
            if pd.isna(v): return None
        except Exception:
            pass
        if isinstance(v,(dict,list,tuple,set)): return json.dumps(v,ensure_ascii=False,default=str)
        if hasattr(v,"item"):
            try: return v.item()
            except Exception: pass
        return v
    ws.append(list(data.columns))
    for row in data.itertuples(index=False, name=None): ws.append([excel_value(v) for v in row])
    ls=wb.create_sheet("labels"); ls.append(["var","lab","values"])
    for r in labels: ls.append([r.get("var",""),r.get("lab",""),r.get("values","")])
    ms=wb.create_sheet("meta"); ms.append(["klíč","hodnota"])
    for k,v in meta.items():
        if isinstance(v,(dict,list)): v=json.dumps(v,ensure_ascii=False)
        ms.append([excel_value(k),excel_value(v)])
    for sh in (ws,ls,ms):
        for cell in sh[1]:
            cell.font=Font(bold=True,color="FFFFFF"); cell.fill=PatternFill("solid",fgColor="243447")
        sh.freeze_panes="A2"
        for col in range(1, sh.max_column+1):
            width=min(42,max(10,max(len(str(sh.cell(r,col).value or "")) for r in range(1,min(sh.max_row,80)+1))+2))
            sh.column_dimensions[get_column_letter(col)].width=width
    wb.save(path); return path


# ---------------------------------------------------------------- 17.1.1 report

def _w(series: pd.Series, weights: pd.Series) -> float | None:
    """Vazeny prumer pres neprazdne hodnoty."""
    m = series.notna()
    if not m.any():
        return None
    w = weights[m].astype(float)
    if float(w.sum()) <= 0:
        return None
    return float((series[m].astype(float) * w).sum() / w.sum())


def _object_findings(spec, data: pd.DataFrame, run_detail: pd.DataFrame | None = None) -> list[dict[str, Any]]:
    """Vazena znamost a hodnoceni pro kazdy objekt baterie."""
    w = data["vaha"].astype(float) if "vaha" in data.columns else pd.Series(1.0, index=data.index)
    out = []
    for obj in spec.objects:
        label = getattr(obj, "label", str(obj))
        key = None
        for c in data.columns:
            if c.startswith("obj_") and c[4:] in str(getattr(obj, "column", "") or "") :
                key = c
        if key is None:
            cand = [c for c in data.columns if c.startswith("obj_")]
            idx = list(spec.objects).index(obj)
            key = cand[idx] if idx < len(cand) else None
        if key is None:
            continue
        fam = "fam_" + key[4:]
        rating = pd.to_numeric(data[key], errors="coerce")
        known = pd.to_numeric(data[fam], errors="coerce") if fam in data.columns else rating.notna().astype(float)
        support = None
        if run_detail is not None and len(run_detail) == len(data):
            try:
                from uncertainty import donor_support
                support = donor_support(run_detail.loc[rating.notna().to_numpy()])
            except Exception:
                support = None
        out.append({
            "objekt": label,
            "znamost_pct": (_w(known, w) or 0.0) * 100,
            "prumer": _w(rating, w),
            "n_hodnotilo": int(rating.notna().sum()),
            "effective_n": None if not support else support.get("effective_n_combined"),
            "n_unique_core_donors": None if not support else support.get("n_unique_core_donors"),
            "support_status": None if not support else support.get("support_status"),
            "top3box_pct": (_w((rating >= 8).where(rating.notna()), w) or 0.0) * 100,
            "bot3box_pct": (_w((rating <= 3).where(rating.notna()), w) or 0.0) * 100,
        })
    return out


def _add_table(d, header: list[str], rows: list[list[str]]) -> None:
    t = d.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)


def _gate_rows(validation: dict[str, Any]) -> list[list[str]]:
    """Brany jako ctena tabulka misto vypisu Python dictu."""
    rows = []
    for k, v in (validation.get("gates") or {}).items():
        if not isinstance(v, dict):
            rows.append([k, "—", str(v)[:90], "ne"]); continue
        p = v.get("pass")
        stav = "PASS" if p is True else "FAIL" if p is False else (v.get("status") or "NEBĚŽELO")
        detail = []
        for kk, vv in v.items():
            if kk in {"pass", "blocking", "status"}:
                continue
            if isinstance(vv, float):
                detail.append(f"{kk}={vv:.3f}")
            elif isinstance(vv, (int, str)):
                detail.append(f"{kk}={vv}")
            elif isinstance(vv, (list, dict)) and not vv:
                detail.append(f"{kk}=—")
            elif isinstance(vv, list):
                detail.append(f"{kk}: {len(vv)} položek")
            elif isinstance(vv, dict):
                detail.append(f"{kk}: {len(vv)} položek")
        rows.append([k, stav, "; ".join(detail)[:110], "ano" if v.get("blocking") else "ne"])
    return rows


def export_documentation(path: str | Path, *, spec: Any, data: pd.DataFrame,
                         labels: list[dict[str,str]], validation: dict[str,Any],
                         map_result: Any | None = None, segment_result: dict[str,Any] | None = None,
                         run_result: dict[str,Any] | None = None, support_summary: dict[str,Any] | None = None,
                         verification: dict[str,Any] | None = None) -> Path:
    from docx import Document
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    d=Document(); d.add_heading(f"NPC Panel — {spec.name}",0)
    findings=_object_findings(spec, data, (run_result or {}).get("detail") if isinstance(run_result,dict) else None)
    blocking=validation.get("blocking_failures") or []

    # 17.1.1: shrnutí napřed. Klientský dokument musí začínat zjištěním,
    # ne specifikací; QC patří dozadu a do tabulky, ne jako výpis dictů.
    d.add_heading("Shrnutí", 1)
    d.add_paragraph(f"Výzkumná otázka: {spec.research_question}")
    if findings:
        ranked=[f for f in findings if f["prumer"] is not None]
        ranked.sort(key=lambda x: -x["prumer"])
        if ranked:
            best, worst = ranked[0], ranked[-1]
            d.add_paragraph(
                f"Nejlépe hodnocený objekt: {best['objekt']} "
                f"(průměr {best['prumer']:.2f}/10, znalost {best['znamost_pct']:.0f} %). "
                f"Nejhůře: {worst['objekt']} "
                f"(průměr {worst['prumer']:.2f}/10, znalost {worst['znamost_pct']:.0f} %)."
            )
        top_known=max(findings, key=lambda x: x["znamost_pct"])
        low_known=min(findings, key=lambda x: x["znamost_pct"])
        d.add_paragraph(
            f"Rozpětí znalosti: {low_known['objekt']} {low_known['znamost_pct']:.0f} % "
            f"až {top_known['objekt']} {top_known['znamost_pct']:.0f} %."
        )
    if segment_result:
        d.add_paragraph(
            f"Segmentace: {segment_result.get('k')} segmentů; stabilita (bootstrap ARI) "
            f"{segment_result.get('bootstrap_ari')}, entropie {segment_result.get('entropy')}."
        )
    if blocking:
        d.add_paragraph(
            "UPOZORNĚNÍ: studie neprošla blokujícími branami (" + ", ".join(map(str, blocking)) +
            "). Čísla níže jsou orientační a nesmí být použita jako klientský závěr."
        )
    d.add_paragraph(
        "Zdroj dat: syntetický respondentní panel, nikoli lidský terénní sběr."
    )

    d.add_heading("Hlavní zjištění", 1)
    if findings:
        _add_table(
            d,
            ["Objekt", "Znalost %", "Průměr 1–10", "Top-3-box %", "Bottom-3-box %", "raw n", "effective n", "core donoři", "support"],
            [[f["objekt"], f"{f['znamost_pct']:.0f}",
              "—" if f["prumer"] is None else f"{f['prumer']:.2f}",
              f"{f['top3box_pct']:.0f}", f"{f['bot3box_pct']:.0f}", f["n_hodnotilo"],
              "—" if f.get("effective_n") is None else f"{float(f['effective_n']):.1f}",
              "—" if f.get("n_unique_core_donors") is None else str(f["n_unique_core_donors"]),
              f.get("support_status") or "—"] for f in findings],
        )
        d.add_paragraph(
            "Průměry a podíly jsou vážené analytickou vahou a počítané pouze mezi "
            "respondenty, kteří objekt znají. Neznalost není hodnocena jako neutrální."
        )
    else:
        d.add_paragraph("Studie neobsahuje objektovou baterii; viz datový soubor.")


    if support_summary:
        d.add_heading("Podpora vzorku a efektivní N", 1)
        _add_table(d,["raw n","Kish n","unikátní core donoři","vrstva","unikátní layer donoři","effective n","max donor share","status"],[[
            str(support_summary.get("n","—")), str(support_summary.get("effective_n_kish","—")),
            str(support_summary.get("n_unique_core_donors","—")), str(support_summary.get("donor_layer","—")),
            str(support_summary.get("n_unique_layer_donors","—")), str(support_summary.get("effective_n_combined","—")),
            str(support_summary.get("max_donor_share","—")), str(support_summary.get("support_status","—"))]])
        d.add_paragraph("Intervaly a support se interpretují přes reálné donor clustery; raw počet syntetických řádků není počet nezávislých lidí.")

    if verification:
        d.add_heading("Externí kontext / triangulace", 1)
        d.add_paragraph(str(verification.get("note") or "Externí srovnání je triangulace, nikoli důkaz prediktivní validity."))
        rows=[]
        for tid,v in (verification.get("by_target") or {}).items():
            t=v.get("target") or {}; best=v.get("best_direct") or {};
            rows.append([str(t.get("question_text") or tid),str(t.get("npc_value","—")),str(v.get("status","—")),str(best.get("benchmark_value","—")),str(best.get("source_title","—"))])
        if rows:_add_table(d,["Výsledek","NPC","Externí stav","Benchmark","Zdroj"],rows[:30])

    sections=[
        ("1. Identifikace studie", [f"Výzkumná otázka: {spec.research_question}", f"Typ výstupu: {spec.output_type}", f"Objektová rodina: {spec.object_family}"]),
        ("2. Metodologie", ["Syntetický respondentní panel; sekvenční otázky; objektové baterie jsou oddělené od profilovacích charakteristik.", f"Všech {len(spec.objects)} objektů patří do jedné srovnávací rodiny: {spec.object_family}.", "Objekty byly hodnoceny na jednotné škále 1–10; neznámé objekty zůstávají missing."]),
        ("3. Vzorek a vážení", [f"N = {len(data)}", f"Součet analytických vah = {float(data['vaha'].sum()):.3f}"]),
        ("4. Znění dotazníku", [q["text"] for q in spec.questionnaire()]),
        ("5. Datový slovník", [f"{r['var']}: {r['lab']} [{r['values']}]" for r in labels]),
        ("6. Kontrola kvality", [f"Celkový stav: {validation['status']}"] + (["Blokující selhání: " + ", ".join(map(str, blocking))] if blocking else ["Blokující selhání: žádné"])),
        ("7. Struktura souboru", ["XLSX obsahuje listy data, labels a meta. Jedna proměnná = jeden sloupec; jeden respondent = jeden řádek."]),
        ("8. Co chybí / omezení", ["Jde o syntetickou simulaci, ne lidský terén.", "V7 vyžaduje externí reálný seed stejné kategorie; pokud nebyl dodán, je explicitně NOT_RUN."]),
        ("9. Podmínky použití", ["Objektová mapa je povolena pouze při průchodu blokujícími branami V3–V5.", "Charakteristiky nevstupují do vzdálenostní matice."]),
        ("10. Kontrolní seznam", ["Výzkumná otázka vyplněna", f"Počet objektů: {len(spec.objects)} (4–15 doporučeno, technická policy ověřena)", f"Jedna objektová rodina: {spec.object_family}", "Labels přítomny", "V1–V8 zapsány", "Metoda mapy a stress zapsány"]),
    ]
    for title, lines in sections:
        d.add_heading(title,1)
        for line in lines: d.add_paragraph(str(line))
        if title.startswith("6."):
            _add_table(d, ["Brána", "Stav", "Naměřeno", "Blokující"], _gate_rows(validation))
    if map_result is not None:
        d.add_paragraph(f"Mapa: {map_result.method}; stress-1={map_result.stress_1:.4f}")
    if segment_result:
        d.add_paragraph(f"Segmentace: K={segment_result.get('k')}; bootstrap ARI={segment_result.get('bootstrap_ari')}; entropy={segment_result.get('entropy')}")
    d.save(path); return path
