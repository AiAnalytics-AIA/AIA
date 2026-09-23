"""
NPC PANEL — pipeline.py
Hlavní rozhraní: run_pruzkum(otazka, n, filtry, kategorie)

Nahrazuje llm_survey_engine.py + survey_aggregator.py.
Vyžaduje: pandas, numpy, anthropic ; ANTHROPIC_API_KEY (kromě mode="dry")

Použití:
    from pipeline import run_pruzkum
    v = run_pruzkum("Kolik byste připlatili za...", n=500,
                    kategorie=["do 100 Kc","100-300 Kc","nad 300 Kc","nic"])
    print(v["celkem_pct"])
"""

from __future__ import annotations

import json
import os
import re
import time
import threading
import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np
import pandas as pd

from env_loader import load_dotenv
load_dotenv()

# ---------------------------------------------------------------- konfigurace

from data_contract import panel_path as _contract_panel_path, weight as _contract_weight
_DEFAULT_PANEL = _contract_panel_path()
_INGEST_REGISTRY = Path(os.environ.get("NPC_INGEST_REGISTRY", str(Path(__file__).with_name("data") / "ingest_registry.sqlite")))

def resolve_panel_path() -> str:
    """Resolve active immutable ingest version unless NPC_PANEL explicitly pins a file."""
    if os.environ.get("NPC_PANEL"):
        return os.environ["NPC_PANEL"]
    if _INGEST_REGISTRY.exists():
        try:
            from npc_ingest.registry import Registry
            with Registry(_INGEST_REGISTRY) as reg:
                active = reg.active_version()
            if active and Path(active["cesta"]).exists():
                return str(Path(active["cesta"]))
        except Exception:
            pass
    return str(_DEFAULT_PANEL)

PANEL_PATH = resolve_panel_path()

def resolve_panel_metadata(path: str|Path|None=None) -> dict[str, Any]:
    """Resolve immutable panel/version metadata for output provenance.

    ``target_hash`` binds a recalibrated ingest snapshot to the exact Track-B target
    payload. The base v14 snapshot instead binds to the Census backbone targets file.
    """
    p=Path(path or resolve_panel_path()).resolve()
    meta={"panel_version":"v17.1.2" if p.name==_DEFAULT_PANEL.name else p.stem,
          "target_hash":"","registry_managed":False}
    if _INGEST_REGISTRY.exists():
        try:
            from npc_ingest.registry import Registry
            with Registry(_INGEST_REGISTRY) as reg:
                row=reg.version_for_path(p)
            if row:
                meta.update({"panel_version":row.get("verze") or meta["panel_version"],
                             "target_hash":row.get("hash_cilu") or "",
                             "registry_managed":True,
                             "parent_version":row.get("rodic") or ""})
                return meta
        except Exception:
            pass
    # Base v15.2 is Census-anchored: hash the exact retained target artifact.
    if p.name==_DEFAULT_PANEL.name:
        target_file=Path(__file__).with_name("BACKBONE_CENSUS_2021_TARGETS.csv")
        if target_file.exists():
            h=hashlib.sha256()
            with target_file.open("rb") as f:
                for ch in iter(lambda:f.read(1024*1024),b""):
                    h.update(ch)
            meta["target_hash"]=h.hexdigest()
    return meta

RUNS_DIR = Path(os.environ.get("NPC_RUNS", "runs"))

# Respondent-question cells carried by a single grouped provider call.  This one number
# governs the call count of a blocked run (calls ~= respondents * questions / budget),
# not the block size: at 336 a 112x45 run costs 15 calls whether blocks hold 6 or 8
# questions.  dotaznik imports it so the preflight forecast can never drift from what
# actually executes.  Raise it only against a real parity run; the ceiling protects the
# structured output limit and Windows stdin.
BLOCK_CELL_BUDGET = max(48, min(1200, int(os.environ.get("NPC_RESPONDENT_BLOCK_CELL_BUDGET", "336") or 336)))
_BLOCK_CELL_BUDGET = BLOCK_CELL_BUDGET

# Model IDs and cost estimates live in one audited place.
from runtime_config import DEFAULT_MODEL, resolve_model, pricing, resolve_provider_model, provider_pricing, RUN_DEFAULTS
from anthropic_compat import create_message, sanitize_params

# Backward-compatible mapping used by older aggregation/report code.
CENIK = {m: pricing(m) for m in [
    DEFAULT_MODEL, "claude-sonnet-5", "claude-opus-5"
]}

SEGMENTY = ["pohlavi", "vek_skupina", "vzdelani", "kraj", "zamestnani_status"]

# prefixy psychologickych vrstev v panelu (suffixy se detekuji automaticky)
PREFIXY = {
    "hexaco": ("H_", "E_", "X_", "A_", "C_", "O_"),
    "elements": ("Air_", "Earth_", "Fire_", "Water_"),
    "tci": ("TCI_",),
    "schwartz": ("SCHWARTZ_",),
    "spokojenost": ("spokojenost_",),
    "dispozice": ("D_",),
}

# Vrstvy vyrazene z bloku "Povaha" v persone. Dispozice maji vlastni sekci.
# Schwartz: 6 dimenzi je konstanta, Uspech ma
# 3 hodnoty a zbyle tri (Tradice, Konformita, Stimulace) koreluji s vekem
# na r = 1,00 / 1,00 / 0,98 — je to vek prevedeny do jine skaly, ne hodnoty.
# Vek uz v persone je. Az bude vrstva prepocitana, staci prefix odebrat.
VYRAZENE_VRSTVY = ("schwartz", "spokojenost", "dispozice")

STUPNE = [
    (-1.25, "velmi nizka"),
    (-0.5, "spise nizka"),
    (0.5, "prumerna"),
    (1.25, "spise vysoka"),
    (99, "velmi vysoka"),
]


# ---------------------------------------------------------------- nacteni

class Panel:
    """Panel + z-standardizace psychologickych sloupcu podle samotneho panelu.

    Standardizuje se interne, takze je jedno, jestli jsou v CSV z-skore
    nebo hrube skaly.
    """

    def __init__(self, df: pd.DataFrame, min_vek: int = 18):
        self.source_path = None
        if min_vek and "vek" in df.columns:
            v = pd.to_numeric(df["vek"], errors="coerce")
            self.vyrazeno_vek = int((v.isna() | (v < min_vek)).sum())
            df = df[v.notna() & (v >= min_vek)]
        else:
            self.vyrazeno_vek = 0
        self.min_vek = min_vek
        # 10.12 persona overlay is deliberately separate from the population core.
        # It is joined by stable panel_row_id and skipped safely for custom panels.
        from persona_depth import attach_overlay
        df = attach_overlay(df)
        # 17.9.3: targetable society factors use a non-destructive runtime layer.
        # Base panel bytes remain immutable; derived and approved evidence dimensions
        # are attached by panel_row_id for both preview and real sampling.
        try:
            from audience_dimensions import enrich_panel
            df = enrich_panel(df)
        except Exception:
            # Custom/external panels may not support the population overlay.
            pass
        self.df = df.reset_index(drop=True)
        self.psych_cols = self._detect_psych_cols()
        self.z = self._standardize()
        from styly import prirad_styly
        self.styly = prirad_styly(self.df)
        if "vaha_kalibrovana" not in self.df.columns:
            self.df["vaha_kalibrovana"] = 1.0
        self.df["vaha_kalibrovana"] = (
            pd.to_numeric(self.df["vaha_kalibrovana"], errors="coerce")
            .fillna(0.0).clip(lower=0.0)
        )
        _wcol=_contract_weight("default_current")
        _src=self.df[_wcol] if _wcol in self.df.columns else self.df["vaha_kalibrovana"]
        self.df["_analysis_weight"]=pd.to_numeric(_src,errors="coerce").fillna(0.0).clip(lower=0.0)

    @classmethod
    def load(cls, path: str | Path | None = None, min_vek: int = 18,
             hlasit: bool = True) -> "Panel":
        p = Path(path or resolve_panel_path())
        if not p.exists():
            raise FileNotFoundError(
                f"Panel nenalezen: {p}. Nastav NPC_PANEL nebo predej cestu."
            )
        panel = cls(pd.read_csv(p, low_memory=False, dtype={'occupation_isco08':'string'}), min_vek=min_vek)
        panel.source_path = p.resolve()
        if hlasit and panel.vyrazeno_vek:
            print(f"[panel] vyrazeno {panel.vyrazeno_vek} respondentu pod {min_vek} let "
                  f"nebo bez veku; zbyva {len(panel.df)}")
        if hlasit and VYRAZENE_VRSTVY:
            print(f"[panel] mimo obecny psychologicky blok Povaha: "
                  f"{', '.join(VYRAZENE_VRSTVY)} "
                  f"(dispozice se pouzivaji samostatne tematicky)")
        if hlasit and panel.mrtve_cols:
            print(f"[panel] {len(panel.mrtve_cols)} psychologickych dimenzi je "
                  f"konstantnich a do persony nevstupuje: "
                  f"{', '.join(panel.mrtve_cols)}")
        return panel

    def _detect_psych_cols(self) -> dict[str, list[str]]:
        """Detekce podle prefixu + vyrazeni konstantnich dimenzi.

        Konstantni sloupec by po standardizaci mel z=0 a nikdy by se do persony
        nedostal, ale explicitni vyrazeni je citelnejsi a hlasi se pri nacteni.
        """
        out: dict[str, list[str]] = {}
        self.mrtve_cols: list[str] = []
        for vrstva, prefixy in PREFIXY.items():
            zive = []
            for c in self.df.columns:
                if not (c.startswith(prefixy)
                        and pd.api.types.is_numeric_dtype(self.df[c])):
                    continue
                if self.df[c].dropna().nunique() <= 5:
                    self.mrtve_cols.append(c)
                else:
                    zive.append(c)
            out[vrstva] = zive
        return out

    def _standardize(self) -> pd.DataFrame:
        cols = [c for k, v in self.psych_cols.items()
                if k not in VYRAZENE_VRSTVY for c in v]
        if not cols:
            return pd.DataFrame(index=self.df.index)
        sub = self.df[cols].astype(float)
        sd = sub.std(ddof=0).replace(0, np.nan)
        return ((sub - sub.mean()) / sd).fillna(0.0)


# ---------------------------------------------------------------- vyber vzorku

def sample_representative(
    panel: Panel,
    n: int,
    filtry: dict[str, Any] | None = None,
    seed: int | None = None,
    selection_weights: pd.Series | np.ndarray | None = None,
) -> pd.DataFrame:
    """PPS výběr BEZ náhrady, pravděpodobnost ~ ``vaha_kalibrovana``.

    Stejná syntetická osoba se v jednom datasetu neopakuje. Pokud požadovaný n
    přesahuje dostupný support po filtru, běh explicitně selže místo tichého
    duplikování person.
    """
    df = panel.df
    if filtry:
        # One canonical audience-mask implementation is shared by preview, preflight
        # and real sampling. This prevents the old bug where JSON range filters could
        # preview correctly but select only two exact numeric values during fieldwork.
        from audience import _mask, sanitize_filters
        clean,dropped=sanitize_filters(df,filtry)
        if dropped:
            raise ValueError("Neplatný audience filtr: "+"; ".join(dropped))
        df = df[_mask(df,clean)]
    if len(df) == 0:
        raise ValueError(f"Filtr {filtry} nevybral zadneho respondenta.")

    w = df.get("_analysis_weight",df["vaha_kalibrovana"]).to_numpy(dtype=float)
    if not np.isfinite(w).all() or w.sum() <= 0:
        w = np.ones(len(df), dtype=float)
    if selection_weights is not None:
        if isinstance(selection_weights, pd.Series):
            sw = pd.to_numeric(selection_weights.reindex(df.index), errors="coerce").to_numpy(dtype=float)
        else:
            arr = np.asarray(selection_weights, dtype=float)
            if len(arr) != len(panel.df):
                raise ValueError("selection_weights musi mit delku celeho panelu nebo byt Series indexovana jako panel.df")
            sw = arr[df.index.to_numpy()]
        sw = np.where(np.isfinite(sw), sw, 0.0)
        sw = np.clip(sw, 0.0, None)
        if sw.sum() <= 0:
            raise ValueError("selection_weights po filtru nemaji zadnou kladnou hmotu")
        w = w * sw
    w = np.clip(w, 1e-12, None)
    if n > len(df):
        raise ValueError(
            f"Po filtru je jen {len(df)} unikátních syntetických osob, ale požadováno n={n}. "
            "Produkční sampling je bez náhrady; zmenši n nebo rozšiř support population."
        )
    # 17.7: representative-by-construction selection.  The normal product never
    # asks the user to interpret ESS/relevance warnings.  We draw repeatedly over
    # the chosen population, preserve the best sociodemographic composition and
    # rake analysis weights to the same population margins.  Full diagnostics are
    # stored in dataframe.attrs for audit/final AI review.
    from representative_sampling import draw_representative
    out,audit=draw_representative(df,int(n),seed=seed,weights=w,attempts=40)
    if selection_weights is not None:
        out["_targeting_weight"] = 1.0
    out.attrs["representativeness"] = audit
    return out

    rng = np.random.default_rng(seed)
    if n > len(df):
        raise ValueError(
            f"Po filtru je jen {len(df)} unikátních syntetických osob, ale požadováno n={n}. "
            "Produkční PPS sampling je bez náhrady; zmenši n nebo rozšiř support population."
        )

    # Systematic PPS without replacement. Certainty units are peeled off first;
    # the remainder then has max(weight) < sampling interval, guaranteeing that
    # no cumulative interval can select the same row twice. First-order inclusion
    # probabilities are stored so aggregation can use w_i / pi_i if certainty
    # units occur in a narrow filtered segment.
    rem_idx = df.index.to_numpy().copy()
    rem_w = w.copy()
    selected: list[int] = []
    inclusion: dict[int, float] = {}
    n_rem = int(n)
    while n_rem > 0 and len(rem_idx):
        W = float(rem_w.sum())
        pis = n_rem * rem_w / W
        certainty = pis >= 1.0 - 1e-12
        if not certainty.any():
            break
        for ix in rem_idx[certainty]:
            selected.append(int(ix)); inclusion[int(ix)] = 1.0
        keep = ~certainty
        n_rem -= int(certainty.sum())
        rem_idx, rem_w = rem_idx[keep], rem_w[keep]

    if n_rem > 0:
        W = float(rem_w.sum())
        interval = W / n_rem
        order = rng.permutation(len(rem_idx))
        oi, ow = rem_idx[order], rem_w[order]
        start = float(rng.uniform(0.0, interval))
        thresholds = start + interval * np.arange(n_rem)
        pos = np.searchsorted(np.cumsum(ow), thresholds, side="right")
        picks = oi[pos]
        if len(set(map(int, picks))) != len(picks):
            raise RuntimeError("Systematic PPS invariant failed: duplicate pick; check weights/filter support.")
        for ix in picks:
            loc = int(np.where(rem_idx == ix)[0][0])
            selected.append(int(ix))
            inclusion[int(ix)] = min(1.0, n_rem * float(rem_w[loc]) / W)

    idx = np.asarray(selected, dtype=int)
    if len(idx) != n or len(np.unique(idx)) != n:
        raise RuntimeError("PPS sampling failed to produce n unique rows.")
    idx = idx[rng.permutation(len(idx))]
    out = panel.df.loc[idx].copy()
    out["_zdroj_index"] = idx
    out["_sample_poradi"] = range(n)
    pi = np.asarray([inclusion[int(i)] for i in idx], dtype=float)
    out["_inclusion_prob"] = pi
    aw = out.get("_analysis_weight",out["vaha_kalibrovana"]).to_numpy(dtype=float) / pi
    out["_analysis_weight"] = aw / aw.mean()
    if selection_weights is not None:
        out["_targeting_weight"] = w[[int(np.where(df.index.to_numpy() == i)[0][0]) for i in idx]]
    return out.reset_index(drop=True)


# ---------------------------------------------------------------- persona

def _stupen(z: float) -> str:
    for hranice, popis in STUPNE:
        if z <= hranice:
            return popis
    return "prumerna"


def _hezky(col: str) -> str:
    s = re.sub(r"^TCI_[A-Z]{2}_", "", col)          # TCI_HA_Vyhybani -> Vyhybani
    s = re.sub(r"^(H|E|X|A|C|O|TCI|SCHWARTZ|Air|Earth|Fire|Water|spokojenost)_", "", s)
    return s.replace("_", " ").strip().lower()


# Rys -> temata, kde se ma v personě objevit. Kazdy zaznam ma oporu ve studii,
# ne jen intuici. Rozsireno oproti prvni verzi (byla priliš uzka — impulzivita
# a introverze/extraverze si zaslouzi sirsi pokryti, ne jen 1-2 temata).
#
#   Honesty-Humility -> cena/znacka/etika/nakup: nizke H predikuje
#     materialismus, ochotu koupit padelek (Ashton & Lee 2007; Italian J. of
#     Marketing 2023, N=566+501) a je NEJSILNEJSIM prediktorem impulzivniho
#     nakupu spolu s C (Naz et al. 2025, HEXACO N=388: H a C snizuji, E a X
#     zvysuji impulzivni nakup)
#   Svedomitost -> finance/nakup/predplatne/prace: vysoka C predikuje sporeni
#     a financni planovani (Nyhus & Webley) a je nejsilnejsim ochrannym
#     faktorem proti impulzivnimu nakupu (Naz et al. 2025)
#   Emocionalita (HEXACO N.) -> zdravi/finance/politika/vztahy/nakup: vysoka
#     E = vyssi uzkost z rizika, ale i vyssi impulzivita v afektivni slozce
#     nakupu (Naz et al. 2025) a celkove nestabilnejsi nalada
#   Extraverze -> media/socialni_site/online/moda/nakup: predikuje aktivitu
#     na socialnich sitich, mnozstvi socialni interakce online a kognitivni
#     slozku impulzivniho nakupu (Naz et al. 2025)
#   Otevrenost -> technologie/online/znacka/sluzby/media: predikuje ranou
#     adopci novinek (Matzler et al.) a rozmanitost medialni spotreby
#   Privetivost -> sluzby/reklamace/socialni_site/vztahy: vyssi A = mensi
#     sklon ke konfliktu a stiznostem
#
# Prah pro zobrazeni (|z| >= 0,8) je zamerne prisny a nemeni se s poctem
# temat — sirsi pokryti neznamena nizsi latku pro to, kdy se rys ukaze.
# Milieu-popis ke kazde tride — kratky sociologicky ramec "kdo je jako ja /
# jak vnimam svou pozici", ne jen nalepka. Zdroj: popisy tříd v Prokop,
# Buchtík, Tabery, Dvořák, Pilnáček (2019) "Rozděleni svobodou" — 4 kapitaly
# (ekonomicky, socialni, kulturni, lidsky), + ramovani in-group/out-group
# podle Bornschier (2011) a Zollinger (2024): identita se stavi na tom,
# ke komu se clovek citi blizko a od koho se vymezuje.
TRIDA_MILIEU: dict[str, str] = {
    "Zajištěná střední": "stabilní zázemí, cítí se součástí hlavního proudu společnosti",
    "Nastupující kosmopolitní": "mladší, vzdělaní, otevření změnám, identita spíš "
                                "kosmopolitní než lokální",
    "Tradiční pracující": "stabilní, ale bez vzestupu; drží se zavedeného a "
                          "osvědčeného",
    "Třída místních vazeb": "silné vazby na obec a kraj, opatrnost vůči cizímu",
    "Ohrožená": "nejistota o budoucnost, pocit, že ztrácí kontrolu nad svým místem "
               "ve společnosti",
    "Strádající": "finanční tíseň, pocit vyloučení z hlavního proudu společnosti",
}

RYSY_TEMATA: dict[str, list[str]] = {
    "H_Poctivost_pokora": ["cena", "znacka", "nakup", "reklama", "loajalita"],
    "O_Otevrenost": ["technologie", "online", "znacka", "sluzby", "predplatne", "media"],
    "C_Svedomitost": ["finance", "cena", "bydleni", "predplatne", "nakup", "prace"],
    "E_Emocionalita": ["zdravi", "finance", "regulace", "politika", "nakup", "vztahy"],
    "X_Extraverze": ["media", "reklama", "online", "moda", "socialni_site", "nakup"],
    "A_Privetivost": ["sluzby", "loajalita", "reklama", "socialni_site", "vztahy"],
}


def _age_band_label(v: Any) -> str:
    try:
        a=int(float(v))
    except Exception:
        return "věk neuveden"
    for lo,hi in ((18,24),(25,34),(35,44),(45,54),(55,64),(65,74)):
        if lo <= a <= hi: return f"{lo}–{hi} let"
    return "75 a více let" if a >= 75 else "méně než 18 let"


def _income_band_label(v: Any) -> str:
    try: x=float(v)
    except Exception: return "příjem neuveden"
    if x <= 0: return "příjem neuveden"
    if x < 20000: return "do 20 tisíc Kč čistého měsíčně"
    if x < 30000: return "20–30 tisíc Kč čistého měsíčně"
    if x < 45000: return "30–45 tisíc Kč čistého měsíčně"
    if x < 60000: return "45–60 tisíc Kč čistého měsíčně"
    return "60 tisíc Kč a více čistého měsíčně"


def _first_person_persona(lines: list[str], *, max_words: int = 200) -> str:
    """Turn the audited structured profile into a compact first-person prompt.

    The structured fields remain available in the respondent CSV; this is only
    the model-facing representation. Age/income are bands and psychometric
    dimension names are not introduced here.
    """
    vals={}
    rest=[]
    for line in lines:
        if ': ' in line and not line.startswith('  '):
            k,v=line.split(': ',1)
            if k in {'Pohlaví','Věk','Vzdělání','Kraj','Příjmové pásmo','Socioekonomický kontext (odhad)'}:
                vals[k]=v; continue
        rest.append(line.strip())
    subj='Jsem muž' if vals.get('Pohlaví')=='muž' else 'Jsem žena' if vals.get('Pohlaví')=='žena' else 'Jsem člověk'
    bio=[subj]
    if vals.get('Věk'): bio.append(f"ve věku {vals['Věk']}")
    sentence=', '.join(bio)+'.'
    if vals.get('Vzdělání'): sentence+=f" Mám {vals['Vzdělání'].lower()} vzdělání."
    if vals.get('Kraj'): sentence+=f" Žiju v kraji {vals['Kraj']}."
    if vals.get('Příjmové pásmo'): sentence+=f" Můj příjem je zhruba v pásmu {vals['Příjmové pásmo']}."
    if vals.get('Socioekonomický kontext (odhad)'): sentence+=f" Můj modelovaný socioekonomický kontext: {vals['Socioekonomický kontext (odhad)']}."
    mapping={
      'Mediální chování [modelovaná intenzita]:':'Mediální chování — z médií a platforem je pro mě typické:',
      'Nákupní a značkový profil [1–10]:':'Nákupní a značkový profil — při nákupu je pro mě typické:',
      'Co typicky rozhoduje při reakci na značku [1–10; predispozice, ne výsledek konkrétního testu]:':'Když reaguji na značku, obvykle rozhoduje:',
      'Hodnoty a postoje [1–10]:':'V hodnotách a postojích mám sklon k:',
      'Životní/digitální chování [1–10]:':'V běžném a digitálním životě je pro mě typické:',
      'Jak odpovídá v dotaznících:':'Když odpovídám v dotazníku,',
    }
    cleaned=[]
    for x in rest:
        if not x or x=='Komplexní behaviorální profil:' or x.startswith('Poznámka k profilu:'): continue
        for a,b in mapping.items():
            if x.startswith(a): x=b+x[len(a):]; break
        if x.startswith('Povaha:'):
            # Full persona remains experimental; avoid exposing psychometric labels as ontology.
            x='Moje chování v relevantních situacích je vyhraněné takto:'+x.split(':',1)[1]
        cleaned.append(x)
    text=sentence+' '+ ' '.join(cleaned)
    words=text.split()
    if len(words)>max_words:
        # FIX 17.1.1: the old hard word cut truncated mid-sentence (and mid-citation)
        # for ~11 % of calibrated personas, and did so non-randomly: the richer the
        # respondent record, the more of it was lost. Fall back to the last clause
        # boundary so the model never receives a dangling fragment.
        cut=' '.join(words[:max_words])
        floor=int(len(cut)*0.55)
        best=max(cut.rfind('. '), cut.rfind('; '))
        if best>floor: cut=cut[:best]
        text=cut.rstrip(' ,;—-')+'.'
    return text


HEXACO_BEHAVIOR = {
    "H_Poctivost_pokora": ("spíš odmítá obcházet pravidla kvůli vlastní výhodě a méně řeší status", "je citlivější na status a vlastní výhodu; pravidla posuzuje pragmatičtěji"),
    "E_Emocionalita": ("silněji prožívá nejistotu a při zátěži hledá emoční oporu", "v nejistotě zůstává spíš emočně klidný a soběstačný"),
    "X_Extraverze": ("snadno vstupuje do kontaktu, prosazuje se a čerpá energii ze sociálních situací", "je rezervovanější, méně vyhledává sociální pozornost a netlačí se do popředí"),
    "A_Privetivost": ("při konfliktu spíš ustoupí, odpouští a drží hněv pod kontrolou", "k vnímané křivdě se vrací déle a v konfliktu bývá tvrdší"),
    "C_Svedomitost": ("plánuje dopředu, dotahuje úkoly a preferuje řád", "častěji improvizuje a méně lpí na plánu či detailu"),
    "O_Otevrenost": ("vyhledává nové podněty, složitější vysvětlení a neobvyklé možnosti", "preferuje známé, praktické a osvědčené postupy před experimentováním"),
}

def _hexaco_behavioral_anchors(z: pd.Series | None, max_items: int = 3, temata: list[str] | None = None, *, adaptive: bool = False) -> str:
    if z is None or not len(z): return ""
    topics=set(temata or [])
    vals=[]
    for col,(hi,lo) in HEXACO_BEHAVIOR.items():
        if col not in z.index or pd.isna(z[col]): continue
        if adaptive and topics and not (set(RYSY_TEMATA.get(col, [])) & topics):
            continue
        score=float(z[col])
        if abs(score) >= .8: vals.append((abs(score), hi if score>0 else lo))
    vals.sort(reverse=True,key=lambda x:x[0])
    return "; ".join(x[1] for x in vals[:max_items])


def generate_persona_text(
    row: pd.Series,
    z: pd.Series | None = None,
    styly: pd.Series | None = None,
    temata: list[str] | None = None,
    max_rysu: int = 3,
    max_hodnot: int = 3,
    persona_mode: str = RUN_DEFAULTS["persona_mode"],
    allow_own_estimates: bool = RUN_DEFAULTS["allow_own_estimates"],
) -> str:
    """Strukturovany (KLIC: hodnota) profil respondenta pro LLM prompt.

    FORMAT ZMENEN 13.8.2026: puvodni verze skladala vety oddelene strednikem
    do prozaickych odstavcu ("Muz, 32 let; vzdelani: ..."). Literatura
    (Kambhatla et al., "Pay What LLM Wants", arXiv:2508.03262) ukazuje, ze
    strukturovany "survey format" prekonava "storytelling format" — jemne
    deskriptory v prozaicke forme zvysuji delku promptu bez pridane presnosti,
    zatimco strukturovany zapis je citelnejsi a min nachylny k tomu, aby LLM
    smazal drobne rozdily mezi personami do jedne "prumerneho" stylu.

    Zamerne NEuvadi vsech ~30 psychologickych skore — jen nejvyhrannenejsi
    rysy. Duvod: pri vypisu vseho model zprumeruje a persony se sblizi.
    """
    if persona_mode not in {"full", "core", "demographics", "none", "calibrated"}:
        raise ValueError("persona_mode musi byt full | core | demographics | none | calibrated")
    requested_persona_mode = persona_mode
    adaptive_persona = requested_persona_mode == "calibrated"
    if persona_mode == "calibrated":
        from persona_calibration import resolve_effective_mode
        persona_mode, _persona_calibration = resolve_effective_mode("calibrated", temata)
    if persona_mode == "none":
        return "Bez individuálního profilu. Odpověz jako obecný respondent, bez přidaných osobních údajů."
    zaklad: list[tuple[str, str]] = []
    pohl = str(row.get("pohlavi", "")).strip().lower()
    vek = row.get("vek")
    zaklad.append(("Pohlaví", "muž" if pohl.startswith("mu") else "žena" if pohl else "neuvedeno"))
    
    if pd.notna(vek):
        try: zaklad.append(("Věk", f"{int(float(vek))} let"))
        except Exception: zaklad.append(("Věk", _age_band_label(vek)))
    else:
        zaklad.append(("Věk", "neuvedeno"))
    for k, popis in [("vzdelani", "Vzdělání"), ("kraj", "Kraj")]:
        v = row.get(k)
        if pd.notna(v) and str(v).strip():
            zaklad.append((popis, str(v)))

    if persona_mode == "demographics":
        return _first_person_persona([f"{k}: {v}" for k, v in zaklad])

    # v15.2: socioekonomický základ se bere z jednoho koherentního core donora.
    # Specialistické bloky jej nikdy nepřepisují. Preferujeme měřený osobní příjem
    # z nového core, starý název držíme jen jako kompatibilní fallback.
    prijem = row.get("prijem_osobni_mesicni", row.get("prijem_cisty_mesicni"))
    try:
        ma_prijem = pd.notna(prijem) and float(prijem or 0) > 0
    except Exception:
        ma_prijem = False
    if ma_prijem:
        _income_def=str(row.get("prijem_definice") or "")
        _income_label="Pracovní výdělek" if "work_earnings" in _income_def else "Osobní příjem"
        zaklad.append((_income_label, _income_band_label(prijem)))
    irank=row.get("prijem_pozice_0_1")
    if pd.notna(irank):
        try: zaklad.append(("Relativní příjmová pozice", f"přibližně {int(round(float(irank)*100))}. percentil v harmonizované příjmové pozici"))
        except Exception: pass
    else:
        dec=row.get("prijem_decile")
        if pd.notna(dec):
            try: zaklad.append(("Příjmová pozice (compatibility proxy)", f"{int(float(dec))}/10"))
            except Exception: pass
    _employment_labels={"employed":"pracuje","unemployed":"nezaměstnaný/á","student":"student/ka","retired":"důchodce/kyně","inactive":"ekonomicky neaktivní","inactive_other":"jiná ekonomická neaktivita","unknown":"neuvedeno"}
    _isco_major={1:"manažeři",2:"specialisté",3:"techničtí a odborní pracovníci",4:"úředníci",5:"pracovníci ve službách a prodeji",6:"kvalifikovaní pracovníci v zemědělství",7:"řemeslníci a opraváři",8:"obsluha strojů a zařízení",9:"pomocní a nekvalifikovaní pracovníci",0:"ozbrojené síly"}
    emp=row.get("zamestnani_status")
    if pd.notna(emp) and str(emp).strip():
        zaklad.append(("Pracovní status", _employment_labels.get(str(emp),str(emp))))
    # Objective work status and subjective main status are intentionally separate.
    # A working student remains employed while the education role is still visible.
    if bool(row.get("is_student",False)) and str(emp)=="employed":
        zaklad.append(("Současně", "student/ka"))
    occ=row.get("occupation_major")
    if pd.notna(occ):
        try:
            ol=_isco_major.get(int(float(occ)),f"ISCO {int(float(occ))}")
            zaklad.append(("Aktuální profesní skupina" if str(emp)=="employed" else "Poslední/uváděná profesní skupina",ol))
        except Exception: pass
    hh=row.get("velikost_domacnosti")
    if pd.notna(hh):
        try: zaklad.append(("Velikost domácnosti", f"{int(float(hh))} osoba/y"))
        except Exception: pass
    ch=row.get("pocet_deti_celkem")
    if pd.notna(ch):
        try: zaklad.append(("Rodičovství", f"uvádí {int(float(ch))} dítě/dětí celkem; nemusí žít ve stejné domácnosti"))
        except Exception: pass
    cohab=row.get("partner_cohabiting")
    hasp=row.get("has_partner")
    try:
        if pd.notna(hasp) and int(float(hasp))==0:
            zaklad.append(("Partnerský status v core datech", "nemá stálého partnera/partnerku"))
        elif pd.notna(hasp) and int(float(hasp))==1 and pd.notna(cohab) and int(float(cohab))==0:
            zaklad.append(("Partnerský status v core datech", "má stálého partnera/partnerku, ale nežijí ve společné domácnosti"))
        elif pd.notna(cohab) and int(float(cohab))==1:
            zaklad.append(("Partnerský status v core datech", "žije s partnerem/manželem či partnerkou/manželkou ve společné domácnosti"))
        elif pd.notna(cohab) and int(float(cohab))==0:
            zaklad.append(("Partnerský status v core datech", "nežije s partnerem ve společné domácnosti; existence partnera mimo domácnost není z tohoto core zdroje jistá"))
    except Exception:
        pass

    # Staré heuristické společenské třídy se do v17 produkční persony
    # nepřenášejí. Pokud je načten legacy panel, zůstávají dostupné jen v
    # neadaptivním diagnostickém režimu.
    trida = row.get("trida_spolecenska")
    if "core_source" not in row.index and (not adaptive_persona) and pd.notna(trida) and str(trida).strip():
        milieu = TRIDA_MILIEU.get(str(trida), "")
        zaklad.append(("Socioekonomický kontext (legacy odhad)", f"{trida}" + (f" — {milieu}" if milieu else "")))

    if temata and ({"zdravi","mentalni_zdravi"} & set(temata)):
        h=row.get("zdravi_sebehodnoceni")
        if pd.notna(h):
            try:
                _hn={1:"výborné",2:"velmi dobré",3:"dobré",4:"uspokojivé",5:"špatné"}
                zaklad.append(("Zdraví v core datech",_hn.get(int(float(h)),str(h))))
            except Exception: pass

    kval = row.get("kraj_kvalita_zivota_poradi")
    if pd.notna(kval):
        zaklad.append(("Kvalita života v kraji", f"{int(kval)}. místo ze 14"))

    # Deep behavioral layer: media/platform use, purchasing/brand behaviour, values
    # and observable lifestyle.  It has its own registry and explicitly labels
    # synthetic-derived fields; it does NOT upgrade external predictive validation.
    from persona_depth import deep_profile_text
    hluboky_profil = deep_profile_text(row, temata, mode=persona_mode, adaptive=adaptive_persona)
    hexaco_kotvy = "" if adaptive_persona else _hexaco_behavioral_anchors(z, max_items=(3 if persona_mode=="full" else 2), temata=temata, adaptive=False)

    rysy = ""
    if persona_mode == "full" and (not adaptive_persona) and z is not None and len(z):
        osobnost = [
            c for c in z.index
            if not c.startswith(("SCHWARTZ_", "spokojenost_") + PREFIXY["elements"])
        ]
        hodnoty = [c for c in z.index if c.startswith("SCHWARTZ_")]
        if osobnost:
            # Tematicky filtr — rys se ukaze jen kdyz (a) je vyhraneny A
            # (b) ma dokumentovanou vazbu na tema teto otazky (RYSY_TEMATA).
            # Bez tematu (temata=None) spadne na puvodni chovani: top rysy
            # bez ohledu na relevanci.
            if temata is not None:
                relevantni = [c for c in osobnost
                             if set(RYSY_TEMATA.get(c, [])) & set(temata)]
                top = sorted(relevantni, key=lambda c: -abs(z[c]))[:max_rysu]
            else:
                # Jen pro explicitni legacy/debug pouziti. Produkcni survey
                # predava vzdy seznam temat; prazdny seznam = core-only.
                top = sorted(osobnost, key=lambda c: -abs(z[c]))[:max_rysu]
            top = [c for c in top if abs(z[c]) >= 0.8]  # jen vyhranene, ne prumerne
            rysy = "; ".join(f"{_hezky(c)}: {_stupen(z[c])}" for c in top)
        # Schwartz je ve VYRAZENE_VRSTVY, takze hodnoty budou obvykle prazdne.
        # Az bude vrstva prepocitana, tahle vetev ji zase zacne pouzivat.
        if len(hodnoty) >= 5:
            th = sorted(hodnoty, key=lambda c: -z[c])[:max_hodnot]
            rysy += "; " + ", ".join(_hezky(c) for c in th)

    postoje = []
    if persona_mode == "full" and (not adaptive_persona) and str(row.get("muze_ovlivnit_obec_urcite", "")).lower() in ("1", "ano", "true"):
        postoje.append("věří, že může ovlivnit dění v obci")
    if persona_mode == "full" and (not adaptive_persona) and str(row.get("muze_se_vyjadrit_urcite", "")).lower() in ("1", "ano", "true"):
        postoje.append("věří, že se může veřejně svobodně vyjádřit")

    if persona_mode == "full" and (not adaptive_persona) and z is not None and len(z) and temata is not None:
        SP_TEMATA = {
            "spokojenost_zivotni_uroven": {"finance", "cena", "bydleni"},
            "spokojenost_ekonomicka_situace_cr": {"finance", "politika", "verejne"},
            "spokojenost_naplnujici_prace": {"prace"},
            "spokojenost_vyvoj_spolecnosti": {"politika", "verejne"},
            "spokojenost_volny_cas": {"volny_cas", "sport"},
            "spokojenost_vztahy_rodina_pratele": {"vztahy"},
            "spokojenost_zdravi": {"zdravi"},
        }
        spok = [c for c in z.index if c.startswith("spokojenost_")
                and SP_TEMATA.get(c, set()) & set(temata)]
        # Pracovni spokojenost je denominator-sensitive a v12 nema explicitni
        # employment status, proto ji zatim nevystavujeme.
        if "spokojenost_naplnujici_prace" in spok:
            spok.remove("spokojenost_naplnujici_prace")
        if spok:
            nej = max(spok, key=lambda c: z[c])
            nejh = min(spok, key=lambda c: z[c])
            if z[nej] > 0.4:
                postoje.append(f"oproti průměru populace výrazně spokojenější s {_hezky(nej)}")
            if z[nejh] < -0.4 and nejh != nej:
                postoje.append(f"oproti průměru populace výrazně nespokojenější s {_hezky(nejh)}")

    # Zivotni trajektorie — pravidlove slozena z realnych dat (biografie.py),
    # ne volne generovana LLM (Özkan 2026/CoMPosT: volny backstory u silnych
    # modelu skodi presnosti).
    from biografie import sestav_trajektorii
    trajektorie = sestav_trajektorii(row, temata) if persona_mode == "full" and not adaptive_persona else ""

    fakta, disp = "", ""
    if (adaptive_persona or persona_mode == "full") and any(str(k).startswith(("D_", "F_")) for k in row.index):
        from dispozice import popis_dispozic, popis_faktu
        # Topic-relevant F_* household facts are safe to keep in production; the
        # legacy latent prose is redundant with the v15.2 evidence-aware retriever.
        fakta = popis_faktu(row, temata)
        if not adaptive_persona:
            disp = popis_dispozic(row, temata, allow_own_estimates=allow_own_estimates)

    styl_text = ""
    if persona_mode == "full" and (not adaptive_persona) and styly is not None:
        from styly import popis_stylu
        styl_text = popis_stylu(styly)

    # --- sestaveni strukturovaneho bloku KLIC: hodnota
    radky = [f"{k}: {v}" for k, v in zaklad]
    # v15 Customer / Special Audience: pass-through of explicitly measured
    # uploaded fields. No extra latent scores are inferred from these values.
    try:
        from audience_profile import audience_facts_text
        audience_facts = audience_facts_text(row)
    except Exception:
        audience_facts = ""
    if audience_facts:
        radky.append(audience_facts)
    if hexaco_kotvy:
        radky.append("HEXACO behaviorální kotvy [dispoziční profil, ne životní fakt]: " + hexaco_kotvy)
    if hluboky_profil:
        radky.append("Komplexní behaviorální profil:")
        radky += [f"  {x}" for x in hluboky_profil.splitlines()]
    _tt=set(temata or [])
    if _tt & {"znacka","kampan","reklama"}:
        try:_brand_ready=int(float(row.get("brand_specific_background_ready",0) or 0))==1
        except Exception:_brand_ready=False
        if not _brand_ready:
            radky.append("Brand-specific background: NEDODÁN — nepředpokládej předchozí znalost, používání ani zkušenost s konkrétní značkou; vyhodnocuj pouze stimulus a obecné predispozice.")

    # Full Simulation Lab (10.14) can attach a topic-specific stochastic overlay.
    # The block is intentionally explicit about its epistemic status so the same
    # runtime can serve evidence-safe studies and bold experimental forecasts
    # without confusing hypothesized joint structure with measured attributes.
    fs_profile = row.get("FS_SIMULATION_PROFILE")
    if pd.notna(fs_profile) and str(fs_profile).strip():
        radky.append("Experimentální simulace pro toto téma [hypotéza, nikoli měření]:")
        radky.append("  " + str(fs_profile).strip())
    if trajektorie:
        radky.append(f"Životní trajektorie: {trajektorie}")
    if fakta:
        radky.append(f"Domácnost: {fakta}")
    if disp:
        radky.append("Situace a postoje:")
        radky += [f"  - {p.strip()}" for p in disp.split(";")]
    if rysy:
        radky.append(f"Povaha: {rysy}")
    if postoje:
        radky.append("Další kontext: " + "; ".join(postoje))
    if styl_text:
        radky.append(f"Jak odpovídá v dotaznících: {styl_text}")
    return _first_person_persona(radky, max_words=185 if adaptive_persona else 200)


# ---------------------------------------------------------------- prompty

SYSTEM = """Jsi respondent ve výzkumu. Dostaneš profil konkrétního člověka nebo člena
konkrétní audience. Vžiješ se do něj a odpovíš TAK, JAK BY ODPOVĚDĚL ON —
ne jak je to správně, ne jak by to bylo zdvořilé, ne jak by odpověděl průměrný Čech.

Pravidla:
- Rozhoduj podle příjmu, vzdělání, kraje, věku a povahy toho člověka.
- Část lidí téma nezajímá, spěchají, odpovídají povrchně nebo si protiřečí. To je v pořádku.
- Řádek „Jak odpovídá v dotaznících" je závazný. Popisuje, jak ten člověk vyplňuje
  dotazník, ne co si myslí. Drž se ho i tehdy, když by vyváženější odpověď dávala větší smysl.
- Nevymýšlej si fakta o svém životě nad rámec profilu.
- Pokud je otázka o konkrétní značce, produktu nebo nákupu, používej obecný nákupní profil jen jako predispozici. Pokud profil říká, že brand-specific background není dodán, NESMÍŠ si vymyslet znalost značky, používání, nákupní historii ani předchozí zkušenost.
- Pokud je otázka o médiu nebo platformě, respektuj konkrétní mediální skóre 1–10 a jeho časovou kotvu. Modelovanou minutáž nepovyšuj na pozorovaný fakt a nepřenášej ji automaticky na jiné platformy.
- Hodnotový profil používej hlavně tam, kde je pro otázku věcně relevantní; nesmí přebít explicitní fakta a chování v profilu.
- Pokud profil obsahuje „Experimentální simulace pro toto téma“, ber ji jako plausibilní skrytou dispozici konkrétního člověka v jednom možném světě. Není to jistý fakt ani požadovaný výsledek. Nikdy v odpovědi nezmiňuj interní název simulace, skóre ani to, že jsi syntetický respondent.
- Neodvozuj agregátní výsledek ani to, jak „má populace odpovědět“. Rozhoduj pouze za tohoto konkrétního člověka.
- Vyber PRÁVĚ JEDNU nabízenou možnost.

Odpovíš výhradně JSON objektem, bez markdownu a bez komentáře:
{"volba": <číslo možnosti>, "jistota": <1-5>, "duvod": "<max 12 slov, první osoba>"}"""

UZIVATEL = """PROFIL:
{persona}

OTÁZKA TAZATELE:
{otazka}

MOŽNOSTI:
{moznosti}

Odpověz JSON."""


def build_messages(persona: str, otazka: str, kategorie: list[str]) -> dict:
    moznosti = "\n".join(f"{i+1}. {k}" for i, k in enumerate(kategorie))
    return {
        "system": [
            {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [
            {
                "role": "user",
                "content": UZIVATEL.format(
                    persona=persona, otazka=otazka, moznosti=moznosti
                ),
            },
            {"role": "assistant", "content": '{"volba":'},  # prefill -> uspora + tvar
        ],
    }


def _parse(text: str, n_kat: int) -> dict:
    raw = text if text.strip().startswith("{") else '{"volba":' + text
    try:
        obj = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception:
        m = re.search(r"\d+", raw)
        obj = {"volba": int(m.group(0)) if m else None}
    v = obj.get("volba")
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = None
    if v is not None and not (1 <= v <= n_kat):
        v = None
    return {
        "volba": v,
        "jistota": obj.get("jistota"),
        "duvod": str(obj.get("duvod", ""))[:200],
    }


# ---------------------------------------------------------------- LLM backendy

@dataclass
class Odhad:
    n: int
    model: str
    tok_in: int
    tok_out: int
    usd_sync: float
    usd_batch: float

    def __str__(self) -> str:
        return (
            f"{self.n} respondentu / {self.model}: ~{self.tok_in:,} in + "
            f"{self.tok_out:,} out tokenu => ${self.usd_sync:.2f} sync, "
            f"${self.usd_batch:.2f} batch"
        ).replace(",", " ")


def odhad_nakladu(n: int, delka_persony: int, model: str = DEFAULT_MODEL, provider: str = "anthropic") -> Odhad:
    ti = n * (len(SYSTEM) // 3 + delka_persony // 3 + 80)
    to = n * 40
    model = resolve_provider_model(provider, model)
    ci, co = provider_pricing(provider, model)
    usd = ti / 1e6 * ci + to / 1e6 * co
    return Odhad(n, model, ti, to, usd, usd * 0.5)



def _anthropic_content_to_text(message: Any) -> str:
    """Normalize Anthropic text/tool-use responses to a JSON-compatible string.

    Closed survey questions use a forced client-side tool call so parsing does not
    depend on the model emitting syntactically perfect free-form JSON.
    """
    blocks = getattr(message, "content", None) or []
    for block in blocks:
        if getattr(block, "type", None) == "tool_use":
            return json.dumps(getattr(block, "input", {}) or {}, ensure_ascii=False)
    texts = [getattr(b, "text", "") for b in blocks if getattr(b, "type", None) == "text"]
    return "".join(texts)


def _kw_system_text(kw: dict) -> str:
    raw=kw.get("system") or ""
    if isinstance(raw,str): return raw
    if isinstance(raw,list):
        parts=[]
        for item in raw:
            if isinstance(item,dict): parts.append(str(item.get("text") or item.get("content") or ""))
            else: parts.append(str(item))
        return "\n".join(x for x in parts if x)
    return str(raw)


def _claude_subscription_grouped_responses(
    kw_list: list[dict], model: str, *, max_tokens: int,
    progress: Callable[[int,int],None] | None = None,
    on_result: Callable[[int,dict],None] | None = None,
    event_callback: Callable[[dict],None] | None = None,
    cancel_check: Callable[[],bool] | None = None,
) -> list[dict]:
    """Run exact respondent cases in question-level Claude batches.

    The previous subscription transport launched one Claude CLI process per respondent.
    With one subscription slot that made N=120 wait for 120 serial processes PER QUESTION
    and the UI emitted its first respondent progress only after item 25.  This helper keeps
    the one-question-at-a-time epistemic contract, but sends many independent respondent
    cases in one structured Claude request.  Every case still carries its own persona,
    history and anchors and is journaled separately after a completed batch.

    Failed/oversized batches split recursively.  A successful sub-batch is durable through
    the caller's ``on_result`` journal, so a later failure can resume without replaying it.
    """
    total=len(kw_list)
    if not total:return []
    first=kw_list[0]
    tools=list(first.get('tools') or [])
    if not tools or not isinstance((tools[0] or {}).get('input_schema'),dict):
        raise ValueError('SUBSCRIPTION_GROUPED_REQUIRES_RESPONSE_SCHEMA')
    response_schema=(tools[0] or {}).get('input_schema')
    common_system=_kw_system_text(first)
    questions_per_case=max(1,int(first.get('_npc_questions_per_case') or 1))
    if questions_per_case > 1:
        # One provider call carries at most ~336 respondent-question cells. This keeps
        # both the structured output and Windows stdin below conservative limits while
        # preserving two provider calls for the common n=112 run at block size six.
        default_cases=max(16,_BLOCK_CELL_BUDGET//questions_per_case)
        configured_cases=max(1,int(os.environ.get('NPC_RESPONDENT_BLOCK_CASES',str(default_cases)) or default_cases))
        max_cases=min(default_cases,configured_cases)
        max_chars=max(40000,int(os.environ.get('NPC_RESPONDENT_BLOCK_CHARS','380000') or 380000))
    else:
        max_cases=max(1,int(os.environ.get('NPC_RESPONDENT_BATCH_CASES','96') or 96))
        max_chars=max(20000,int(os.environ.get('NPC_RESPONDENT_BATCH_CHARS','220000') or 220000))
    hard_timeout=max(120,int(os.environ.get('NPC_RESPONDENT_BATCH_TIMEOUT_S','420') or 420))
    question_timeout=max(hard_timeout,int(os.environ.get('NPC_RESPONDENT_QUESTION_TIMEOUT_S','1800') or 1800))
    question_started=time.monotonic()

    # Build context-safe chunks.  We count characters conservatively; the actual token
    # count is lower, but keeping a large safety margin protects long history/persona cases.
    chunks=[];cur=[];chars=0
    for idx,kw in enumerate(kw_list):
        prompt=str(((kw.get('messages') or [{}])[0] or {}).get('content') or '')
        cost=len(prompt)+120
        if cur and (len(cur)>=max_cases or chars+cost>max_chars):
            chunks.append(cur);cur=[];chars=0
        cur.append(idx);chars+=cost
    if cur:chunks.append(cur)
    out=[None]*total;done=0;initial_batches=len(chunks)

    unit=("stejnému krátkému bloku otázek" if questions_per_case>1 else "STEJNÉ aktuální otázce")
    instruction=(common_system+"\n\nBATCH EXECUTION CONTRACT:\n"
      f"Níže dostaneš více NEZÁVISLÝCH respondentních případů ke {unit}. "
      "Každý case vyhodnoť pouze z jeho vlastního profilu, historie a kotev. Případy mezi sebou "
      "neporovnávej, neodvozuj z nich populační distribuci a nepřenášej informace mezi case_id. "
      "Vrať přesně jednu response pro každý case_id ve vstupním pořadí.")

    def emit(payload):
        if event_callback is not None:
            try:event_callback(payload)
            except Exception:pass

    max_split_depth=max(0,min(6,int(os.environ.get('NPC_RESPONDENT_MAX_SPLIT_DEPTH','3') or 3)))

    def split_safe(exc:BaseException,indices:list[int],depth:int)->bool:
        """Split only when a smaller payload can plausibly fix the failure.

        Before 17.9.9 any unclassified error split the batch 96->48->...->1 with no depth
        cap, so a single dropped connection or auth hiccup turned into dozens of paid
        provider calls.  Quota and Windows temp locks are already handled by the caller;
        everything else must prove it is a size/shape problem to earn a retry.
        """
        if len(indices)<4 or depth>=max_split_depth:
            return False
        low=str(exc or '').lower()
        never_split=(
            'winerror 32','npc_claude_code_','subscription_provider_limit',
            'individual spend limit','session limit resets','usage limit','usage cap',
            'out_of_credits','authentication','not authenticated','permission','forbidden',
            'subscription_provider_busy','connection reset','connection aborted','broken pipe',
        )
        if any(x in low for x in never_split):
            return False
        return (
            isinstance(exc,TimeoutError)
            or any(x in low for x in (
                'subscription_provider_timeout','respondent_batch_incomplete',
                'respondent_batch_missing_responses','input_too_large',
                'too large','context length','max_turns','error_max_turns',
            ))
        )

    def run_chunk(indices:list[int],label:str,depth:int=0):
        nonlocal done
        if cancel_check is not None and bool(cancel_check()): raise RuntimeError('JOB_CANCELLED')
        elapsed=time.monotonic()-question_started
        if elapsed>question_timeout:
            raise RuntimeError(f'RESPONDENT_QUESTION_WATCHDOG_TIMEOUT completed={done}/{total} elapsed_s={int(elapsed)} limit_s={question_timeout}')
        cases=[]
        for idx in indices:
            kw=kw_list[idx];prompt=str(((kw.get('messages') or [{}])[0] or {}).get('content') or '')
            cases.append({'case_id':str(idx),'prompt':prompt})
        schema={'type':'object','properties':{
            'responses':{'type':'array','minItems':len(indices),'maxItems':len(indices),'items':{
                'type':'object','properties':{'case_id':{'type':'string'},'response':response_schema},
                'required':['case_id','response'],'additionalProperties':False}}
            },'required':['responses'],'additionalProperties':False}
        emit({'phase':'respondent_batch_start','batch':label,'batch_cases':len(indices),'batch_depth':depth,
              'completed_respondents':done,'total_respondents':total,'initial_batches':initial_batches,'batch_timeout_seconds':hard_timeout,'question_timeout_seconds':question_timeout})
        # Estimate output budget by case count. Closed questions are tiny; open text is
        # bounded by the original per-case max_tokens. Keep a safe global ceiling.
        # A six-question block emits roughly six times the JSON of a single question, so
        # the flat 24k ceiling truncated it and forced a paid resume.
        output_ceiling=32000 if questions_per_case>1 else 24000
        batch_max_tokens=max(2500,min(output_ceiling,len(indices)*(max(32,int(max_tokens))+24)))
        timeout_s=min(600,max(180,min(hard_timeout,150+len(indices)*2+max(0,questions_per_case-1)*30)))
        try:
            from ai_router import call_structured
            wait_stop=threading.Event();wait_started=time.monotonic()
            def _wait_heartbeat():
                while not wait_stop.wait(12):
                    emit({'phase':'respondent_batch_heartbeat','batch':label,'batch_cases':len(indices),'batch_depth':depth,
                          'completed_respondents':done,'total_respondents':total,'elapsed_seconds':int(time.monotonic()-wait_started),
                          'question_elapsed_seconds':int(time.monotonic()-question_started),'timeout_seconds':timeout_s})
            wait_thread=threading.Thread(target=_wait_heartbeat,daemon=True);wait_thread.start()
            try:
                rr=call_structured(system=instruction,messages=[{'role':'user','content':json.dumps({'cases':cases},ensure_ascii=False)}],
                    schema=schema,schema_name='npc_respondent_batch',anthropic_model=model,max_tokens=batch_max_tokens,
                    prefer='claude_code_subscription',allow_fallback=False,timeout=timeout_s)
            finally:
                wait_stop.set();wait_thread.join(timeout=1)
            data=rr.get('data') or {}; rows=data.get('responses') if isinstance(data,dict) else None
            if not isinstance(rows,list): raise RuntimeError('RESPONDENT_BATCH_MISSING_RESPONSES')
            mapped={str(x.get('case_id')):x.get('response') for x in rows if isinstance(x,dict)}
            if any(str(i) not in mapped or not isinstance(mapped[str(i)],dict) for i in indices):
                missing=[i for i in indices if str(i) not in mapped or not isinstance(mapped[str(i)],dict)]
                raise RuntimeError('RESPONDENT_BATCH_INCOMPLETE: '+','.join(map(str,missing[:12])))
            tin=int(rr.get('tok_in') or 0);tout=int(rr.get('tok_out') or 0);n=len(indices)
            for pos,idx in enumerate(indices):
                # Allocate aggregate usage without double-counting; exact usage stays on
                # provider telemetry, while legacy respondent summaries still add correctly.
                ai=tin//n+(1 if pos<tin%n else 0);ao=tout//n+(1 if pos<tout%n else 0)
                item={'text':json.dumps(mapped[str(idx)],ensure_ascii=False),'tok_in':ai,'tok_out':ao,'chyba':None,
                      'provider':'claude_code_subscription','model':rr.get('model') or model,'fallback_used':False,
                      'subscription_usage':True,
                      'execution_mode':('grouped_multiquestion_batch_v2' if questions_per_case>1 else 'grouped_question_batch')}
                out[idx]=item
                if on_result is not None:on_result(idx,dict(item))
                done+=1
                if progress is not None:
                    try:progress(done,total)
                    except Exception:pass
            emit({'phase':'respondent_batch_complete','batch':label,'batch_cases':len(indices),'batch_depth':depth,
                  'completed_respondents':done,'total_respondents':total,'provider_model':rr.get('model') or model})
        except Exception as exc:
            from ai_execution_context import is_cancel_exception
            if is_cancel_exception(exc): raise
            # 17.8.8: provider availability is NOT a batch-size problem.
            # A Claude Pro session limit must park the durable workflow instead of
            # recursively hammering 96→48→...→1 against an exhausted subscription.
            try:
                from ai_router import classify_provider_exception
                _provider_kind=classify_provider_exception(exc)
            except Exception:
                _provider_kind='OTHER'
            _low=str(exc or '').lower()
            if _provider_kind=='QUOTA' or any(x in _low for x in ('session limit','usage limit','usage cap','out_of_credits','rate_limit_event')):
                emit({'phase':'respondent_waiting_credits','batch':label,'batch_cases':len(indices),'batch_depth':depth,
                      'completed_respondents':done,'total_respondents':total,'reason':str(exc)[:900]})
                raise RuntimeError(f'RESPONDENT_WAITING_CREDITS: {exc}') from exc
            if 'winerror 32' in _low or 'právě využívá jiný proces' in _low or 'being used by another process' in _low:
                emit({'phase':'respondent_transport_retry','batch':label,'batch_cases':len(indices),'batch_depth':depth,
                      'completed_respondents':done,'total_respondents':total,'reason':str(exc)[:900]})
                raise RuntimeError(f'RESPONDENT_BATCH_TRANSIENT_WINDOWS_LOCK: {exc}') from exc
            # Only request-shape/context-size/structured-output failures benefit from
            # recursive splitting. Successful sub-batches remain journaled.
            if split_safe(exc,indices,depth):
                emit({'phase':'respondent_batch_split','batch':label,'batch_cases':len(indices),'batch_depth':depth,
                      'completed_respondents':done,'total_respondents':total,'reason':str(exc)[:500]})
                mid=len(indices)//2
                run_chunk(indices[:mid],label+'a',depth+1);run_chunk(indices[mid:],label+'b',depth+1);return
            emit({'phase':'respondent_batch_failed_no_split','batch':label,'batch_cases':len(indices),'batch_depth':depth,
                  'completed_respondents':done,'total_respondents':total,'reason':str(exc)[:500]})
            raise RuntimeError(f'RESPONDENT_BATCH_FAILED batch={label} cases={len(indices)} first_case={indices[0]}: {exc}') from exc

    for bi,indices in enumerate(chunks,1):run_chunk(indices,str(bi),0)
    if any(x is None for x in out): raise RuntimeError('RESPONDENT_BATCH_RESULT_INCOMPLETE')
    return out


def _call_llm(
    kw_list: list[dict],
    model: str = DEFAULT_MODEL,
    mode: str = "sync",
    *,
    max_tokens: int = 120,
    workers: int = 8,
    poll_s: int = 20,
    mock: Callable[[dict, int], str] | None = None,
    progress: Callable[[int, int], None] | None = None,
    on_result: Callable[[int, dict], None] | None = None,
    provider_policy: str = "fallback",
    budget_guard: Any | None = None,
    event_callback: Callable[[dict],None] | None = None,
    cancel_check: Callable[[],bool] | None = None,
) -> list[dict]:
    """LLM runner with an explicit provider contract.

    ``provider_policy='strict_anthropic'`` and ``strict_openai`` are equal production
    contracts: no cross-provider fallback is permitted and the selected-provider
    failure aborts the question/run. ``fallback`` remains legacy/development only.
    """
    total = len(kw_list)
    policy = str(provider_policy or "fallback").lower()
    if policy in {"strict_openai", "openai_only"}:
        strict_provider = "openai"
    elif policy in {"strict_claude_code_subscription", "claude_code_subscription_only"}:
        strict_provider = "claude_code_subscription"
    elif policy in {"strict", "strict_anthropic", "anthropic_only"}:
        strict_provider = "anthropic"
    else:
        strict_provider = None
    strict = strict_provider is not None
    model = resolve_provider_model(strict_provider or "anthropic", model)

    if mode == "dry":
        if mock is None:
            raise ValueError("mode='dry' vyzaduje mock callable.")
        return [{"text": mock(kw, i), "tok_in": 0, "tok_out": 0, "chyba": None,
                 "provider":"dry","fallback_used":False}
                for i, kw in enumerate(kw_list)]

    from provider_auth import create_anthropic_client, has_anthropic_key, has_openai_key, resolve_available_anthropic_model
    anthropic_client=None
    setup_error=None
    if strict_provider not in {"openai","claude_code_subscription"} and has_anthropic_key():
        try:
            anthropic_client=create_anthropic_client(max_retries=3)
            model=resolve_available_anthropic_model(model)
        except Exception as exc:
            setup_error=exc; anthropic_client=None
    if strict_provider == "anthropic" and anthropic_client is None:
        raise RuntimeError("STRICT_LIVE_PROVIDER_FAILED: Anthropic provider není připraven: " + str(setup_error or "chybí API klíč"))
    if strict_provider == "openai" and not has_openai_key():
        raise RuntimeError("STRICT_LIVE_PROVIDER_FAILED: OpenAI provider není připraven: chybí API klíč")
    if strict_provider == "claude_code_subscription":
        from claude_code_provider import health
        h=health()
        if not h.get("ok"): raise RuntimeError("SUBSCRIPTION_PROVIDER_UNAVAILABLE: "+str(h.get("message") or h))

    if strict_provider == "claude_code_subscription" and all((kw.get("tools") or []) for kw in kw_list):
        return _claude_subscription_grouped_responses(kw_list,model,max_tokens=max_tokens,progress=progress,on_result=on_result,event_callback=event_callback,cancel_check=cancel_check)

    if mode == "batch" and strict_provider == "anthropic" and anthropic_client is not None and budget_guard is None:
        try:
            reqs = [{"custom_id": f"r{i}",
                     "params": sanitize_params({"model": model, "max_tokens": max_tokens, **kw})}
                    for i, kw in enumerate(kw_list)]
            davky = [reqs[i:i + 10000] for i in range(0, len(reqs), 10000)]
            vysl: dict[str, dict] = {}
            for davka in davky:
                b = anthropic_client.messages.batches.create(requests=davka)
                while True:
                    st = anthropic_client.messages.batches.retrieve(b.id)
                    if st.processing_status == "ended": break
                    if progress: progress(st.request_counts.succeeded, total)
                    time.sleep(poll_s)
                for r in anthropic_client.messages.batches.results(b.id):
                    if r.result.type == "succeeded":
                        m = r.result.message
                        if budget_guard is not None: budget_guard.charge(m.usage.input_tokens,m.usage.output_tokens)
                        vysl[r.custom_id] = {"text": _anthropic_content_to_text(m), "tok_in": m.usage.input_tokens,
                            "tok_out": m.usage.output_tokens, "chyba": None,"provider":"anthropic_batch","fallback_used":False}
                    else:
                        if strict: raise RuntimeError(f"STRICT_LIVE_PROVIDER_FAILED: Anthropic batch item {r.custom_id}: {r.result.type}")
                        vysl[r.custom_id] = {"text": "", "tok_in": 0, "tok_out": 0,
                            "chyba": r.result.type,"provider":"anthropic_batch","fallback_used":False}
            return [vysl.get(f"r{i}", {"text":"","tok_in":0,"tok_out":0,"chyba":"chybi","provider":"anthropic_batch","fallback_used":False}) for i in range(total)]
        except Exception:
            if strict: raise
            mode="sync"

    from concurrent.futures import ThreadPoolExecutor
    hotovo = [0]

    def jedno(item: tuple[int, dict]) -> dict:
        idx, kw = item
        out = {"text":"","tok_in":0,"tok_out":0,"chyba":None,"provider":"none","fallback_used":False}
        last_error=None; reservation=0.0
        if budget_guard is not None:
            reservation=budget_guard.authorize_call()
        try:
            if strict_provider == "claude_code_subscription":
                try:
                    from ai_router import call_text
                    out=call_text(kw,anthropic_model=model,max_tokens=max_tokens,prefer="claude_code_subscription",allow_fallback=False)
                    if out.get("chyba"): raise RuntimeError(out.get("chyba"))
                except Exception as e:
                    last_error=e;out={"text":"","tok_in":0,"tok_out":0,"chyba":str(e)[:300],"provider":"none","fallback_used":False}
            elif strict_provider == "openai":
                try:
                    from ai_router import call_text
                    out = call_text(kw, anthropic_model=model, openai_model=model, max_tokens=max_tokens, prefer="openai", allow_fallback=False)
                    if out.get("chyba"):
                        raise RuntimeError(out.get("chyba"))
                    if budget_guard is not None:
                        budget_guard.charge(out.get("tok_in",0),out.get("tok_out",0),reservation); reservation=0.0
                except Exception as e:
                    last_error=e
                    out={"text":"","tok_in":0,"tok_out":0,"chyba":str(e)[:300],"provider":"none","fallback_used":False}
            elif anthropic_client is not None:
                for pokus in range(3):
                    try:
                        r = create_message(anthropic_client, model=model, max_tokens=max_tokens, **dict(kw))
                        out = {"text":_anthropic_content_to_text(r),"tok_in":r.usage.input_tokens,
                               "tok_out":r.usage.output_tokens,"chyba":None,"provider":"anthropic","model":model,"fallback_used":False}
                        if budget_guard is not None: budget_guard.charge(r.usage.input_tokens,r.usage.output_tokens,reservation); reservation=0.0
                        break
                    except Exception as e:
                        last_error=e
                        if pokus < 2: time.sleep(1.2 ** pokus + random.random() * .25)
            if strict and out["provider"] == "none":
                raise RuntimeError("STRICT_LIVE_PROVIDER_FAILED: " + str(last_error or f"{strict_provider} call failed"))
            if not strict and (out["provider"]=="none" or out["chyba"]):
                try:
                    from ai_router import call_text
                    fb=call_text(kw,anthropic_model=model,openai_model=model,max_tokens=max_tokens,prefer="openai",allow_fallback=True)
                    out=fb
                    out["fallback_used"]=bool(last_error) or not bool(anthropic_client)
                    if budget_guard is not None and not fb.get("chyba"):
                        budget_guard.charge(fb.get("tok_in",0),fb.get("tok_out",0),reservation); reservation=0.0
                    elif last_error and out.get("chyba"):
                        out["chyba"]=(str(last_error)[:160]+" | fallback: "+str(out["chyba"])[:160])[:320]
                except Exception as e:
                    out["chyba"]=(str(last_error or e))[:300]
            hotovo[0] += 1
            if on_result is not None: on_result(idx, dict(out))
            if progress and (hotovo[0] % 25 == 0 or hotovo[0] == total): progress(hotovo[0], total)
            return out
        finally:
            if reservation and budget_guard is not None: budget_guard.cancel(reservation)

    # NPC AI RUNTIME FIX: pri subscription provideru se strop vlaken odvozuje
    # od poctu skutecnych slotu, jinak vlakna navic jen vyrabeji BUSY.
    if strict_provider == "claude_code_subscription":
        try:
            from claude_code_provider import _slot_count
            _cap = _slot_count()
        except Exception:
            _cap = 1
        max_workers = max(1, min(int(workers or 1), _cap))
    else:
        max_workers = max(1, min(int(workers or 1), 8))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(jedno, list(enumerate(kw_list))))


def _mock_volba(kw: dict, i: int, n_kat: int, seed: int = 0) -> str:
    """Deterministicky nahradni vystup pro mode='dry'.

    Odvozen z hashe promptu -> stabilni, ale nahodne rozlozeny.
    NEMA zadnou vypovidaci hodnotu, slouzi jen k testu potrubi.
    """
    h = hashlib.sha256((str(kw["messages"][0]["content"]) + str(seed)).encode()).hexdigest()
    return json.dumps({"volba": int(h[:8], 16) % n_kat + 1,
                       "jistota": int(h[8], 16) % 5 + 1, "duvod": "[dry-run]"})


# ---------------------------------------------------------------- agregace

def _rozlozeni(s: pd.Series, kategorie: list[str], weights: pd.Series | np.ndarray | None = None) -> dict[str, float]:
    """Weighted distribution; falls back to equal weights for legacy callers."""
    from uncertainty import weighted_distribution
    if weights is None:
        weights = np.ones(len(s), dtype=float)
    return weighted_distribution(s.reset_index(drop=True), kategorie, np.asarray(weights, dtype=float))


def agreguj(detail: pd.DataFrame, kategorie: list[str], min_cell: int = 50) -> dict:
    from uncertainty import clean_weights, kish_effective_n, bootstrap_weighted_distribution, n_guard
    ok = detail[detail["odpoved"].notna()].copy()
    w = clean_weights(ok)
    ci = bootstrap_weighted_distribution(ok["odpoved"], kategorie, w, reps=400, seed=20260816) if len(ok) else {}
    out: dict[str, Any] = {
        "n_dotazano": len(detail),
        "n_platnych": len(ok),
        "n_chyb": int(detail["odpoved"].isna().sum()),
        "effective_n": round(kish_effective_n(w), 1),
        "celkem_pct": {k: float(v["estimate"]) for k, v in ci.items()},
        "intervaly_95": {k: {"low": v["low"], "high": v["high"]} for k, v in ci.items()},
        "prumerna_jistota": round(float(np.average(pd.to_numeric(ok["jistota"], errors="coerce").fillna(0), weights=w)), 2) if len(ok) else None,
        "uncertainty_note": "95% interval = vážený respondentní bootstrap. Nezahrnuje nevalidovanou population-joint chybu.",
    }
    for seg in SEGMENTY:
        if seg not in detail.columns:
            continue
        tab, male = {}, []
        for hod, grp in ok.groupby(seg):
            guard = n_guard(grp, min_cell)
            if not guard["allowed"]:
                tab[str(hod)] = {"suppressed": True, "reason": "málo pozorování", "effective_n": guard["effective_n"]}
                male.append(str(hod)); continue
            gw = clean_weights(grp)
            gci = bootstrap_weighted_distribution(grp["odpoved"], kategorie, gw, reps=250, seed=20260817)
            tab[str(hod)] = {
                "n": len(grp), "effective_n": guard["effective_n"],
                **{k: float(v["estimate"]) for k, v in gci.items()},
                "intervaly_95": {k:{"low":v["low"],"high":v["high"]} for k,v in gci.items()},
            }
        out[f"podle_{seg}"] = tab
        if male:
            out.setdefault("varovani", []).append(f"{seg}: buňky pod effective n<{min_cell} jsou skryté: {', '.join(male)}")
    return out


# ---------------------------------------------------------------- hlavni funkce

def run_pruzkum(
    otazka: str,
    n: int = 500,
    kategorie: list[str] | None = None,
    filtry: dict[str, Any] | None = None,
    *,
    panel: Panel | None = None,
    panel_path: str | Path = PANEL_PATH,
    model: str = DEFAULT_MODEL,
    mode: str = "sync",          # "sync" | "batch" | "dry"
    povolit_nevim: bool = True,
    seed: int | None = None,
    workers: int = 8,
    ulozit: bool = True,
    tichy: bool = False,
    persona_mode: str = "full",
) -> dict:
    """LEGACY jednootazkovy engine. Produkce pouziva dotaznik.run_dotaznik.

    ZMENA 17.1.1: tato cesta ma jiny system prompt, volny JSON s regex fallbackem
    a jiny respondentni kontrakt nez produkcni engine. Ponechana je jen pro
    zpetnou kompatibilitu a dry experimenty; LIVE beh vyzaduje vedomy opt-in pres
    NPC_ALLOW_LEGACY_ENGINE=1, aby klientsky vystup nikdy nevznikl na jinem
    enginu, nez ktery se validuje.
    """
    import os as _os, warnings as _warnings
    _warnings.warn(
        "pipeline.run_pruzkum je legacy engine; pouzij dotaznik.run_dotaznik.",
        DeprecationWarning, stacklevel=2,
    )
    if mode != "dry" and _os.environ.get("NPC_ALLOW_LEGACY_ENGINE") != "1":
        raise RuntimeError(
            "LEGACY_ENGINE_BLOCKED: run_pruzkum nesmi delat LIVE beh. Pouzij "
            "dotaznik.run_dotaznik, nebo vedome nastav NPC_ALLOW_LEGACY_ENGINE=1."
        )
    if not kategorie:
        raise ValueError("Zadej seznam kategorii (uzavrena otazka).")
    kat = list(kategorie) + (["Nevím / neodpovím"] if povolit_nevim else [])

    from holdout_registry import assert_holdout_clean
    assert_holdout_clean()
    panel = panel or Panel.load(panel_path)
    vzorek = sample_representative(panel, n, filtry, seed)

    from dispozice import odvod_temata
    temata = odvod_temata(otazka + " " + " ".join(kat))
    personas = [
        generate_persona_text(row, panel.z.loc[row["_zdroj_index"]],
                              panel.styly.loc[row["_zdroj_index"]], temata,
                              persona_mode=persona_mode)
        for _, row in vzorek.iterrows()
    ]
    payloads = [{"_persona": p, "_otazka": otazka} for p in personas]

    odhad = odhad_nakladu(n, int(np.mean([len(p) for p in personas])), model)
    log = (lambda *a: None) if tichy else print
    log(f"[odhad] {odhad}")

    t0 = time.time()
    prog = None if tichy else (lambda a, b: log(f"[prubeh] {a}/{b}"))
    kw_list = [build_messages(p["_persona"], p["_otazka"], kat) for p in payloads]
    syrove = _call_llm(
        kw_list, model, mode, workers=workers, progress=prog,
        mock=lambda kw, i: _mock_volba(kw, i, len(kat), seed or 0))
    res = []
    for r in syrove:
        d = _parse(r["text"], len(kat)) if not r["chyba"] else {
            "volba": None, "jistota": None, "duvod": f"CHYBA: {r['chyba']}"}
        d["tok_in"], d["tok_out"] = r["tok_in"], r["tok_out"]
        res.append(d)
    trvani = time.time() - t0

    detail = vzorek.copy()
    detail["synthetic_case_id"] = [f"NPC-{i+1:06d}" for i in range(len(detail))]
    detail["persona_text"] = personas
    detail["volba"] = [r["volba"] for r in res]
    detail["odpoved"] = [kat[r["volba"] - 1] if r["volba"] else None for r in res]
    detail["jistota"] = [r.get("jistota") for r in res]
    detail["duvod"] = [r.get("duvod") for r in res]
    detail["provider"] = [r.get("provider", "unknown") for r in syrove]
    detail["provider_fallback"] = [bool(r.get("fallback_used", False)) for r in syrove]

    # 10.12 Czech-language screening layer. This is a linter/screening signal, not
    # a cultural-validity score. It is kept per response so suspicious verbatims can
    # be audited later; dry runs are excluded because their reason is a placeholder.
    if mode != "dry":
        try:
            from npc_tools.npc_lint import zkontroluj
            qc=[]
            for _, rr in detail.iterrows():
                x=zkontroluj(rr.get("duvod", ""), rr.get("kraj"))
                qc.append(x)
            detail["language_qc_score"]=[int(x.get("skore",0) or 0) for x in qc]
            detail["language_qc_flags"]=[" | ".join(str(y[1]) for y in x.get("nalezy",[])) for x in qc]
        except Exception:
            detail["language_qc_score"]=np.nan
            detail["language_qc_flags"]=""

    ci, co = pricing(model)
    ti = sum(r.get("tok_in", 0) for r in res)
    to = sum(r.get("tok_out", 0) for r in res)

    vysledky = agreguj(detail, kat)
    vysledky.update({
        "otazka": otazka, "kategorie": kat, "filtry": filtry or {},
        "model": model, "mode": mode, "seed": seed, "persona_mode": persona_mode,
        "trvani_s": round(trvani, 1),
        "naklady_usd": round(ti / 1e6 * ci + to / 1e6 * co, 4),
        "tokeny": {"in": ti, "out": to},
        "language_qc": {
            "status": "SCREENING_ONLY" if mode != "dry" else "NOT_RUN_DRY",
            "mean_score": (round(float(pd.to_numeric(detail.get("language_qc_score"),errors="coerce").mean()),3) if mode != "dry" and "language_qc_score" in detail else None),
            "flagged_share": (round(float((pd.to_numeric(detail.get("language_qc_score"),errors="coerce").fillna(0)>=4).mean()),4) if mode != "dry" and "language_qc_score" in detail else None),
        },
        "detail": detail,
    })

    if ulozit:
        rid = time.strftime("%Y%m%d-%H%M%S")
        d = RUNS_DIR / rid
        d.mkdir(parents=True, exist_ok=True)
        detail.to_csv(d / "detail.csv", index=False)
        with open(d / "souhrn.json", "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in vysledky.items() if k != "detail"},
                      f, ensure_ascii=False, indent=2)
        vysledky["run_dir"] = str(d)
        log(f"[ulozeno] {d}")

    return vysledky


def tabulka(vysledky: dict) -> str:
    """Vysledky jako text do reportu."""
    r = [f"OTAZKA: {vysledky['otazka']}",
         f"n={vysledky['n_platnych']} platnych z {vysledky['n_dotazano']} "
         f"(+-{vysledky.get('ci95_pp','?')} p.b.)", ""]
    for k, v in sorted(vysledky["celkem_pct"].items(), key=lambda x: -x[1]):
        r.append(f"  {v:5.1f} %  {k}")
    for seg in SEGMENTY:
        tab = vysledky.get(f"podle_{seg}")
        if not tab:
            continue
        r += ["", f"— podle {seg} —"]
        for hod, radek in tab.items():
            top = max((x for x in radek.items() if x[0] != "n"), key=lambda x: x[1])
            r.append(f"  {hod[:28]:30} n={radek['n']:<5} nej: {top[0]} ({top[1]} %)")
    for w in vysledky.get("varovani", []):
        r.append(f"! {w}")
    return "\n".join(r)


if __name__ == "__main__":
    v = run_pruzkum(
        "Kolik byste byl ochoten mesicne priplatit za trideni bioodpadu?",
        n=300,
        kategorie=["do 100 Kc", "100-300 Kc", "nad 300 Kc", "nic"],
        mode="dry", seed=1,
    )
    print(tabulka(v))
