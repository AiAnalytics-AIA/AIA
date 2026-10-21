"""A study's wallet, Peněženka (ADR 0028 decision 2, ``lead-orchestration`` LO1).

``GET /studies/{study_id}/wallet``: the open wallet, its bounds, what is charged and what
remains (by the charged runs' ceilings), its raises and charges; ``PUT …/wallet`` sets its cap,
the researcher's act inside the client's wallet ceiling and the study's budget, written to the
approval ledger. Behind ``AIA_STUDY_WALLET_ENABLED`` (off by default): off, ``GET`` says the
wallet is unavailable without reading it and ``PUT`` is ``409 wallet_disabled``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from aia_core.application.wallet import (
    StudyWallets,
    WalletDisabled,
    WalletRaiseRefused,
)
from aia_core.domain.money import RaiseVerdict
from aia_core.domain.scope import Permission, ScopeDenied, StudyContext
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import SessionDep, SettingsDep, StudyScopeDep, require_permission
from ..schemas.projects import ErrorResponse

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Insufficient role, or the study is closed"},
    404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
}

router = APIRouter(prefix="/studies/{study_id}", tags=["wallet"], responses=_RESPONSES)

_DISABLED = "wallet_disabled"


class WalletRaiseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_cap_usd: float
    to_cap_usd: float
    raised_by: str
    created_at: datetime


class WalletChargeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    kind: str
    ceiling_usd: float
    plan_id: str | None
    created_at: datetime


class WalletState(BaseModel):
    """The wallet as the header's second meter reads it. ``wallet`` is ``None`` when the switch
    is off (``available: false``) or when no wallet is set."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    unavailable_reason: Literal["wallet_disabled"] | None = None
    wallet_id: str | None = None
    cap_usd: float | None = None
    #: The cap bounded by the client's wallet ceiling and the study's budget.
    effective_cap_usd: float | None = None
    study_budget_usd: float | None = None
    #: The client's wallet ceiling; null: none set (the study's budget bounds the wallet).
    client_ceiling_usd: float | None = None
    #: The charged runs' cost ceilings, summed: never their settled spend (ADR 0028 decision 2).
    charged_usd: float | None = None
    remaining_usd: float | None = None
    raises: list[WalletRaiseOut] = Field(default_factory=list)
    charges: list[WalletChargeOut] = Field(default_factory=list)


class WalletCapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cap_usd: float = Field(ge=0, allow_inf_nan=False)


def _error(code: int, name: str, message: str, **details: Any) -> HTTPException:
    detail: dict[str, Any] = {"code": name, "message": message}
    if details:
        detail["details"] = details
    return HTTPException(status_code=code, detail=detail)


@contextmanager
def _wallet_errors() -> Iterator[None]:
    try:
        yield
    except WalletDisabled as exc:
        raise _error(409, _DISABLED, "The study wallet is switched off.") from exc
    except WalletRaiseRefused as exc:
        if exc.verdict is RaiseVerdict.ABOVE_CLIENT_CEILING:
            raise _error(
                409,
                exc.reason,
                "The wallet cannot exceed the client's wallet ceiling. An organization owner or "
                "administrator can raise the ceiling.",
                to_cap_usd=exc.to_cap_usd,
                client_ceiling_usd=exc.bound_usd,
                who_can_raise=[role.value for role in exc.who_can_raise],
            ) from exc
        raise _error(
            409,
            exc.reason,
            "The wallet cannot exceed the study's budget.",
            to_cap_usd=exc.to_cap_usd,
            study_budget_usd=exc.bound_usd,
        ) from exc
    except ScopeDenied as exc:
        if exc.reason == "unknown_study":
            raise _error(404, "not_found", "No such study.") from exc
        name = "study_closed" if exc.reason == "study_closed" else "insufficient_role"
        raise _error(
            status.HTTP_403_FORBIDDEN, name, "Your role does not permit that.", reason=exc.reason
        ) from exc


def _state(wallets: StudyWallets) -> WalletState:
    wallet, raises, charges = wallets.read()
    if wallet is None:
        return WalletState(available=True)
    return WalletState(
        available=True,
        wallet_id=wallet.wallet_id,
        cap_usd=wallet.cap_usd,
        effective_cap_usd=wallet.effective_cap_usd,
        study_budget_usd=wallet.study_budget_usd,
        client_ceiling_usd=wallet.client_ceiling_usd,
        charged_usd=wallet.charged_usd,
        remaining_usd=wallet.remaining_usd,
        raises=[
            WalletRaiseOut(
                from_cap_usd=r.from_cap_usd,
                to_cap_usd=r.to_cap_usd,
                raised_by=r.raised_by,
                created_at=r.created_at,
            )
            for r in raises
        ],
        charges=[
            WalletChargeOut(
                run_id=c.run_id,
                kind=c.kind.value,
                ceiling_usd=c.ceiling_usd,
                plan_id=c.plan_id,
                created_at=c.created_at,
            )
            for c in charges
        ],
    )


@router.get("/wallet", response_model=WalletState, summary="The study's wallet (Peněženka)")
def read_wallet(scope: StudyScopeDep, session: SessionDep, settings: SettingsDep) -> WalletState:
    """The open wallet and what remains of it; ``available: false`` when switched off, read
    without touching a wallet row."""
    if not settings.study_wallet_enabled:
        return WalletState(available=False, unavailable_reason=_DISABLED)
    with _wallet_errors():
        return _state(StudyWallets(session, scope, enabled=True))


@router.put(
    "/wallet",
    response_model=WalletState,
    summary="Set the study's wallet cap",
    responses={409: {"model": ErrorResponse, "description": "Off, or above a bound"}},
)
def set_wallet_cap(
    body: WalletCapRequest,
    scope: Annotated[StudyContext, Depends(require_permission(Permission.APPROVE_BUDGET))],
    session: SessionDep,
    settings: SettingsDep,
) -> WalletState:
    """Set the wallet's cap: inside the client's wallet ceiling (409
    ``above_client_ceiling``, naming who can raise it) and the study's budget (409
    ``above_study_budget``). Recorded in the approval ledger (``wallet``)."""
    with _wallet_errors():
        wallets = StudyWallets(session, scope, enabled=settings.study_wallet_enabled)
        wallets.set_cap(body.cap_usd)
        return _state(wallets)
