"""Datový kontrakt modulu VÝZKUM.

Objekty (fam_/obj_) jsou jediná třída proměnných, která vstupuje do mapy.
Charakteristiky (dem_/att_/beh_/bin_) slouží pouze k profilaci a drill-down.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

from product_policy import tracked_set_limits
import re
import unicodedata

OutputType = Literal["segmentace", "pozicni_mapa", "lovebrand", "test_konceptu"]
CharType = Literal["attitude", "frequency", "binary", "ordinal", "metric", "nps"]


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "x"


@dataclass(frozen=True)
class StudyObject:
    name: str
    slug: str = ""
    label: str = ""
    family: str = ""

    def normalized(self, default_family: str = "") -> "StudyObject":
        return StudyObject(
            self.name,
            self.slug or slugify(self.name),
            self.label or self.name,
            self.family or default_family,
        )


@dataclass(frozen=True)
class Characteristic:
    name: str
    kind: CharType
    text: str
    values: list[str] = field(default_factory=list)
    source_column: str | None = None
    topics: list[str] = field(default_factory=list)
    scale: list[int] = field(default_factory=list)  # optional [min,max], e.g. NPS 0-10

    @property
    def prefix(self) -> str:
        return {
            "attitude": "att_", "frequency": "beh_", "binary": "bin_",
            "ordinal": "dem_", "metric": "dem_", "nps": "att_",
        }[self.kind]

    @property
    def variable(self) -> str:
        return self.prefix + slugify(self.name)


@dataclass
class StudySpec:
    name: str
    research_question: str
    output_type: OutputType
    objects: list[StudyObject | str | dict[str, Any]]
    characteristics: list[Characteristic | dict[str, Any]] = field(default_factory=list)
    object_family: str = ""
    object_question: str = "Jaký je Váš vztah k objektu {object}?"
    object_scale_labels: tuple[str, str] = ("velmi negativní", "velmi pozitivní")
    familiarity_question: str = "Znáte {object}?"
    # None = auto: familiarita se zapíná jen u typů, kde je typicky smysluplná
    # (např. značky / produkty). U médií, emocí, vztahů, atributů apod. je default OFF.
    familiarity_required: bool | None = None
    n: int = 500
    seed: int = 20260814
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        family = str(self.object_family or self.metadata.get("object_family") or "").strip()
        normalized_objects = []
        for o in self.objects:
            if isinstance(o, StudyObject):
                obj = o.normalized(default_family=family)
            elif isinstance(o, dict):
                od=dict(o)
                if not od.get("name") and od.get("label"):
                    od["name"] = od["label"]
                obj = StudyObject(**od).normalized(default_family=family)
            else:
                obj = StudyObject(str(o), family=family).normalized(default_family=family)
            normalized_objects.append(obj)
        self.objects = normalized_objects
        self.object_family = family
        if family:
            self.metadata.setdefault("object_family", family)

        # Sledované objekty mohou být libovolného srovnatelného typu. Familiarita není
        # obecná vlastnost mapy: dává smysl typicky u značek/produktů/konceptů, ale ne
        # automaticky u médií, emocí, vztahových výroků nebo atributů. Explicitní volba
        # výzkumného designu má vždy přednost.
        if self.familiarity_required is None:
            fam_slug = slugify(family)
            # Auto-default familiarity ON for families whose *head type* is normally
            # knowable/recognisable.  The family may be specific (e.g.
            # "značky nealkoholických nápojů"), so exact-string matching is too
            # brittle.  Explicit user/design choice still overrides this heuristic.
            familiarity_tokens = {
                "znacka", "znacky", "brand", "brands",
                "produkt", "produkty", "product", "products",
                "koncept", "koncepty", "concept", "concepts",
            }
            tokens = {t for t in fam_slug.split("_") if t}
            self.familiarity_required = bool(tokens & familiarity_tokens)
        self.metadata.setdefault("familiarity_required", bool(self.familiarity_required))
        self.characteristics = [c if isinstance(c, Characteristic) else Characteristic(**c)
                                for c in self.characteristics]
        self._inject_output_requirements()
        self.validate()


    def _has_characteristic(self, name: str) -> bool:
        target=slugify(name)
        return any(slugify(c.name)==target for c in self.characteristics)

    def _inject_output_requirements(self) -> None:
        """Make output type operational rather than a post-hoc label."""
        if self.output_type == "segmentace":
            if not self._has_characteristic("frekvence_nakupu"):
                self.characteristics.append(Characteristic(
                    "frekvence_nakupu", "frequency",
                    "Jak často nakupujete nebo používáte produkty v této kategorii?",
                    topics=["nakup"]))
            if not self._has_characteristic("cenova_citlivost"):
                self.characteristics.append(Characteristic(
                    "cenova_citlivost", "attitude",
                    "Jak důležitá je pro vás při výběru v této kategorii cena?",
                    topics=["cena", "nakup"]))
        elif self.output_type == "lovebrand":
            focal=str(self.metadata.get("focal_object") or self.objects[0].label)
            battery=[
                ("brand_love_obliba", f"Jak moc máte značku {focal} rád/a?"),
                ("brand_love_blizkost", f"Jak blízká je vám značka {focal}?"),
                ("brand_love_duvera", f"Jak moc značce {focal} důvěřujete?"),
                ("brand_love_preference", f"Jak silně dáváte značce {focal} přednost před alternativami?"),
                ("brand_love_identifikace", f"Jak moc značka {focal} odpovídá tomu, kdo jste nebo chcete být?"),
                ("brand_love_ztrata", f"Jak moc by vám vadilo, kdyby značka {focal} z trhu zmizela?"),
            ]
            for name,text in battery:
                if not self._has_characteristic(name):
                    self.characteristics.append(Characteristic(name,"attitude",text,topics=["znacka"]))
            if not self._has_characteristic("nps"):
                self.characteristics.append(Characteristic(
                    "nps", "nps", f"Jak pravděpodobné je, že byste značku {focal} doporučil/a známému?",
                    topics=["znacka"], scale=[0,10]))
            self.metadata.setdefault("focal_object", focal)
        elif self.output_type == "test_konceptu":
            tested=str(self.metadata.get("test_object") or self.objects[-1].label)
            if not self._has_characteristic("ochota_vyzkouset"):
                self.characteristics.append(Characteristic(
                    "ochota_vyzkouset", "attitude", f"Jak ochotný/á byste byl/a vyzkoušet {tested}?",
                    topics=["nakup"]))
            if not self._has_characteristic("cenovy_prah"):
                bands=list(self.metadata.get("price_bands") or [])
                if not bands:
                    raise ValueError("test_konceptu vyžaduje metadata.price_bands; systém nesmí sám vymýšlet cenová pásma.")
                self.characteristics.append(Characteristic(
                    "cenovy_prah", "ordinal", f"Jaká je nejvyšší cenová úroveň, při které byste {tested} ještě zvažoval/a?",
                    values=[str(x) for x in bands], topics=["cena", "nakup"]))
            self.metadata.setdefault("test_object", tested)

    def scale_domains(self) -> dict[str, tuple[int,int]]:
        domains={}
        for o in self.objects:
            if self.familiarity_required:
                domains[f"fam_{o.slug}"]=(0,1)
            domains[f"obj_{o.slug}"]=(1,10)
        for c in self.characteristics:
            if c.kind in {"attitude","nps"}:
                rng=tuple(c.scale) if len(c.scale)==2 else ((0,10) if c.kind=="nps" else (1,10))
                domains[c.variable]=(int(rng[0]),int(rng[1]))
            elif c.kind=="frequency": domains[c.variable]=(1,5)
            elif c.kind=="binary": domains[c.variable]=(0,1)
        return domains

    def validate(self) -> None:
        if not str(self.research_question).strip():
            raise ValueError("Výzkumná otázka je povinná.")
        if self.output_type not in {"segmentace", "pozicni_mapa", "lovebrand", "test_konceptu"}:
            raise ValueError("Neznámý typ výstupu.")
        hard_min, hard_max, _recommended = tracked_set_limits(self.output_type)
        if len(self.objects) < hard_min:
            if self.output_type == "pozicni_mapa":
                raise ValueError(f"Poziční mapa potřebuje alespoň {hard_min} srovnatelné položky.")
            raise ValueError(f"Sledovaná sada potřebuje alespoň {hard_min} položku.")
        if len(self.objects) > hard_max:
            raise ValueError(f"Sledovaná sada může mít nejvýše {hard_max} položek v jednom běhu; větší sadu rozděl nebo použij vhodnější design.")
        if not self.object_family:
            raise ValueError(
                "object_family je povinné: položky v jedné sledované sadě musí být stejného druhu "
                "(např. 'značky', 'emoce', 'procesy', 'povolání', 'atributy')."
            )
        fam_key = slugify(self.object_family)
        mismatched = [o.label for o in self.objects if slugify(o.family) != fam_key]
        if mismatched:
            raise ValueError(
                "Všechny objekty musí být ze stejného 'hrníčku'. Nesouhlasí object_family u: "
                + ", ".join(mismatched[:5])
            )
        slugs = [o.slug for o in self.objects]
        if len(set(slugs)) != len(slugs):
            raise ValueError("Objekty po slugifikaci nemají unikátní názvy.")
        for c in self.characteristics:
            if c.kind in {"binary", "ordinal"} and not c.values and not c.source_column:
                raise ValueError(f"{c.name}: {c.kind} potřebuje values nebo source_column.")

    def questionnaire(self) -> list[dict[str, Any]]:
        q: list[dict[str, Any]] = []
        for o in self.objects:
            if self.familiarity_required:
                q.append({
                    "id": f"fam_{o.slug}", "text": self.familiarity_question.format(object=o.label),
                    "typ": "vyber", "kategorie": ["Neznám", "Znám"], "povolit_nevim": False,
                    "metadata": {"study_class": "familiarity", "object": o.slug,
                                 "object_family": self.object_family, "map_role": "familiarity"},
                })
            obj_q = {
                "id": f"obj_{o.slug}", "text": self.object_question.format(object=o.label),
                "typ": "skala", "skala": (1, 10),
                "popisky_skaly": tuple(self.object_scale_labels),
                "povolit_nevim": False,
                "metadata": {"study_class": "object", "object": o.slug,
                             "object_family": self.object_family, "map_role": "mapped_item"},
            }
            if self.familiarity_required:
                obj_q["filtr"] = f"fam_{o.slug} == 'Znám'"
            q.append(obj_q)
        for c in self.characteristics:
            if c.source_column:
                continue
            if c.kind in {"attitude", "nps"}:
                rng=tuple(c.scale) if len(c.scale)==2 else ((0,10) if c.kind=="nps" else (1,10))
                q.append({"id": c.variable, "text": c.text, "typ": "skala", "skala": rng,
                          "popisky_skaly": ("nejméně pravděpodobné" if c.kind=="nps" else "nejméně",
                                             "nejvíce pravděpodobné" if c.kind=="nps" else "nejvíce"),
                          "povolit_nevim": False,
                          "topics": c.topics, "metadata": {"study_class": "characteristic", "kind":c.kind}})
            elif c.kind == "frequency":
                q.append({"id": c.variable, "text": c.text, "typ": "skala", "skala": (1, 5),
                          "popisky_skaly": ("nikdy", "velmi často"), "povolit_nevim": False,
                          "topics": c.topics, "metadata": {"study_class": "characteristic"}})
            elif c.kind == "binary":
                q.append({"id": c.variable, "text": c.text, "typ": "vyber", "kategorie": list(c.values),
                          "povolit_nevim": False, "topics": c.topics,
                          "metadata": {"study_class": "characteristic"}})
            elif c.kind == "ordinal":
                q.append({"id": c.variable, "text": c.text, "typ": "vyber", "kategorie": list(c.values),
                          "povolit_nevim": False, "topics": c.topics,
                          "metadata": {"study_class": "characteristic"}})
            elif c.kind == "metric":
                raise ValueError(f"{c.name}: metrická charakteristika se musí dodat jako source_column; "
                                 "LLM free-number elicitation není standardizovaná.")
        return q

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["objects"] = [asdict(o) for o in self.objects]
        d["characteristics"] = [asdict(c) for c in self.characteristics]
        return d
