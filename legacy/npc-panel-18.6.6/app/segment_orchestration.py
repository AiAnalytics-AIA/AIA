"""High-level segment preparation shared by CLI and local UI."""
from __future__ import annotations
from runtime_config import RUN_DEFAULTS

import json
from pathlib import Path
from typing import Any
import pandas as pd

from pipeline import Panel
from segment import (SegmentSpec, fit_propensity_segment, profile_segment,
                     screener_labels, save_segment_artifacts)


def prepare_segment(panel: Panel, config: dict[str, Any] | None, *,
                    model: str, mode: str, seed: int | None,
                    context_events=None, context_sha256: str | None = None,
                    workers: int = 8) -> tuple[pd.Series | None, dict[str, Any]]:
    cfg = config or {}
    smode = str(cfg.get("mode", "none")).lower()
    if smode in {"", "none", "off"}:
        return None, {"mode": "none"}
    if smode == "propensity_file":
        path = Path(str(cfg.get("propensity_file", "")))
        if not path.exists():
            raise FileNotFoundError("propensity_file segment potrebuje existujici CSV")
        d = pd.read_csv(path)
        if "propensity" not in d.columns:
            raise KeyError("propensity_file potrebuje sloupec propensity")
        if "panel_row_id" in d.columns and "panel_row_id" in panel.df.columns:
            mapper = pd.Series(d["propensity"].to_numpy(), index=d["panel_row_id"].astype(str))
            prop = panel.df["panel_row_id"].astype(str).map(mapper)
        elif "panel_index" in d.columns:
            mapper = pd.Series(d["propensity"].to_numpy(), index=pd.to_numeric(d["panel_index"], errors="coerce"))
            prop = pd.Series(panel.df.index, index=panel.df.index).map(mapper)
        else:
            if len(d) != len(panel.df):
                raise ValueError("propensity_file bez panel id musi mit presne delku panelu")
            prop = pd.Series(d["propensity"].to_numpy(), index=panel.df.index)
        prop = pd.to_numeric(prop, errors="coerce").fillna(0).clip(0,1)
        meta_path = Path(str(cfg.get("metadata_file", path.with_name("segment_model.json"))))
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        meta.update({"mode":"propensity_file", "name": cfg.get("name") or meta.get("name") or path.stem,
                     "propensity_source": str(path)})
        return prop, meta
    if smode != "learned":
        raise ValueError("segment.mode podporuje none | learned | propensity_file; prime filtry patri do filtry")

    spec = SegmentSpec(
        name=str(cfg.get("name") or "learned_segment"),
        membership_source=str(cfg.get("membership_source", "synthetic_screener")),
        prevalence_target=(float(cfg["prevalence_target"]) if cfg.get("prevalence_target") is not None else None),
        prevalence_source=cfg.get("prevalence_source"),
        positive_answers=list(cfg.get("positive_answers") or []),
        min_ess=float(cfg.get("min_ess", 150)),
        min_positive_train=int(cfg.get("min_positive_train", 20)),
        include_sensitive_features=bool(cfg.get("include_sensitive_features", False)),
        include_own_estimates=bool(cfg.get("include_own_estimates", False)),
        exclude_features=list(cfg.get("exclude_features") or []),
    )
    if not spec.positive_answers:
        raise ValueError("learned segment potrebuje positive_answers")

    source = spec.membership_source.lower()
    if source in {"human", "human_screener", "microdata", "measured"}:
        path = Path(str(cfg.get("labels_file", "")))
        if not path.exists():
            raise FileNotFoundError("Measured segment potrebuje labels_file")
        lab = pd.read_csv(path)
        label_col = str(cfg.get("label_column", "label"))
        if label_col not in lab.columns:
            raise KeyError(f"labels_file nema sloupec {label_col}")
        if "panel_row_id" in lab.columns and "panel_row_id" in panel.df.columns:
            mapper = pd.Series(panel.df.index, index=panel.df["panel_row_id"].astype(str))
            idx = lab["panel_row_id"].astype(str).map(mapper)
        elif "panel_index" in lab.columns:
            idx = pd.to_numeric(lab["panel_index"], errors="coerce")
        else:
            raise KeyError("labels_file potrebuje panel_row_id nebo panel_index")
        ok = idx.notna() & lab[label_col].notna()
        train_idx = idx[ok].astype(int).to_numpy()
        y = lab.loc[ok, label_col].astype(int).to_numpy()
        screener_meta = {"source": str(path), "n": int(len(y)), "question_id": None}
    else:
        q = cfg.get("screener")
        if not isinstance(q, dict):
            raise ValueError("synthetic learned segment potrebuje screener question object")
        from dotaznik import run_dotaznik
        screener_n = int(cfg.get("screener_n", min(1500, len(panel.df))))
        screener_uses_context = bool(cfg.get("screener_use_research_context", False))
        sv = run_dotaznik(
            [q], n=screener_n, panel=panel, model=model, mode=mode,
            seed=(seed or 0) + 44017, workers=workers, ulozit=False, tichy=True,
            response_mode="probability", allow_own_estimates=False,
            kontext_udalosti=(context_events if screener_uses_context else None),
            context_sha256=(context_sha256 if screener_uses_context else None),
            persona_mode=str(cfg.get("screener_persona_mode", RUN_DEFAULTS["persona_mode"])),
        )
        qid = str(q["id"])
        train_idx, y = screener_labels(sv["detail"], qid, spec.positive_answers)
        screener_meta = {"source": "npc_synthetic_screener", "n": int(len(y)),
                         "positive": int(y.sum()), "question_id": qid,
                         "run_id": sv.get("run_id"),
                         "research_context_used": screener_uses_context}

    prop, model_obj, _ = fit_propensity_segment(panel.df, train_idx, y, spec, seed=seed or 0)
    profile = profile_segment(panel.df, prop)
    meta = model_obj.to_dict()
    meta.update({"mode": "learned", "screener": screener_meta, "profile": profile})
    if model_obj.ess_population < spec.min_ess:
        behavior = str(cfg.get("low_ess_action", "block")).lower()
        if behavior == "block":
            raise RuntimeError(model_obj.warning)
        meta["low_ess_action"] = behavior
    return prop, meta
