"""The study's dimensions as the persona topic allowlist (plan run-recovery-and-truth 5c)."""

from __future__ import annotations

from aia_core.domain.persona_topics import block_topics, dimension_topic, question_topics

QUESTION = ("Třídíte odpad a recyklujete kvůli klimatu?", ("ano", "ne"))


def test_ekologie_stands_for_the_eko_topic() -> None:
    """The owner's mapping of 2026-10-15: the catalogue's ``ekologie`` lets ``eko`` through."""
    assert "eko" in question_topics(QUESTION[0])
    assert dimension_topic("ekologie") == "eko"
    assert "eko" in block_topics([QUESTION], allowlist=["Ekologie"])
    assert block_topics([QUESTION], allowlist=["ekologie"]) == block_topics(
        [QUESTION], allowlist=["eko"]
    )


def test_komunikace_stands_for_the_osobnost_topic() -> None:
    """The owner's mapping of 2026-10-15: communication style is a personality trait."""
    question = ("Jakou máte povahu, když jednáte s lidmi?", ())
    assert "osobnost" in question_topics(question[0])
    assert dimension_topic("komunikace") == "osobnost"
    assert block_topics([question], allowlist=["komunikace"]) == ["osobnost"]


def test_a_dimension_that_names_no_topic_still_lets_nothing_through() -> None:
    """18.6.6's set test, kept for every id that is no topic and no mapped dimension."""
    assert dimension_topic("vek_skupina") is None
    assert block_topics([QUESTION], allowlist=["vek_skupina"]) == []
