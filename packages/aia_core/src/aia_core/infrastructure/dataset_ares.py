"""ARES, the Czech register of economic subjects: one legal entity's public facts as a table.

Registered by nothing yet (plan ``deep-research-web-search.md`` chunk 16; chunk 23 wires
it). The interface, as recorded in ``docs/architecture/deep-research-connectors.md``
(2026-10-06): ARES's REST base is ``https://ares.gov.cz/ekonomicke-subjekty-v-be/rest``
and ``GET /ekonomicke-subjekty/{ico}`` answers one economic subject as JSON. Both are
**unverified** -- the Ministry of Finance's pages were not reachable from where this
was written; the path and the field names come from a client generated from ARES's
OpenAPI document and from other third-party clients -- so this connector reads only
the fields it names and refuses an answer in any other shape (``response_contract``).

**Personal data (plan § 4).** What is read is an allowlist of legal-entity fields
(:data:`ARES_FIELDS`, :data:`ARES_SEAT_FIELDS`, :data:`ARES_REGISTRATION_FIELDS`):
the IČO, the business name, the legal-form code, the registered seat, dates, the VAT
identifier, NACE codes and registration states. Nothing else of the answer is read,
copied, rendered or stored -- not a delivery address, not a file mark, not any
member, owner or other person the answer may carry -- and the raw body is kept only
as its SHA256 and length.

**A sole trader is a person.** ARES holds natural persons who do business (OSVČ);
their "business name" is their own name and their seat may be their home. A subject
is read only when its legal-form code is in :data:`LEGAL_ENTITY_FORMS`, an allowlist
of forms that are legal persons; any other code -- a natural person's form, a form
not yet recorded, or no code at all -- is refused (``not_a_legal_entity``) before a
table exists, with fixed text that carries nothing of the answer. The allowlist is
short on purpose: a legal form missing from it costs a refused query; a natural
person's form wrongly on it would store a person's name.

The table: one row, the subject (``subjekt``), labelled with its IČO; one column per
allowlisted field, values as ARES published them (text; a list of NACE codes joined
in their published order). The licence is not stamped (unverified), so ``licence``
is ``None``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Final

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery
from ..domain.deep_research.grounding import normalise_text
from .dataset_connectors import DatasetResponse, HostScopedClient, build_result, contract_failure
from .web_retrieval import FetchTransport, Resolver, ToolCallFailed

__all__ = [
    "ARES_CONNECTOR_ID",
    "ARES_FIELDS",
    "ARES_HOST",
    "ARES_REGISTRATION_FIELDS",
    "ARES_SEAT_FIELDS",
    "LEGAL_ENTITY_FORMS",
    "AresConnector",
    "valid_ico",
]

ARES_CONNECTOR_ID: Final = "ares-subject-1"
ARES_HOST: Final = "ares.gov.cz"
ARES_REST: Final = f"https://{ARES_HOST}/ekonomicke-subjekty-v-be/rest"
ARES_PUBLISHER: Final = (
    "Administrativní registr ekonomických subjektů (ARES), Ministerstvo financí ČR"
)
#: Unverified (connectors doc): None until the Ministry's terms are read first-hand.
ARES_LICENCE: Final[str | None] = None
#: One subject is a few kilobytes; a much larger answer is not the one this reads.
ARES_MAX_BYTES: Final = 512_000

#: Legal-form codes (ČSÚ/ROS ``PravniForma``) read as legal persons. Every code here is
#: recorded as a legal person ("právnická osoba") in the code list, per the connectors
#: doc (UNVERIFIED: search excerpts of the ROS code list). Anything else is refused.
LEGAL_ENTITY_FORMS: Final[Mapping[str, str]] = {
    "111": "Veřejná obchodní společnost",
    "112": "Společnost s ručením omezeným",
    "113": "Společnost komanditní",
    "121": "Akciová společnost",
    "205": "Družstvo",
    "325": "Organizační složka státu",
    "331": "Příspěvková organizace zřízená územním samosprávným celkem",
    "801": "Obec",
}

#: (column key, column label, ARES field, kind), in column order. ``kind`` is how the
#: field must look: ``str``, ``date`` (an ISO date, optionally with a time), ``codes``
#: (a list of code strings). Nothing outside this allowlist is read.
ARES_FIELDS: Final = (
    ("ico", "IČO", "ico", "str"),
    ("obchodni_jmeno", "Obchodní jméno", "obchodniJmeno", "str"),
    ("pravni_forma", "Právní forma (kód)", "pravniForma", "str"),
    ("datum_vzniku", "Datum vzniku", "datumVzniku", "date"),
    ("datum_zaniku", "Datum zániku", "datumZaniku", "date"),
    ("datum_aktualizace", "Datum aktualizace záznamu", "datumAktualizace", "date"),
    ("dic", "DIČ", "dic", "str"),
    ("cz_nace", "CZ-NACE (kódy)", "czNace", "codes"),
)
#: The registered seat (``sidlo``) of a legal entity: its address, public by law.
ARES_SEAT_FIELDS: Final = (
    ("sidlo_adresa", "Sídlo (adresa)", "textovaAdresa", "str"),
    ("sidlo_obec", "Sídlo (obec)", "nazevObce", "str"),
    ("sidlo_psc", "Sídlo (PSČ)", "psc", "int"),
    ("sidlo_kraj", "Sídlo (kraj)", "nazevKraje", "str"),
    ("sidlo_stat", "Sídlo (kód státu)", "kodStatu", "str"),
)
#: The subject's state in three source registers (``seznamRegistraci``), as codes.
ARES_REGISTRATION_FIELDS: Final = (
    ("stav_vr", "Stav ve veřejném rejstříku", "stavZdrojeVr", "str"),
    ("stav_res", "Stav v RES", "stavZdrojeRes", "str"),
    ("stav_dph", "Stav v registru plátců DPH", "stavZdrojeDph", "str"),
)

_ICO: Final = re.compile(r"^[0-9]{8}$")
_DATE: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9:.+\-Z]{1,30})?$")
_CODE: Final = re.compile(r"^[A-Za-z0-9.]{1,20}$")


def valid_ico(ico: str) -> bool:
    """An IČO: eight digits whose last is the mod-11 check digit of the first seven."""
    if _ICO.fullmatch(ico) is None:
        return False
    total = sum(int(d) * w for d, w in zip(ico[:7], range(8, 1, -1), strict=True))
    return (11 - total % 11) % 10 == int(ico[7])


def _not_sent(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.NOT_SENT)


def _value(doc: Mapping[str, Any], field: str, kind: str) -> str | None:
    """One allowlisted field as text, or None when absent; any other shape is refused."""
    raw = doc.get(field)
    if raw is None:
        return None
    if kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise contract_failure("an ARES subject")
        return str(raw)
    if kind == "codes":
        if not isinstance(raw, list) or not all(
            isinstance(c, str) and _CODE.fullmatch(c) for c in raw
        ):
            raise contract_failure("an ARES subject")
        return ", ".join(raw) if raw else None
    if not isinstance(raw, str):
        raise contract_failure("an ARES subject")
    text = normalise_text(raw)
    if kind == "date" and _DATE.fullmatch(text) is None:
        raise contract_failure("an ARES subject")
    if not text or len(text) > 2000:
        raise contract_failure("an ARES subject")
    return text


def _section(doc: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    section = doc.get(field)
    if section is None:
        return {}
    if not isinstance(section, Mapping):
        raise contract_failure("an ARES subject")
    return section


class AresConnector:
    """One ARES economic subject per query, read only if it is a legal entity."""

    connector_id: Final = ARES_CONNECTOR_ID

    def __init__(
        self,
        *,
        transport: FetchTransport,
        resolver: Resolver,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = HostScopedClient(
            host=ARES_HOST,
            transport=transport,
            resolver=resolver,
            media_types=("application/json",),
            max_bytes=ARES_MAX_BYTES,
        )
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def request_url(self, query: DatasetQuery) -> str:
        """The one URL a query becomes, or a refusal before anything is sent."""
        if query.connector_id != self.connector_id:
            raise _not_sent("the query is for another connector", "connector_mismatch")
        if query.filters or query.period is not None:
            raise _not_sent("a subject record takes no filter or period", "filters_unsupported")
        if not valid_ico(query.dataset_id):
            raise _not_sent("an IČO is eight digits with its check digit", "dataset_id_invalid")
        return f"{ARES_REST}/ekonomicke-subjekty/{query.dataset_id}"

    def query(self, query: DatasetQuery) -> DatasetResponse:
        url = self.request_url(query)
        response = self._client.get(url)
        try:
            doc = json.loads(response.body)
        except (UnicodeDecodeError, ValueError) as exc:
            raise contract_failure("JSON") from exc
        if not isinstance(doc, Mapping):
            raise contract_failure("an ARES subject")
        if _value(doc, "ico", "str") != query.dataset_id:
            raise contract_failure("the subject asked for")
        # Decided before anything else of the answer is read: a natural person's
        # record is refused whole, with text that carries none of it.
        form = _value(doc, "pravniForma", "str")
        if form is None or form not in LEGAL_ENTITY_FORMS:
            raise ToolCallFailed(
                "the subject is not a legal entity this connector reads",
                reason="not_a_legal_entity",
                delivery=Delivery.RESPONDED,
            )
        seat = _section(doc, "sidlo")
        registrations = _section(doc, "seznamRegistraci")
        columns: list[dict[str, str]] = []
        values: list[str | None] = []
        for fields, source in (
            (ARES_FIELDS, doc),
            (ARES_SEAT_FIELDS, seat),
            (ARES_REGISTRATION_FIELDS, registrations),
        ):
            for key, label, field, kind in fields:
                columns.append({"key": key, "label": label})
                values.append(_value(source, field, kind))
        name = values[1]
        if name is None:
            raise contract_failure("an ARES subject")
        result = build_result(
            connector_id=self.connector_id,
            dataset_id=query.dataset_id,
            query=query,
            title=f"Ekonomický subjekt {name}"[:500],
            publisher=ARES_PUBLISHER,
            licence=ARES_LICENCE,
            source_url=url,
            retrieved_at=self._clock(),
            notes=[f"Právní forma {form}: {LEGAL_ENTITY_FORMS[form]} (právnická osoba)."],
            columns=columns,
            rows=[{"key": "subjekt", "label": f"IČO {query.dataset_id}", "values": values}],
        )
        return DatasetResponse(
            result=result,
            raw_sha256=hashlib.sha256(response.body).hexdigest(),
            raw_bytes=len(response.body),
            http_status=response.status,
            provider_request_id=response.provider_request_id,
        )
