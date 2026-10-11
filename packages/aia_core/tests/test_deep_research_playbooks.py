"""Search playbooks: where each kind of evidence is found, as hints (plan chunk 49).

The hints are rendered from the reputation register into the investigator's prompt. They
name publishers and kinds of documents, never a host, a URL or a query a model could send:
code still decides what leaves. The rendered text is pinned to the prompt version, so a
register change that moves the hints cannot ship under the old version.
"""

from __future__ import annotations

import hashlib
import re

from aia_core.domain.deep_research.agents import (
    INVESTIGATOR_PROMPT_VERSION,
    AgentRole,
    prompt_for,
)
from aia_core.domain.deep_research.playbooks import (
    PLAYBOOKS,
    EvidenceNeed,
    render_playbooks,
)
from aia_core.domain.deep_research.reputation import (
    REPUTATION_REGISTER_V1,
    Publisher,
    RegisterStatus,
    ReputationRegister,
)
from aia_core.domain.deep_research.sources import SourceClass, SourceTier

HINTS = render_playbooks(REPUTATION_REGISTER_V1)
#: The hints of prompt version 3. Moved: bump INVESTIGATOR_PROMPT_VERSION, then re-pin.
HINTS_SHA256 = "3c9e5e342d8d5d37c54d6ffb528aecf5f3a7f11a35276c8556c145ab312ba429"


def test_the_hints_remain_in_the_current_investigator_prompt() -> None:
    assert INVESTIGATOR_PROMPT_VERSION == "5"
    assert hashlib.sha256(HINTS.encode()).hexdigest() == HINTS_SHA256
    assert HINTS in prompt_for(AgentRole.INVESTIGATOR)
    # Only the investigator is given them: no other role's prompt moved.
    for role in AgentRole:
        if role is not AgentRole.INVESTIGATOR:
            assert HINTS not in prompt_for(role)


def test_no_hint_carries_a_host_a_url_or_an_address() -> None:
    hosts = {h for p in REPUTATION_REGISTER_V1.publishers for h in p.hosts}
    for host in hosts:
        assert host not in HINTS, host
    assert re.search(r"https?:|www\.|/|@", HINTS) is None
    assert re.search(r"\w\.(?:cz|eu|org|com|net|int|gov)\b", HINTS) is None


def test_every_kind_of_evidence_has_one_line_and_names_only_register_publishers() -> None:
    lines = HINTS.splitlines()[1:]
    assert len(lines) == len(PLAYBOOKS) == len(EvidenceNeed)
    named = re.findall(r"např\. ([^:]+):", HINTS)
    shown = {
        n.split(" (")[0].strip() for group in named for n in re.split(r", (?=[A-ZČŘŠŽÚ])", group)
    }
    canonical = {p.canonical_name for p in REPUTATION_REGISTER_V1.publishers}
    assert shown and shown <= canonical
    # The statistics office before a newspaper: the press is a kind, named by no title.
    assert "Český statistický úřad (ČSÚ)" in HINTS
    for p in REPUTATION_REGISTER_V1.publishers:
        if p.source_class is SourceClass.MEDIA:
            assert p.canonical_name not in HINTS


def test_a_publisher_whose_name_reads_as_an_address_is_left_out() -> None:
    official, t1 = SourceClass.OFFICIAL_STATISTICS, SourceTier.T1
    register = ReputationRegister(
        version="test",
        status=RegisterStatus.PROPOSED,
        publishers=(
            Publisher("Statistika.example", (), ("statistika.example",), official, t1),
            Publisher("Úřad pro data", ("ÚPD",), ("urad.example",), official, t1),
        ),
    )
    hints = render_playbooks(register)
    assert "Statistika.example" not in hints
    assert "Úřad pro data (ÚPD)" in hints
