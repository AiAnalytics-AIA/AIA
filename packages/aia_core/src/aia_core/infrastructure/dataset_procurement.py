"""Czech public procurement: one notice's forms as a table, keyed by its evidence number.

Registered by nothing yet (plan ``deep-research-web-search.md`` chunk 16; chunk 23 wires
it). What is known of the interfaces, as recorded in ``docs/architecture/
deep-research-connectors.md`` (2026-10-06), is thin and **unverified**: the ISVZ
(Informační systém o veřejných zakázkách) publishes open data on public contracts
recorded in the Věstník veřejných zakázek (VVZ) and NEN, and a contract's evidence
number on the VVZ has the form ``Z{yyyy}-{nnnnnn}``. No per-notice read interface
of ISVZ, VVZ or NEN could be read first-hand, so this module does not invent one:

* :class:`NoticeSource` is the seam a source implements -- one notice's records, by
  its evidence number, with the hash of the bytes they were read from. The only
  source today is :class:`RecordedNoticeSource` (a test double; ``make layer_check``
  keeps it out of every composition). A live source is chunk 23's, after the
  interface is read first-hand and one real answer captured.
* :class:`ProcurementNoticeConnector` turns those records into a table, and is where
  personal data stops.

**The record.** A record is one form published for the contract, keyed by the field
names of the ISVZ open-data ``VZ`` element (2016-2024 files, as a third-party
reader of them names them; unverified, and whether the newer JSON open data uses
the same names is not known). A record in another shape is refused.

**Personal data (plan § 4).** Only :data:`NOTICE_FIELDS` is read -- the contract's
identity, its contracting authority (official name and IČO), subject, CPV code,
values and currencies, dates and form state. The contracting authority's contact
person, e-mail and telephone, the persons entitled to attend the opening of tenders,
the free-text description, and every supplier field are never read: a supplier can
be a sole trader, whose name is a person's. The two free-text fields that are read
(the authority's name and the contract's title) are scanned for e-mail addresses
and telephone numbers, which are replaced by :data:`REDACTED` and said in a note.
The raw records are kept only as their SHA256 and length.

The table: one row per form (key: the form's number on the VVZ), labelled with the
notice's evidence number and the form number; the first column is the evidence
number itself, so every cell's quote names the notice it belongs to. Values are as
published, as text; a number published as a JSON float is refused, never
re-formatted. The licence is not stamped (unverified), so ``licence`` is ``None``.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Protocol

from ..domain.ai_contracts import Delivery, canonical_json
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery
from ..domain.deep_research.grounding import normalise_text
from .dataset_connectors import DatasetResponse, build_result, contract_failure
from .web_retrieval import ToolCallFailed

__all__ = [
    "NOTICE_FIELDS",
    "PROCUREMENT_CONNECTOR_ID",
    "REDACTED",
    "NoticeRecords",
    "NoticeSource",
    "ProcurementNoticeConnector",
    "RecordedNoticeSource",
    "valid_notice_id",
]

PROCUREMENT_CONNECTOR_ID: Final = "isvz-notice-1"
PROCUREMENT_PUBLISHER: Final = (
    "Informační systém o veřejných zakázkách (ISVZ), Ministerstvo pro místní rozvoj ČR"
)
#: Unverified (connectors doc): None until the ISVZ open data's terms are read first-hand.
PROCUREMENT_LICENCE: Final[str | None] = None
#: Forms one notice may have before the answer is refused, never cut short.
MAX_NOTICE_FORMS: Final = 50
#: What replaces an e-mail address or telephone number found in a read text field.
REDACTED: Final = "[osobní údaj odstraněn]"

#: (column key, column label, record field, kind), in column order. ``kind``: ``id``
#: (the evidence number), ``text`` (free text, scanned for contact details), ``code``,
#: ``ico``, ``amount`` (digits, a decimal comma or point, spaces), ``date``.
NOTICE_FIELDS: Final = (
    ("notice_id", "Evidenční číslo zakázky ve VVZ", "EvidencniCisloVZnaVVZ", "id"),
    ("form_type", "Druh formuláře", "DruhFormulare", "code"),
    ("valid_form", "Platný formulář", "PlatnyFormular", "code"),
    ("published", "Datum uveřejnění", "DatumUverejneni", "date"),
    ("authority", "Zadavatel (úřední název)", "ZadavatelUredniNazev", "text"),
    ("authority_ico", "IČO zadavatele", "ZadavatelICO", "ico"),
    ("subject", "Název zakázky", "NazevVZ", "text"),
    ("contract_type", "Druh zakázky", "DruhVZ", "code"),
    ("procedure", "Druh řízení", "DruhRizeni", "code"),
    ("cpv_main", "Hlavní kód CPV", "CPVhlavni", "code"),
    ("estimated_value", "Odhadovaná hodnota bez DPH", "OdhadovanaHodnotaVZbezDPH", "amount"),
    ("estimated_currency", "Měna odhadované hodnoty", "OdhadovanaHodnotaVZmena", "code"),
    ("final_value", "Celková konečná hodnota", "CelkovaKonecnaHodnotaVZ", "amount"),
    ("final_currency", "Měna konečné hodnoty", "CelkovaKonecnaHodnotaVZmena", "code"),
    ("tender_deadline", "Lhůta pro doručení nabídek", "LhutaProDoruceniNabidek", "date"),
)
_FORM_FIELD: Final = "CisloFormulareNaVVZ"

_NOTICE_ID: Final = re.compile(r"^Z[0-9]{4}-[0-9]{6}$")
_FORM: Final = re.compile(r"^[A-Za-z0-9_.:+-]{1,60}$")
_CODE: Final = re.compile(r"^[^\x00-\x1f]{1,120}$")
_ICO: Final = re.compile(r"^[0-9]{1,8}$")
_AMOUNT: Final = re.compile(r"^-?[0-9][0-9 ]{0,30}([.,][0-9]{1,6})?$")
_DATE: Final = re.compile(r"^[0-9]{1,4}[0-9.:T /+\-]{0,30}$")
_EMAIL: Final = re.compile(r"[\w.+\-]+@[\w\-]+(\.[\w\-]+)+")
_PHONE: Final = re.compile(r"(\+|00)?(420[ ]?)?[0-9]{3}[ ]?[0-9]{3}[ ]?[0-9]{3}\b")


def valid_notice_id(notice_id: str) -> bool:
    """A contract's evidence number on the VVZ: ``Z{yyyy}-{nnnnnn}``."""
    return _NOTICE_ID.fullmatch(notice_id) is not None


@dataclass(frozen=True, slots=True)
class NoticeRecords:
    """One notice's records, as a source read them, and what its bytes were."""

    records: tuple[Mapping[str, Any], ...]
    #: SHA256 and length of the bytes the records were read from.
    raw_sha256: str
    raw_bytes: int
    http_status: int
    source_url: str
    provider_request_id: str | None


class NoticeSource(Protocol):
    """Where one notice's records come from. Translates; never retries or reroutes."""

    @property
    def retrieval_mode(self) -> RetrievalMode: ...

    def fetch(self, notice_id: str) -> NoticeRecords:
        """One notice's records, or :class:`ToolCallFailed` with its delivery -- nothing else."""
        ...


def _redact(text: str) -> tuple[str, bool]:
    redacted = _PHONE.sub(REDACTED, _EMAIL.sub(REDACTED, text))
    return redacted, redacted != text


def _value(record: Mapping[str, Any], name: str, kind: str) -> tuple[str | None, bool]:
    """One allowlisted field as text (and whether it was redacted); any other shape refused."""
    raw = record.get(name)
    if raw is None:
        return None, False
    if isinstance(raw, int) and not isinstance(raw, bool) and kind in ("ico", "amount", "code"):
        raw = str(raw)
    if not isinstance(raw, str):
        raise contract_failure("a procurement notice record")
    text = normalise_text(raw)
    if not text:
        return None, False
    if len(text) > 2000:
        raise contract_failure("a procurement notice record")
    pattern = {"id": _NOTICE_ID, "code": _CODE, "ico": _ICO, "amount": _AMOUNT, "date": _DATE}
    if kind == "text":
        return _redact(text)
    if pattern[kind].fullmatch(text) is None:
        raise contract_failure("a procurement notice record")
    return text, False


class ProcurementNoticeConnector:
    """One notice per query, by its VVZ evidence number, its forms as rows."""

    connector_id: Final = PROCUREMENT_CONNECTOR_ID

    def __init__(
        self,
        *,
        source: NoticeSource,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._source = source
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return self._source.retrieval_mode

    def query(self, query: DatasetQuery) -> DatasetResponse:
        if query.connector_id != self.connector_id:
            raise ToolCallFailed(
                "the query is for another connector",
                reason="connector_mismatch",
                delivery=Delivery.NOT_SENT,
            )
        if query.filters or query.period is not None:
            raise ToolCallFailed(
                "a notice takes no filter or period",
                reason="filters_unsupported",
                delivery=Delivery.NOT_SENT,
            )
        notice_id = query.dataset_id
        if not valid_notice_id(notice_id):
            raise ToolCallFailed(
                "a notice is asked for by its evidence number, Z<year>-<six digits>",
                reason="dataset_id_invalid",
                delivery=Delivery.NOT_SENT,
            )
        answer = self._source.fetch(notice_id)
        if not answer.records:
            raise ToolCallFailed(
                "the source holds no such notice",
                reason="notice_not_found",
                delivery=Delivery.RESPONDED,
            )
        if len(answer.records) > MAX_NOTICE_FORMS:
            raise ToolCallFailed(
                f"the notice has more than {MAX_NOTICE_FORMS} forms",
                reason="notice_too_large",
                delivery=Delivery.RESPONDED,
            )
        rows: list[dict[str, Any]] = []
        redacted = False
        for record in answer.records:
            if not isinstance(record, Mapping):
                raise contract_failure("a procurement notice record")
            form = record.get(_FORM_FIELD)
            if isinstance(form, int) and not isinstance(form, bool):
                form = str(form)
            if not isinstance(form, str) or _FORM.fullmatch(form) is None:
                raise contract_failure("a procurement notice record")
            values: list[str | None] = []
            for _, _, name, kind in NOTICE_FIELDS:
                value, cut = _value(record, name, kind)
                values.append(value)
                redacted = redacted or cut
            # Every record is a form of the notice asked for, or the answer is not read.
            if values[0] != notice_id:
                raise contract_failure("the notice asked for")
            rows.append({"key": form, "label": f"{notice_id} formulář {form}", "values": values})
        notes = [
            "Kontaktní osoby, e-maily, telefony, popis zakázky a údaje o dodavatelích "
            "se nečtou ani neukládají."
        ]
        if redacted:
            notes.append(f"E-mailové adresy a telefonní čísla v textu jsou nahrazeny: {REDACTED}.")
        result = build_result(
            connector_id=self.connector_id,
            dataset_id=notice_id,
            query=query,
            title=f"Veřejná zakázka {notice_id}",
            publisher=PROCUREMENT_PUBLISHER,
            licence=PROCUREMENT_LICENCE,
            source_url=answer.source_url,
            retrieved_at=self._clock(),
            notes=notes,
            columns=[{"key": key, "label": label} for key, label, _, _ in NOTICE_FIELDS],
            rows=sorted(rows, key=lambda r: str(r["key"])),
        )
        return DatasetResponse(
            result=result,
            raw_sha256=answer.raw_sha256,
            raw_bytes=answer.raw_bytes,
            http_status=answer.http_status,
            provider_request_id=answer.provider_request_id,
        )


# --------------------------------------------------------------------------- #
# Recorded double
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RecordedNoticeSource:
    """Replays captured notices by evidence number; an unrecorded one has no records.

    A notice is ``{"source_url": …, "records": [...], "request_id": …}``, or a failure:
    ``{"fail": "not_sent" | "known" | "uncertain"}``. Its "raw bytes" are the canonical
    JSON of its records.
    """

    notices: Mapping[str, Mapping[str, Any]]
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def fetch(self, notice_id: str) -> NoticeRecords:
        self.calls.append(notice_id)
        notice = self.notices.get(notice_id, {"source_url": "https://isvz.example/", "records": []})
        failure = notice.get("fail")
        if failure == "not_sent":
            raise ToolCallFailed(
                "recorded: refused", reason="refused_recorded", delivery=Delivery.NOT_SENT
            )
        if failure == "uncertain":
            raise ToolCallFailed("recorded: no answer", reason="lost", delivery=Delivery.UNKNOWN)
        if failure == "known":
            raise ToolCallFailed(
                "recorded: provider error", reason="provider_error", delivery=Delivery.RESPONDED
            )
        records: Sequence[Mapping[str, Any]] = tuple(notice.get("records", ()))
        raw = canonical_json(list(records)).encode("utf-8")
        return NoticeRecords(
            records=tuple(records),
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            raw_bytes=len(raw),
            http_status=200,
            source_url=str(notice["source_url"]),
            provider_request_id=notice.get("request_id"),
        )
