"""Run one integrated mixed research project through one respondent sample.

Ordinary questions and all object batteries are compiled into one sequential survey,
so every answer in the downloadable dataset belongs to the same synthetic respondent.
Each object battery can then be analysed separately from that shared respondent dataset.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import numpy as np
import pandas as pd

from research_project import compile_project
from study_contract import StudySpec
from study_validation import validate_study_dataset
from sociomap import fit_segments, profile_segments, relation_map_from_battery, export_relational_html, export_relational_png, relational_nearest_pairs
from study_export import export_xlsx, export_documentation
from core_joint import joint_output_gate


def _encode_categories(s: pd.Series) -> tuple[pd.Series, dict[int, str]]:
    vals = sorted(s.dropna().astype(str).unique().tolist())
    mp = {v: i + 1 for i, v in enumerate(vals)}
    return s.map(lambda x: mp.get(str(x)) if pd.notna(x) else np.nan), {i: v for v, i in mp.items()}


def _battery_dataset(detail: pd.DataFrame, battery: dict[str, Any]) -> tuple[pd.DataFrame, list[dict[str, str]], StudySpec]:
    sec = battery["section"]
    spec = StudySpec(**battery["spec"])
    out = pd.DataFrame(index=detail.index)
    out["respondent_id"] = np.arange(1, len(detail) + 1)
    w = pd.to_numeric(detail.get("_analysis_weight", pd.Series(1.0, index=detail.index)), errors="coerce").fillna(1.0)
    out["vaha"] = w * (len(out) / float(w.sum() or 1.0))
    labels = [
        {"var": "respondent_id", "lab": "Identifikátor syntetického respondenta", "values": ""},
        {"var": "vaha", "lab": "Analytická váha; součet = N", "values": ""},
    ]
    for src, dst in {"pohlavi":"dem_pohlavi","vek":"dem_vek","vzdelani":"dem_vzdelani","kraj":"dem_kraj","trida_spolecenska":"dem_trida"}.items():
        if src not in detail:
            continue
        if src == "vek":
            out[dst] = pd.to_numeric(detail[src], errors="coerce")
            labels.append({"var":dst,"lab":"Věk","values":"raw"})
        else:
            enc, inv = _encode_categories(detail[src])
            out[dst] = enc
            labels.append({"var":dst,"lab":src.replace("_"," ").capitalize(),"values":"; ".join(f"{k} = {v}" for k,v in inv.items())})
    mapping = battery["mapping"]
    for obj in spec.objects:
        slug = obj.slug
        source_obj = mapping["obj"].get(slug)
        source_fam = mapping["fam"].get(slug)
        target_obj = f"obj_{slug}"
        if source_obj in detail:
            out[target_obj] = pd.to_numeric(detail[source_obj], errors="coerce")
        else:
            out[target_obj] = np.nan
        if spec.familiarity_required:
            target_fam = f"fam_{slug}"
            if source_fam in detail:
                raw = detail[source_fam]
                out[target_fam] = raw.map({"Neznám":0,"Znám":1}).astype("Int64")
            else:
                out[target_fam] = pd.Series([pd.NA]*len(detail), dtype="Int64")
            out.loc[out[target_fam].fillna(0).astype(int)==0, target_obj] = np.nan
            labels.append({"var":target_fam,"lab":spec.familiarity_question.format(object=obj.label),"values":"0 = neznám; 1 = znám"})
        labels.append({"var":target_obj,"lab":spec.object_question.format(object=obj.label),"values":f"1 = {spec.object_scale_labels[0]} … 10 = {spec.object_scale_labels[1]}"})
    return out.reset_index(drop=True), labels, spec


def _object_ranking(data: pd.DataFrame, spec: StudySpec) -> list[dict[str, Any]]:
    w=pd.to_numeric(data.get("vaha",pd.Series(1.0,index=data.index)),errors="coerce").fillna(1.0).to_numpy(float)
    out=[]
    for obj in spec.objects:
        col=f"obj_{obj.slug}"
        if col not in data: continue
        x=pd.to_numeric(data[col],errors="coerce").to_numpy(float); ok=np.isfinite(x)&np.isfinite(w)&(w>0)
        if not ok.any(): continue
        mean=float(np.average(x[ok],weights=w[ok])); n=int(ok.sum())
        out.append({"object":obj.label,"mean":round(mean,3),"n":n})
    return sorted(out,key=lambda z:z["mean"],reverse=True)


def _mark_internal_map(path: Path, reason: str) -> Path:
    txt=path.read_text(encoding="utf-8")
    banner=("<div style=\"position:sticky;top:0;z-index:9999;background:#8b0000;color:#fff;"
            "padding:10px 14px;font:700 13px Arial,sans-serif;letter-spacing:.04em\">"
            "INTERNAL EXPERIMENTAL MAP · NOT CLIENT-VALIDATED · "+str(reason)+"</div>")
    txt=txt.replace("<body>","<body>"+banner,1)
    path.write_text(txt,encoding="utf-8"); return path


def analyse_battery(detail: pd.DataFrame, battery: dict[str, Any], output_dir: str | Path, *, map_method: str = "auto") -> dict[str, Any]:
    outdir = Path(output_dir); outdir.mkdir(parents=True, exist_ok=True)
    data, labels, spec = _battery_dataset(detail, battery)
    seg = None; profiles = None
    try:
        seg = fit_segments(data, seed=spec.seed)
        profiles = profile_segments(data, seg["labels"])
    except Exception as exc:
        seg = {"error": str(exc), "bootstrap_ari": None, "entropy": None}
    pre = validate_study_dataset(data, segment_metrics=seg if isinstance(seg,dict) and "error" not in seg else None, scale_domains=spec.scale_domains())
    relmap=None
    if pre["status"] == "PASS" and len(spec.objects) >= 3:
        try:
            explicit=(battery.get('section') or {}).get('relation_matrix')
            relmap=relation_map_from_battery(data,spec,explicit_matrix=explicit)
            validation=validate_study_dataset(data,segment_metrics=seg if isinstance(seg,dict) and "error" not in seg else None,stress_1=relmap.stress_1,scale_domains=spec.scale_domains())
        except Exception as exc:
            validation={**pre,'map_warning':str(exc)}
    else:
        validation=pre
    validation["client_output_status"] = "ALLOWED_MODEL_DERIVED_RELATIONAL_MAP" if validation.get('status')=='PASS' else "DATA_VALIDATION_WARNING"
    validation["map_contract"]={"matrix":"all_included_objects_x_all_included_objects","relation_scale":"1-10","diagonal":0,"asymmetry":"allowed for explicitly measured directional matrices; correlation-derived matrices are symmetric","higher_relation":"closer","visual_score":"primary bubble size + color","secondary":"same position/matrix; no score bubble",
                                 "note":"Bahbouh-inspired relational map semantics; not claimed as proprietary QED implementation."}
    stem = spec.name.lower().replace(" ","_")[:50]
    csvp = outdir / f"{stem}_data.csv"; data.to_csv(csvp,index=False,encoding="utf-8-sig")
    xlsx = export_xlsx(outdir / f"{stem}_data.xlsx", data, labels, {
        "nazev_studie":spec.name,"vyzkumna_otazka":spec.research_question,"typ_vystupu":spec.output_type,
        "N":len(data),"objekty_pocet":len(spec.objects),"object_family":spec.object_family,
        "validation_status":validation["status"],"stress_1":relmap.stress_1 if relmap else None,
        "map_method":"relational_all_pairs_stress" if relmap else None,
    })
    html = None; png=None; map_reason=""
    ranking=_object_ranking(data,spec)
    if not battery["section"].get("visualize",True):
        map_reason="Relační vizualizace je pro tuto sledovanou sadu vypnutá."
    elif relmap is None:
        map_reason="Relační mapa nevznikla, protože dataset neprošel předběžným datovým gate nebo sada nemá alespoň 3 objekty."
    else:
        html=export_relational_html(outdir/f"{stem}_relacni_mapa.html",relmap)
        png=export_relational_png(outdir/f"{stem}_relacni_mapa.png",relmap)
        if relmap.relation_source=='DERIVED_FROM_COMMON_RESPONDENT_RATINGS':
            map_reason="Matice vztahů je odvozena ze společných respondentních hodnocení; nejde o přímo měřenou pairwise relační otázku."
    docx = export_documentation(outdir / f"{stem}_dokumentace.docx", spec=spec, data=data, labels=labels, validation=validation,
                                map_result=None,segment_result=seg if isinstance(seg,dict) and 'error' not in seg else None,run_result={})
    valp = outdir / f"{stem}_validation.json"; valp.write_text(json.dumps(validation,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    reljson=None
    if relmap is not None:
        reljson=outdir/f"{stem}_relation_matrix.json";reljson.write_text(json.dumps(relmap.serializable(),ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    return {"id":battery["section"]["id"],"title":battery["section"]["title"],"object_family":spec.object_family,
            "validation":validation,"map_reason":map_reason,"object_ranking":ranking,
            "nearest_pairs":relational_nearest_pairs(relmap,10) if relmap else [],
            "map_metrics":({"stress_1":relmap.stress_1,"method":"relational_all_pairs_stress","relation_source":relmap.relation_source} if relmap is not None else None),
            "files":{"csv":str(csvp),"xlsx":str(xlsx),"docx":str(docx),"html":str(html) if html else None,
                     "map_html":str(html) if html else None,"map_png":str(png) if png else None,
                     "relation_matrix":str(reljson) if reljson else None,"validation":str(valp)}}


def run_project(project: dict[str, Any], *, mode: str = "dry", confirm_live: bool = False,
                map_method: str = "auto", run_dir: str | Path | None = None,
                resume_dir: str | Path | None = None, progress_callback=None, cancel_check=None,
                workflow_id: str | None = None, job_id: str | None = None, precomputed_research: dict[str,Any] | None = None) -> dict[str, Any]:
    import prototype_server as core
    from factual_layer import harmonize_project_fact_choices
    project,_fact_harmonization=harmonize_project_fact_choices(project,core.load_panel_cached())
    compiled = compile_project(project)
    brief = compiled["brief"]
    brief["mode"] = mode
    code, main = core.execute_run({"brief":brief,"project":compiled["project"],"confirm_live":bool(confirm_live),
                                  "precomputed_research":precomputed_research,
                                  "run_dir":str(run_dir) if run_dir else None,
                                  "resume_dir":str(resume_dir) if resume_dir else None,
                                  "progress_callback":progress_callback,"cancel_check":cancel_check,
                                  "workflow_id":workflow_id,"job_id":job_id})
    if code != 200:
        exc = ValueError(main.get("error") or f"Survey run failed ({code}).")
        # Carry the already-classified provider failure so the UI does not
        # re-diagnose a diagnosis and lose the actual cause.
        if main.get("provider_error"):
            setattr(exc, "provider_error", main["provider_error"])
        raise exc
    run_id = (main.get("summary") or {}).get("run_id")
    battery_results = []
    if run_id and compiled["batteries"]:
        detail_path = Path(core.ROOT) / "runs" / str(run_id) / "detail_internal.csv"
        if detail_path.is_file():
            detail = pd.read_csv(detail_path, low_memory=False)
            root = Path(core.OUT) / "project_batteries" / str(run_id)
            for b in compiled["batteries"]:
                try:
                    battery_results.append(analyse_battery(detail,b,root/b["section"]["id"],map_method=map_method))
                except Exception as exc:
                    battery_results.append({"id":b["section"]["id"],"title":b["section"]["title"],"error":str(exc),"files":{}})
    return {"project":compiled["project"],"main":main,"batteries":battery_results,"compiled_question_count":len(brief["otazky"])}
