"""End-to-end modul VÝZKUM."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
from study_contract import StudySpec
from study_dataset import build_study_dataset
from study_validation import validate_study_dataset
from sociomap import fit_unfolding, fit_segments, profile_segments, export_map_html
from study_export import export_xlsx, export_documentation
from core_joint import joint_output_gate
from runtime_config import RUN_DEFAULTS
from uncertainty import donor_support


def run_study(spec: StudySpec | dict[str,Any], *, panel_path=None, model=None, mode=RUN_DEFAULTS["mode"],
              output_dir="study_outputs", map_method="auto", real_seed=None,
              allow_own_estimates=False, anchors: dict[str,Any] | None=None,
              provider_policy: str | None=None, tichy=False) -> dict[str,Any]:
    from dotaznik import run_dotaznik
    from runtime_config import DEFAULT_MODEL
    if not isinstance(spec, StudySpec): spec=StudySpec(**spec)
    if provider_policy is None:
        if mode == "dry":
            provider_policy = "fallback"
        else:
            from provider_auth import get_ai_provider, normalize_ai_provider
            provider_policy = "strict_" + normalize_ai_provider(get_ai_provider())
    out=Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    run=run_dotaznik(spec.questionnaire(), n=spec.n, nazev=spec.name, panel_path=panel_path,
                     model=model or DEFAULT_MODEL, mode=mode, seed=spec.seed, tichy=tichy,
                     allow_own_estimates=allow_own_estimates,
                     anchor_config=anchors, provider_policy=provider_policy)
    data, labels, meta = build_study_dataset(run, spec)
    allow_experimental_map=bool((spec.metadata or {}).get("allow_experimental_map", False))
    joint_gate=joint_output_gate(output="sociomap", allow_experimental=allow_experimental_map)
    # Segment first only as an INTERNAL V8 diagnostic. Under JOINT_UNVALIDATED it must not
    # leak into client-facing DOCX/API unless the owner explicitly enabled EXPERIMENTAL mode.
    seg=None; profiles=None
    try:
        seg=fit_segments(data, seed=spec.seed)
        profiles=profile_segments(data, seg["labels"])
    except Exception as e:
        seg={"error":str(e),"bootstrap_ari":None,"entropy":None}
    pre=validate_study_dataset(data, real_seed=real_seed, segment_metrics=seg if "error" not in seg else None,
                               scale_domains=spec.scale_domains())
    mapres=None
    if pre["status"] == "PASS":
        mapres=fit_unfolding(data, method=map_method, seed=spec.seed)
        validation=validate_study_dataset(data, real_seed=real_seed,
                                          segment_metrics=seg if "error" not in seg else None,
                                          stress_1=mapres.stress_1, scale_domains=spec.scale_domains())
    else:
        validation=pre
    validation["joint_core_gate"] = joint_gate
    validation["client_output_status"] = ("EXPERIMENTAL" if joint_gate.get("experimental") else
                                           "ALLOWED" if joint_gate.get("allowed") else "BLOCKED_CORE_JOINT")
    meta.update({
        "validation_status": validation["status"],
        "V3_PC1_podil": validation["gates"]["V3"].get("pc1_share"),
        "V4_min_korelace": validation["gates"]["V4"].get("min_object_correlation"),
        "V5_max_r_demo_objekt": validation["gates"]["V5"].get("max_abs_r"),
        "V7_pomer_variance": validation["gates"]["V7"].get("variance_ratios"),
        "V8_bootstrap_ARI": validation["gates"]["V8"].get("bootstrap_ari"),
        "stress_1": mapres.stress_1 if mapres else None,
        "map_method": mapres.method if mapres else None,
        "joint_core_status": joint_gate.get("status"),
        "joint_core_client_output_allowed": joint_gate.get("allowed"),
        "joint_core_experimental": joint_gate.get("experimental"),
    })
    stem=spec.name.lower().replace(" ","_")
    xlsx=export_xlsx(out/f"{stem}_data.xlsx",data,labels,meta)
    csv=out/f"{stem}_data.csv"
    data.to_csv(csv,index=False,encoding="utf-8-sig")
    html=None
    if mapres is not None and validation["status"]=="PASS" and joint_gate.get("allowed"):
        suffix="_EXPERIMENTAL_mapa.html" if joint_gate.get("experimental") else "_mapa.html"
        html=export_map_html(out/f"{stem}{suffix}",mapres,data,seg,profiles or {})
    public_segments = seg if joint_gate.get("allowed") else None
    public_profiles = profiles if joint_gate.get("allowed") else None
    docx=export_documentation(out/f"{stem}_dokumentace.docx",spec=spec,data=data,labels=labels,
                              validation=validation,map_result=mapres if joint_gate.get("allowed") else None,
                              segment_result=public_segments,run_result=run,
                              support_summary=donor_support(run["detail"]))
    (out/f"{stem}_validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    return {"spec":spec.to_dict(),"run":run,"data":data,"labels":labels,"meta":meta,
            "validation":validation,
            "map":mapres if joint_gate.get("allowed") else None,
            "segments":public_segments,"profiles":public_profiles,
            "internal_segment_validation": {
                "bootstrap_ari": seg.get("bootstrap_ari") if isinstance(seg,dict) else None,
                "entropy": seg.get("entropy") if isinstance(seg,dict) else None,
                "withheld_from_client": not bool(joint_gate.get("allowed")),
            },
            "files":{"xlsx":str(xlsx),"csv":str(csv),"docx":str(docx),"html":str(html) if html else None}}
