"""Deep, auditable persona overlay for NPC Panel 10.12.

The population core remains unchanged. This module derives *presentation and response-
conditioning features* from existing panel dimensions and demographics. Every feature is
labelled by provenance so a synthetic platform-specific estimate cannot masquerade as an
observed diary variable.

Scale convention
----------------
All ``P_*_10`` columns are integer 1..10. For media platform intensity the scale is also
mapped to a human-readable daily-use anchor. The time anchor is an interpretation band,
not a claim that an individual was observed for that exact duration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OVERLAY_FILE = ROOT / "PERSONA_PROFILE_OVERLAY_v1.csv"
REGISTRY_FILE = ROOT / "PERSONA_PROFILE_REGISTRY_v1.json"

MEDIA_TIME_BANDS = {
    1: (0, "vůbec / 0 min denně"),
    2: (5, "do 5 min denně"),
    3: (15, "cca 15 min denně"),
    4: (30, "cca 30 min denně"),
    5: (60, "cca 1 h denně"),
    6: (90, "cca 1,5 h denně"),
    7: (120, "cca 2 h denně"),
    8: (180, "cca 3 h denně"),
    9: (300, "cca 5 h denně"),
    10: (480, "8+ h denně"),
}

# Compact Czech labels used in persona prompts/UI.
PROFILE_LABELS: dict[str, str] = {
    "P_media_tiktok_10": "TikTok",
    "P_media_instagram_10": "Instagram",
    "P_media_facebook_10": "Facebook",
    "P_media_youtube_10": "YouTube",
    "P_media_online_news_10": "online zpravodajství",
    "P_media_tv_10": "televize",
    "P_media_radio_10": "rádio",
    "P_media_podcasts_10": "podcasty",
    "P_media_streaming_10": "streaming",
    "P_media_print_10": "tištěná média",
    "P_buy_price_sensitivity_10": "citlivost na cenu",
    "P_buy_wtp_premium_10": "ochota připlatit",
    "P_buy_planned_10": "plánovanost nákupu",
    "P_buy_impulse_10": "impulzivnost nákupu",
    "P_buy_deal_orientation_10": "orientace na akce/slevy",
    "P_buy_private_label_10": "otevřenost privátním značkám",
    "P_buy_brand_loyalty_10": "věrnost značkám",
    "P_buy_reviews_10": "vliv recenzí",
    "P_buy_status_brand_10": "statusová role značky",
    "P_buy_premium_orientation_10": "prémiová orientace",
    "P_buy_online_10": "online nakupování",
    "P_buy_novelty_10": "vyhledávání novinek",
    "P_brand_authenticity_10": "autenticita a důvěryhodnost",
    "P_brand_innovation_10": "inovativnost",
    "P_brand_sustainability_10": "udržitelnost",
    "P_brand_social_proof_10": "doporučení a sociální důkaz",
    "P_brand_value_money_10": "poměr cena/výkon",
    "P_brand_quality_premium_10": "kvalita a ochota připlatit",
    "P_brand_design_status_10": "design a status",
    "P_brand_local_origin_10": "lokální původ",
    "P_brand_evidence_10": "recenze a ověřitelné důkazy",
    "P_brand_switch_readiness_10": "ochota změnit značku",
    "P_value_open_change_10": "otevřenost změně",
    "P_value_environment_10": "environmentální odpovědnost",
    "P_value_local_10": "lokální ukotvení",
    "P_value_social_trust_10": "sociální důvěra",
    "P_value_institution_trust_10": "důvěra institucím",
    "P_value_firm_trust_10": "důvěra firmám",
    "P_value_redistribution_10": "podpora redistribuce",
    "P_value_liberal_10": "liberální orientace",
    "P_value_traditional_10": "tradiční orientace",
    "P_life_health_10": "zdravý životní styl",
    "P_life_activity_10": "pohyb",
    "P_life_reading_10": "čtení",
    "P_life_travel_10": "zahraniční cestování",
    "P_life_gaming_10": "hraní her",
    "P_digital_ai_10": "adopce AI",
    "P_digital_banking_10": "internetové bankovnictví",
    "P_digital_egov_10": "e-government",
}

MEDIA_COLS = [
    "P_media_tiktok_10", "P_media_instagram_10", "P_media_facebook_10",
    "P_media_youtube_10", "P_media_online_news_10", "P_media_tv_10",
    "P_media_radio_10", "P_media_podcasts_10", "P_media_streaming_10",
    "P_media_print_10",
]
BUY_COLS = [
    "P_buy_price_sensitivity_10", "P_buy_wtp_premium_10", "P_buy_planned_10",
    "P_buy_impulse_10", "P_buy_deal_orientation_10", "P_buy_private_label_10",
    "P_buy_brand_loyalty_10", "P_buy_reviews_10", "P_buy_status_brand_10",
    "P_buy_premium_orientation_10", "P_buy_online_10", "P_buy_novelty_10",
]
BRAND_DRIVER_COLS = [
    "P_brand_authenticity_10", "P_brand_innovation_10", "P_brand_sustainability_10",
    "P_brand_social_proof_10", "P_brand_value_money_10", "P_brand_quality_premium_10",
    "P_brand_design_status_10", "P_brand_local_origin_10", "P_brand_evidence_10",
    "P_brand_switch_readiness_10",
]
VALUE_COLS = [
    "P_value_open_change_10", "P_value_environment_10", "P_value_local_10",
    "P_value_social_trust_10", "P_value_institution_trust_10", "P_value_firm_trust_10",
    "P_value_redistribution_10", "P_value_liberal_10", "P_value_traditional_10",
]
LIFE_COLS = [
    "P_life_health_10", "P_life_activity_10", "P_life_reading_10",
    "P_life_travel_10", "P_life_gaming_10", "P_digital_ai_10",
    "P_digital_banking_10", "P_digital_egov_10",
]


def media_time_label(score: Any) -> str:
    try:
        s = int(round(float(score)))
    except Exception:
        return "neuvedeno"
    s = min(10, max(1, s))
    return MEDIA_TIME_BANDS[s][1]


def _z(s: pd.Series, default: float = 0.0) -> np.ndarray:
    x = pd.to_numeric(s, errors="coerce").astype(float)
    if x.notna().sum() == 0:
        return np.full(len(s), default, dtype=float)
    x = x.fillna(x.median())
    sd = float(x.std(ddof=0))
    if not np.isfinite(sd) or sd <= 1e-12:
        return np.full(len(s), default, dtype=float)
    return ((x - float(x.mean())) / sd).to_numpy(dtype=float)


def _col_z(df: pd.DataFrame, name: str) -> np.ndarray:
    if name not in df:
        return np.zeros(len(df), dtype=float)
    return _z(df[name])


def _stable_noise(ids: pd.Series, salt: str) -> np.ndarray:
    # Deterministic pseudo-normal residual: stable across runs and Python versions.
    out = np.empty(len(ids), dtype=float)
    for i, v in enumerate(ids.astype(str)):
        h = hashlib.sha256((salt + "|" + v).encode("utf-8")).digest()
        u1 = (int.from_bytes(h[:8], "big") + 1) / (2**64 + 2)
        u2 = (int.from_bytes(h[8:16], "big") + 1) / (2**64 + 2)
        out[i] = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return out


def _decile(latent: np.ndarray) -> np.ndarray:
    s = pd.Series(latent)
    # Percentile rank keeps the score interpretable as relative intensity within the
    # Czech synthetic population. Ties are deterministic by order.
    pct = s.rank(method="average", pct=True).to_numpy(dtype=float)
    return np.clip(np.ceil(pct * 10), 1, 10).astype("int8")


def _direct(df: pd.DataFrame, dim: str, invert: bool = False) -> np.ndarray:
    z = _col_z(df, dim)
    return _decile(-z if invert else z)


def build_persona_overlay(df: pd.DataFrame) -> pd.DataFrame:
    if "panel_row_id" not in df:
        raise ValueError("Panel needs panel_row_id for persona overlay")
    ids = df["panel_row_id"].astype(str)
    age = pd.to_numeric(df.get("vek", 45), errors="coerce").fillna(45).to_numpy(float)
    agez = (age - 45.0) / 18.0
    young = np.clip((35.0 - age) / 12.0, -2.2, 2.2)
    very_young = np.clip((28.0 - age) / 8.0, -2.5, 2.5)
    older = np.clip((age - 48.0) / 16.0, -2.0, 2.2)
    midlife = -np.abs(age - 45.0) / 22.0 + 0.75

    social = _col_z(df, "D_socialni_site")
    online = _col_z(df, "D_media_online")
    digital = _col_z(df, "D_digitalni_zivot")
    public = _col_z(df, "D_zajem_verejne_deni")
    open_change = _col_z(df, "D_otevrenost_zmene")
    novelty = _col_z(df, "TCI_NS_Vyhledavani_noveho")
    extr = _col_z(df, "X_Extraverze")
    edu = _col_z(df, "D_kognitivni_gramotnost")

    def med(name: str, latent: np.ndarray) -> np.ndarray:
        return _decile(latent + .28 * _stable_noise(ids, "media:" + name))

    out = pd.DataFrame({"panel_row_id": ids})
    out["P_media_tiktok_10"] = med("tiktok", .70*social + .32*digital + 1.05*very_young + .15*novelty)
    out["P_media_instagram_10"] = med("instagram", .75*social + .30*digital + .70*young + .18*open_change + .10*extr)
    out["P_media_facebook_10"] = med("facebook", .70*social + .24*digital + .35*midlife - .20*very_young)
    out["P_media_youtube_10"] = med("youtube", .48*online + .48*social + .42*young + .20*digital)
    out["P_media_online_news_10"] = med("online_news", .72*online + .30*public + .18*digital + .12*edu)
    out["P_media_tv_10"] = med("tv", .78*older - .25*digital + .25*public)
    out["P_media_radio_10"] = med("radio", .34*online + .35*midlife + .18*public)
    out["P_media_podcasts_10"] = med("podcasts", .45*online + .35*digital + .32*open_change + .20*edu + .18*young)
    out["P_media_streaming_10"] = med("streaming", .55*digital + .48*young + .24*open_change + .18*social)
    out["P_media_print_10"] = med("print", .62*older - .22*digital + .27*public + .15*edu)

    # Directly inherited panel dimensions -> relative 1-10 expression.
    direct_map = {
        "P_buy_price_sensitivity_10": "D_cenova_citlivost",
        "P_buy_wtp_premium_10": "D_ochota_priplatit",
        "P_buy_planned_10": "D_planovitost_nakupu",
        "P_buy_private_label_10": "D_privatni_znacky",
        "P_buy_brand_loyalty_10": "D_vernost_znacce",
        "P_buy_reviews_10": "D_vliv_recenzi",
        "P_buy_status_brand_10": "D_status_znacka",
        "P_buy_online_10": "D_ecommerce",
        "P_value_open_change_10": "D_otevrenost_zmene",
        "P_value_environment_10": "D_klimaticka_odpovednost" if "D_klimaticka_odpovednost" in df else "D_ekologicka_uvedomelost",
        "P_value_local_10": "D_lokalni_ukotveni",
        "P_value_social_trust_10": "D_socialni_duvera",
        "P_value_institution_trust_10": "D_duvera_instituce",
        "P_value_firm_trust_10": "D_duvera_firmam",
        "P_value_redistribution_10": "D_silna_podpora_redistribuce",
        "P_value_liberal_10": "D_liberalni_orientace",
        "P_value_traditional_10": "D_tradicni_genderove_role",
        "P_life_health_10": "D_zdravy_zivotni_styl",
        "P_life_activity_10": "D_aktivni_pohyb",
        "P_life_reading_10": "D_cetba_knih",
        "P_life_travel_10": "D_cestovani_zahranici",
        "P_life_gaming_10": "D_hraje_hry_tydne",
        "P_digital_ai_10": "D_adopce_ai",
        "P_digital_banking_10": "D_internetove_bankovnictvi",
        "P_digital_egov_10": "D_egovernment_use",
    }
    for dst, src in direct_map.items():
        out[dst] = _direct(df, src)

    # Explicitly derived consumer constructs. They are useful for the LLM but remain
    # SYNTHETIC_DERIVED in the registry and therefore can be ablated separately.
    plan = _col_z(df, "D_planovitost_nakupu")
    price = _col_z(df, "D_cenova_citlivost")
    private = _col_z(df, "D_privatni_znacky")
    wtp = _col_z(df, "D_ochota_priplatit")
    status = _col_z(df, "D_status_znacka")
    reviews = _col_z(df, "D_vliv_recenzi")
    timep = _col_z(df, "D_casova_tisen")
    honesty = _col_z(df, "H_Poctivost_pokora")
    out["P_buy_impulse_10"] = _decile(-.72*plan + .35*novelty + .22*extr + .15*timep - .10*honesty + .25*_stable_noise(ids,"buy:impulse"))
    out["P_buy_deal_orientation_10"] = _decile(.65*price + .35*private - .18*wtp + .20*_stable_noise(ids,"buy:deal"))
    out["P_buy_premium_orientation_10"] = _decile(.52*wtp + .35*status + .20*open_change - .25*price + .16*_stable_noise(ids,"buy:premium"))
    out["P_buy_novelty_10"] = _decile(.45*novelty + .35*open_change + .22*digital + .15*_stable_noise(ids,"buy:novelty"))

    # Brand-response drivers. These are explicitly SYNTHETIC_DERIVED: they summarize
    # how existing traits are likely to enter a brand judgment; they are not observed
    # reactions to any specific brand. The actual brand response remains an outcome of
    # the survey question and can therefore disagree with these predispositions.
    loyalty = _col_z(df, "D_vernost_znacce")
    firmtrust = _col_z(df, "D_duvera_firmam")
    local = _col_z(df, "D_lokalni_ukotveni")
    climate = _col_z(df, "D_klimaticka_odpovednost")
    health = _col_z(df, "D_zdravy_zivotni_styl")
    statusz = _col_z(df, "D_status_znacka")
    cog = _col_z(df, "D_kognitivni_gramotnost")
    out["P_brand_authenticity_10"] = _decile(.34*honesty + .28*firmtrust + .22*local + .12*reviews + .15*_stable_noise(ids,"brand:auth"))
    out["P_brand_innovation_10"] = _decile(.40*open_change + .30*novelty + .20*digital + .12*_stable_noise(ids,"brand:innovation"))
    out["P_brand_sustainability_10"] = _decile(.62*climate + .18*health + .15*local + .12*_stable_noise(ids,"brand:sustain"))
    out["P_brand_social_proof_10"] = _decile(.48*reviews + .25*social + .15*extr + .12*_stable_noise(ids,"brand:socialproof"))
    out["P_brand_value_money_10"] = _decile(.55*price + .24*private - .18*wtp + .16*_stable_noise(ids,"brand:value"))
    out["P_brand_quality_premium_10"] = _decile(.55*wtp + .22*loyalty + .18*statusz - .14*price + .14*_stable_noise(ids,"brand:quality"))
    out["P_brand_design_status_10"] = _decile(.58*statusz + .24*wtp + .14*open_change + .12*_stable_noise(ids,"brand:status"))
    out["P_brand_local_origin_10"] = _decile(.72*local + .16*firmtrust + .12*_stable_noise(ids,"brand:local"))
    out["P_brand_evidence_10"] = _decile(.56*reviews + .23*cog + .15*online + .12*_stable_noise(ids,"brand:evidence"))
    out["P_brand_switch_readiness_10"] = _decile(.42*novelty + .34*open_change - .48*loyalty + .16*_stable_noise(ids,"brand:switch"))

    # Concrete time estimates for UI/persona. Social-platform minutes share one daily
    # budget so a profile cannot simultaneously claim 8h TikTok + 8h Instagram + 8h Facebook.
    # The budget is still a modeled estimate, not observed device telemetry.
    total_social = np.array([MEDIA_TIME_BANDS[int(x)][0] for x in _decile(.72*social+.28*digital)], dtype=float)
    social_cols=["P_media_tiktok_10","P_media_instagram_10","P_media_facebook_10","P_media_youtube_10"]
    smat=out[social_cols].to_numpy(float)
    weights=np.exp((smat-5.5)/1.8); weights[smat<=1]=0.0
    denom=weights.sum(axis=1); denom=np.where(denom>0,denom,1.0)
    mins=(weights/denom[:,None])*total_social[:,None]
    anchors=np.array([MEDIA_TIME_BANDS[i][0] for i in range(1,11)],dtype=float)
    def score_from_minutes(arr):
        arr=np.asarray(arr,dtype=float)
        # Nearest explicit time anchor -> the displayed 1–10 and minute estimate agree.
        return (np.abs(arr[:,None]-anchors[None,:]).argmin(axis=1)+1).astype("int8")
    for j,c in enumerate(social_cols):
        mm=np.rint(mins[:,j]).astype("int16")
        out[c[:-3]+"_minutes_day"] = mm
        out[c] = score_from_minutes(mm)
    caps={
      "P_media_online_news_10":120,"P_media_tv_10":300,"P_media_radio_10":300,
      "P_media_podcasts_10":180,"P_media_streaming_10":300,"P_media_print_10":90,
    }
    for c,cap in caps.items():
        score=out[c].to_numpy(int); ref=np.array([MEDIA_TIME_BANDS[int(x)][0] for x in score],dtype=float)
        out[c[:-3]+"_minutes_day"] = np.rint(np.minimum(ref,cap)).astype("int16")
    out["P_media_social_total_minutes_day"]=np.rint(total_social).astype("int16")
    return out


def build_registry(dictionary_path: Path | None = None) -> dict[str, Any]:
    dictionary_path = dictionary_path or ROOT / "DIMENSION_DATA_DICTIONARY_v2.csv"
    inherited: dict[str, dict[str, Any]] = {}
    if dictionary_path.exists():
        try:
            d = pd.read_csv(dictionary_path)
            for _, r in d.iterrows():
                inherited[str(r.get("column"))] = {
                    "source_role": None if pd.isna(r.get("source_role")) else str(r.get("source_role")),
                    "confidence": None if pd.isna(r.get("confidence")) else float(r.get("confidence")),
                    "source": None if pd.isna(r.get("source")) else str(r.get("source")),
                }
        except Exception:
            inherited = {}
    direct_basis = {
        "P_buy_price_sensitivity_10":"D_cenova_citlivost", "P_buy_wtp_premium_10":"D_ochota_priplatit",
        "P_buy_planned_10":"D_planovitost_nakupu", "P_buy_private_label_10":"D_privatni_znacky",
        "P_buy_brand_loyalty_10":"D_vernost_znacce", "P_buy_reviews_10":"D_vliv_recenzi",
        "P_buy_status_brand_10":"D_status_znacka", "P_buy_online_10":"D_ecommerce",
        "P_value_open_change_10":"D_otevrenost_zmene", "P_value_environment_10":"D_klimaticka_odpovednost",
        "P_value_local_10":"D_lokalni_ukotveni", "P_value_social_trust_10":"D_socialni_duvera",
        "P_value_institution_trust_10":"D_duvera_instituce", "P_value_firm_trust_10":"D_duvera_firmam",
        "P_value_redistribution_10":"D_silna_podpora_redistribuce", "P_value_liberal_10":"D_liberalni_orientace",
        "P_value_traditional_10":"D_tradicni_genderove_role", "P_life_health_10":"D_zdravy_zivotni_styl",
        "P_life_activity_10":"D_aktivni_pohyb", "P_life_reading_10":"D_cetba_knih",
        "P_life_travel_10":"D_cestovani_zahranici", "P_life_gaming_10":"D_hraje_hry_tydne",
        "P_digital_ai_10":"D_adopce_ai", "P_digital_banking_10":"D_internetove_bankovnictvi",
        "P_digital_egov_10":"D_egovernment_use",
    }
    derived_basis = {
        **{c: ["D_socialni_site", "D_media_online", "D_digitalni_zivot", "vek", "+ deterministic residual"] for c in MEDIA_COLS},
        "P_buy_impulse_10":["D_planovitost_nakupu","TCI_NS_Vyhledavani_noveho","X_Extraverze","D_casova_tisen"],
        "P_buy_deal_orientation_10":["D_cenova_citlivost","D_privatni_znacky","D_ochota_priplatit"],
        "P_buy_premium_orientation_10":["D_ochota_priplatit","D_status_znacka","D_otevrenost_zmene","D_cenova_citlivost"],
        "P_buy_novelty_10":["TCI_NS_Vyhledavani_noveho","D_otevrenost_zmene","D_digitalni_zivot"],
        "P_brand_authenticity_10":["H_Poctivost_pokora","D_duvera_firmam","D_lokalni_ukotveni","D_vliv_recenzi"],
        "P_brand_innovation_10":["D_otevrenost_zmene","TCI_NS_Vyhledavani_noveho","D_digitalni_zivot"],
        "P_brand_sustainability_10":["D_klimaticka_odpovednost","D_zdravy_zivotni_styl","D_lokalni_ukotveni"],
        "P_brand_social_proof_10":["D_vliv_recenzi","D_socialni_site","X_Extraverze"],
        "P_brand_value_money_10":["D_cenova_citlivost","D_privatni_znacky","D_ochota_priplatit"],
        "P_brand_quality_premium_10":["D_ochota_priplatit","D_vernost_znacce","D_status_znacka","D_cenova_citlivost"],
        "P_brand_design_status_10":["D_status_znacka","D_ochota_priplatit","D_otevrenost_zmene"],
        "P_brand_local_origin_10":["D_lokalni_ukotveni","D_duvera_firmam"],
        "P_brand_evidence_10":["D_vliv_recenzi","D_kognitivni_gramotnost","D_media_online"],
        "P_brand_switch_readiness_10":["TCI_NS_Vyhledavani_noveho","D_otevrenost_zmene","D_vernost_znacce"],
    }
    fields = {}
    for c, src in direct_basis.items():
        old = inherited.get(src, {})
        fields[c] = {"label": PROFILE_LABELS.get(c,c), "profile_role":"PANEL_DIMENSION_RESCALED",
                     "basis":[src], "inherited_source_role":old.get("source_role"),
                     "inherited_confidence":old.get("confidence"), "source":old.get("source"),
                     "scale":"1-10 relative intensity"}
    for c,basis in derived_basis.items():
        fields[c] = {"label":PROFILE_LABELS.get(c,c), "profile_role":"SYNTHETIC_DERIVED",
                     "basis":basis, "scale":"1-10 modeled relative intensity",
                     "warning":"Not an observed individual diary/transaction. Use as persona conditioning and sensitivity layer."}
    return {
        "version":"persona-profile-v1-10.13.0",
        "population_core_changed":False,
        "purpose":"deepen persona conditioning without pretending derived traits are directly measured",
        "media_time_scale":{str(k):{"minutes_midpoint":v[0],"label":v[1]} for k,v in MEDIA_TIME_BANDS.items()},
        "media_time_warning":"1–10 has explicit time-reference anchors. Per-platform minutes are a budget-constrained modeled estimate, not observed device telemetry; non-social channels may overlap in real life.",
        "fields":fields,
    }


def attach_overlay(df: pd.DataFrame, *, overlay_path: Path | None = None) -> pd.DataFrame:
    """Attach overlay only when it matches the supplied panel safely.

    For custom panel builds/tests, if fewer than 80% of ids are found we leave the frame
    untouched rather than silently borrowing profiles from another population build.
    """
    if os.getenv("NPC_DISABLE_PERSONA_OVERLAY", "").strip().lower() in {"1","true","yes"}:
        return df
    # v15.2 population rows have a coherent core + explicit donor blocks. The old
    # P_* overlay is intentionally never attached to them, even if a legacy file
    # happens to exist next to the runtime.
    if "core_source" in df.columns and "prijem_osobni_mesicni" in df.columns:
        return df
    if "panel_row_id" not in df or any(c.startswith("P_media_") for c in df.columns):
        return df
    p = overlay_path or Path(os.getenv("NPC_PERSONA_OVERLAY", str(OVERLAY_FILE)))
    if not p.exists():
        return df
    try:
        ov = pd.read_csv(p, low_memory=False)
        if "panel_row_id" not in ov:
            return df
        ids = set(df["panel_row_id"].astype(str))
        oids = set(ov["panel_row_id"].astype(str))
        if not ids or len(ids & oids) / len(ids) < .80:
            return df
        left = df.copy(); left["panel_row_id"] = left["panel_row_id"].astype(str)
        ov["panel_row_id"] = ov["panel_row_id"].astype(str)
        return left.merge(ov, on="panel_row_id", how="left", validate="many_to_one")
    except Exception:
        return df


def _minutes_text(minutes: Any) -> str:
    try: m=max(0,int(round(float(minutes))))
    except Exception: return "čas neuveden"
    if m==0:return "0 min/den"
    if m<60:return f"~{m} min/den"
    h=m/60.0
    return f"~{h:.1f} h/den".replace(".0 "," ").replace(".",",")


def _score(row: pd.Series, c: str) -> int | None:
    try:
        x = row.get(c)
        if pd.isna(x): return None
        return min(10,max(1,int(round(float(x)))))
    except Exception:
        return None


def _format_scores(row: pd.Series, cols: list[str], *, top: int | None = None) -> str:
    vals=[]
    for c in cols:
        s=_score(row,c)
        if s is None: continue
        vals.append((c,s))
    if top is not None:
        # keep both strongly high and strongly low traits; those carry the most persona information
        vals=sorted(vals,key=lambda cs: -abs(cs[1]-5.5))[:top]
    return "; ".join(f"{PROFILE_LABELS.get(c,c)} {s}/10" for c,s in vals)


SIGNAL_TOPICS: dict[str, set[str]] = {
    # media
    "P_media_tiktok_10": {"media","socialni_site","online","reklama"},
    "P_media_instagram_10": {"media","socialni_site","online","reklama"},
    "P_media_facebook_10": {"media","socialni_site","online","reklama"},
    "P_media_youtube_10": {"media","online","video","reklama"},
    "P_media_online_news_10": {"media","online","zpravodajstvi","politika","verejne"},
    "P_media_tv_10": {"media","televize","reklama","zpravodajstvi"},
    "P_media_radio_10": {"media","radio","reklama"},
    "P_media_podcasts_10": {"media","podcasty","online"},
    "P_media_streaming_10": {"media","streaming","online","video"},
    "P_media_print_10": {"media","tisk","zpravodajstvi"},
    # buying
    "P_buy_price_sensitivity_10": {"nakup","cena","finance","sleva"},
    "P_buy_wtp_premium_10": {"nakup","cena","finance","premium","znacka"},
    "P_buy_planned_10": {"nakup","rozhodovani"},
    "P_buy_impulse_10": {"nakup","rozhodovani"},
    "P_buy_deal_orientation_10": {"nakup","cena","sleva","finance"},
    "P_buy_private_label_10": {"nakup","znacka","retail"},
    "P_buy_brand_loyalty_10": {"nakup","znacka","loajalita"},
    "P_buy_reviews_10": {"nakup","znacka","recenze","online"},
    "P_buy_status_brand_10": {"znacka","status","premium"},
    "P_buy_premium_orientation_10": {"nakup","znacka","premium","cena"},
    "P_buy_online_10": {"nakup","online","ecommerce"},
    "P_buy_novelty_10": {"nakup","znacka","novinka","inovace"},
    # brand response
    "P_brand_authenticity_10": {"znacka","duvera","reklama"},
    "P_brand_innovation_10": {"znacka","inovace","novinka","technologie"},
    "P_brand_sustainability_10": {"znacka","udrzitelnost","klima","ekologie"},
    "P_brand_social_proof_10": {"znacka","reklama","recenze","socialni_site"},
    "P_brand_value_money_10": {"znacka","cena","nakup"},
    "P_brand_quality_premium_10": {"znacka","premium","kvalita","cena"},
    "P_brand_design_status_10": {"znacka","design","status"},
    "P_brand_local_origin_10": {"znacka","lokalni","puvod"},
    "P_brand_evidence_10": {"znacka","recenze","dukazy","duvera"},
    "P_brand_switch_readiness_10": {"znacka","loajalita","novinka"},
    # values: deliberately narrow; generic health/finance questions do not unlock all values
    "P_value_open_change_10": {"politika","verejne","zmena","inovace","technologie"},
    "P_value_environment_10": {"politika","verejne","klima","ekologie","udrzitelnost"},
    "P_value_local_10": {"politika","verejne","lokalni","komunita"},
    "P_value_social_trust_10": {"vztahy","spolecnost","duvera","politika"},
    "P_value_institution_trust_10": {"politika","verejne","instituce","regulace","duvera"},
    "P_value_firm_trust_10": {"znacka","firma","sluzby","finance","duvera"},
    "P_value_redistribution_10": {"politika","verejne","redistribuce","socialni"},
    "P_value_liberal_10": {"politika","verejne","liberalni","hodnoty"},
    "P_value_traditional_10": {"politika","verejne","tradice","hodnoty"},
    # life/digital
    "P_life_health_10": {"zdravi","zivotni_styl"},
    "P_life_activity_10": {"zdravi","sport","pohyb","zivotni_styl"},
    "P_life_reading_10": {"cetba","knihy","kultura","volny_cas"},
    "P_life_travel_10": {"cestovani","dovolena","volny_cas"},
    "P_life_gaming_10": {"hry","gaming","volny_cas","technologie"},
    "P_digital_ai_10": {"ai","umela_inteligence","technologie","digital"},
    "P_digital_banking_10": {"finance","bankovnictvi","digital"},
    "P_digital_egov_10": {"verejne","egovernment","digital","instituce"},
}


def deep_profile_text(row: pd.Series, temata: list[str] | None = None, *, mode: str = "core", adaptive: bool = False) -> str:
    """Compact behavior context for one respondent.

    Production ``adaptive`` personas do *signal-level retrieval*, not category-level
    dumping.  A small policy-controlled number of modeled signals enters the prompt and each must match the
    current question topics. Legacy ``core`` / ``full`` modes retain the broader
    blocks only for ablation/diagnostic comparability.
    """
    if mode not in {"core","full"}:
        return ""
    topics={str(x).strip().lower() for x in (temata or []) if str(x).strip()}
    all_cols = MEDIA_COLS + BUY_COLS + BRAND_DRIVER_COLS + VALUE_COLS + LIFE_COLS

    if adaptive:
        # 10.20 production path MUST run before checking legacy P_* columns: the
        # legacy panel layouts may contain D_* evidence but no
        # P_* overlay columns.
        from persona_grounded import grounded_profile_text
        grounded = grounded_profile_text(row, topics)
        if grounded:
            return grounded
        # Compatibility fallback only: no canonical grounded candidate was available.
        # It is relevant only for custom/legacy rows that actually carry P_* fields.
        if not topics or not any(c in row.index for c in all_cols):
            return ""
        groups = [
            ("media", MEDIA_COLS), ("buy", BUY_COLS), ("brand", BRAND_DRIVER_COLS),
            ("value", VALUE_COLS), ("life", LIFE_COLS),
        ]
        candidates=[]
        for group, cols in groups:
            for c in cols:
                if not (topics & SIGNAL_TOPICS.get(c,set())):
                    continue
                score=_score(row,c)
                if score is None:
                    continue
                candidates.append((abs(float(score)-5.5), group, c, score))
        if not candidates:
            return ""
        from product_policy import persona_signal_budget
        candidates.sort(key=lambda x:(-x[0], x[2]))
        selected=candidates[:persona_signal_budget(topics)]
        by_group={g:[] for g,_ in groups}
        for _,g,c,score in selected:
            by_group[g].append((c,score))
        lines=[]
        if by_group["media"]:
            vals=[]
            for c,score in by_group["media"]:
                mcol=c[:-3]+"_minutes_day"
                mt=_minutes_text(row.get(mcol)) if mcol in row.index and pd.notna(row.get(mcol)) else media_time_label(score)
                vals.append(f"{PROFILE_LABELS[c]} {score}/10 ({mt})")
            lines.append("Mediální chování [compatibility model]: "+"; ".join(vals))
        if by_group["buy"]:
            lines.append("Nákupní profil [compatibility model]: "+"; ".join(f"{PROFILE_LABELS[c]} {score}/10" for c,score in by_group["buy"]))
        if by_group["brand"]:
            lines.append("Reakce na značku [compatibility model]: "+"; ".join(f"{PROFILE_LABELS[c]} {score}/10" for c,score in by_group["brand"]))
        if by_group["value"]:
            lines.append("Relevantní hodnotový signál [compatibility model]: "+"; ".join(f"{PROFILE_LABELS[c]} {score}/10" for c,score in by_group["value"]))
        if by_group["life"]:
            lines.append("Relevantní životní/digitální chování [compatibility model]: "+"; ".join(f"{PROFILE_LABELS[c]} {score}/10" for c,score in by_group["life"]))
        return "\n".join(lines)

    # Legacy diagnostic arms: deliberately broader to preserve benchmark history.
    if not any(c in row.index for c in all_cols):
        return ""
    lines=[]
    media_vals=[]
    for c in MEDIA_COLS:
        score=_score(row,c)
        if score is not None: media_vals.append((c,score))
    media_vals=sorted(media_vals,key=lambda cs:-abs(cs[1]-5.5))[:4]
    if media_vals:
        txt=[]
        for c,score in media_vals[:7 if mode=="full" else 5]:
            mcol=c[:-3]+"_minutes_day"
            mt=_minutes_text(row.get(mcol)) if mcol in row.index and pd.notna(row.get(mcol)) else media_time_label(score)
            txt.append(f"{PROFILE_LABELS[c]} {score}/10 ({mt})")
        lines.append("Mediální chování [modelovaná intenzita]: " + "; ".join(txt))
    txt=_format_scores(row, BUY_COLS, top=8 if mode=="full" else 6)
    if txt: lines.append("Nákupní a značkový profil [1–10]: " + txt)
    txt=_format_scores(row, BRAND_DRIVER_COLS, top=8 if mode=="full" else 6)
    if txt: lines.append("Co typicky rozhoduje při reakci na značku [1–10; predispozice, ne výsledek konkrétního testu]: " + txt)
    txt=_format_scores(row, VALUE_COLS, top=7 if mode=="full" else 5)
    if txt: lines.append("Hodnoty a postoje [1–10]: " + txt)
    txt=_format_scores(row, LIFE_COLS, top=6)
    if txt: lines.append("Životní/digitální chování [1–10]: " + txt)
    if lines:
        lines.append("Poznámka k profilu: jde o relativní/modelové signály; diagnostické režimy je záměrně ukazují šířeji než produkční adaptivní persona.")
    return "\n".join(lines)


def write_overlay(panel_path: str | Path, output: str | Path = OVERLAY_FILE) -> Path:
    df=pd.read_csv(panel_path,low_memory=False)
    ov=build_persona_overlay(df)
    output=Path(output); ov.to_csv(output,index=False)
    REGISTRY_FILE.write_text(json.dumps(build_registry(),ensure_ascii=False,indent=2),encoding="utf-8")
    return output


if __name__ == "__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("panel"); ap.add_argument("-o",default=str(OVERLAY_FILE)); args=ap.parse_args()
    p=write_overlay(args.panel,args.o); print(p)
