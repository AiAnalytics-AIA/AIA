"""The report's own vocabulary, in Czech (pure).

Words the report writes itself — captions, running heads, the evidence key,
fixed notices — never words a model wrote. Czech is the primary report language
(``docs/design/aia-design-system-brief.md:406-407``). A second language adds a
second mapping here; no string is hardcoded in the renderer.
"""

from __future__ import annotations

from typing import Final

CS: Final[dict[str, str]] = {
    # furniture
    "contents": "Obsah",
    "list_of_figures": "Seznam grafů",
    "list_of_tables": "Seznam tabulek",
    "toc_placeholder": "Obsah se doplní při otevření dokumentu (aktualizace polí).",
    "figure": "Graf",
    "table": "Tabulka",
    "appendix": "Příloha",
    "source": "Zdroj",
    "note": "Poznámka",
    "notes": "Poznámky",
    "page": "strana",
    "page_of": "z",
    "revision": "revize",
    "prepared_by": "Zpracovalo",
    "prepared_for": "Pro",
    "date": "Datum",
    "study": "Studie",
    "client": "Klient",
    "classification": "Klasifikace",
    "document_control": "Řízení dokumentu",
    "approved_by": "Schválil(a)",
    "approval": "Schválení",
    "revision_history": "Historie revizí",
    "identifiers": "Identifikátory",
    # report kinds
    "kind_client": "Závěrečná zpráva",
    "kind_final": "Závěrečná zpráva s externí triangulací",
    "kind_internal": "Interní zpráva",
    "kind_documentation": "Dokumentace studie",
    # classification
    "classification_client": "Důvěrné — určeno výhradně klientovi",
    "classification_internal": "Interní — nepředávat klientovi",
    # components
    "decision_answer": "Odpověď pro rozhodnutí",
    "key_finding": "Zjištění",
    "finding_evidence": "Evidence",
    "finding_meaning": "Co to znamená",
    "finding_confidence": "Jistota",
    "recommendation_why": "Proč",
    "recommendation_priority": "Priorita",
    "method_status": "Metodický status",
    "limitation": "Omezení",
    "provisional": "Předběžné — nejde o výsledek",
    "synthetic_quote": "syntetický respondent",
    "indicative": "orientační",
    # evidence
    "evidence_key": "Klíč k síle evidence",
    "evidence_appendix": "Evidenční příloha",
    "grade_measured": "Měřeno",
    "grade_calibrated": "Kalibrované jádro",
    "grade_modelled": "Modelováno",
    "grade_holdout_pending": "Validace čeká",
    "grade_unknown": "Role neznámá",
    "grade_measured_long": "Měřeno společně na téže osobě.",
    "grade_calibrated_long": "Kalibrované jádro populace vůči externím zdrojům.",
    "grade_modelled_long": "Modelováno z behaviorálního prioru — nejde o měření.",
    "grade_holdout_pending_long": "Externí prediktivní validace dosud neproběhla.",
    "grade_unknown_long": "Evidenční role nedorazila nebo ji systém nezná — nečtěte jako měření.",
    "suppressed_rows": "Potlačeno pro nedostatečnou efektivní velikost vzorku",
    "interval": "interval",
    "effective_n": "efektivní n",
    # disclosures (claims.Disclosure)
    "disclosure_SCOPE": "Platí pro sledovanou populaci a období, nikoli obecně.",
    "disclosure_MODELED_VALUE": "Hodnota je modelovaná, nikoli změřená.",
    "disclosure_HISTORICAL": "Údaj je historický; nemusí odpovídat současnému stavu.",
    # method status (validation.METHOD_STATUS_*), printed on the page
    "method_status_pending": (
        "Syntetický a modelovaný výzkum. Externí prediktivní validace proti lidskému "
        "vzorku dosud neproběhla; výsledky nečtěte jako měření na lidské populaci."
    ),
    "method_status_validated": (
        "Syntetický a modelovaný výzkum, externě validovaný proti slepému lidskému vzorku."
    ),
}


def t(key: str) -> str:
    """The Czech string for ``key``. A missing key is a programming error."""
    try:
        return CS[key]
    except KeyError:
        raise KeyError(f"report copy has no key {key!r}") from None
