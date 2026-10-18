"""The client report's introduction names the parts the report holds, and no other."""

from aia_core.application.client_report import intro_contents


def test_the_introduction_names_maps_only_when_the_report_holds_them() -> None:
    # A run without a tracked set or an approved map has no map chapter: the introduction said
    # "a mapy hodnocených objektů" all the same (cross-review).
    assert intro_contents(questions=True, maps=False) == (
        "Zpráva uvádí návrh studie, kdo odpovídal a výsledky jednotlivých otázek."
    )
    assert intro_contents(questions=True, maps=True) == (
        "Zpráva uvádí návrh studie, kdo odpovídal, výsledky jednotlivých otázek a mapy "
        "hodnocených objektů."
    )
    assert intro_contents(questions=False, maps=False) == (
        "Zpráva uvádí návrh studie a kdo odpovídal."
    )
