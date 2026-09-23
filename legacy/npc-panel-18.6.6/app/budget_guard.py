"""Hard per-run spend cap for paid respondent calls."""
from __future__ import annotations
from dataclasses import dataclass, field
from threading import Lock
from runtime_config import provider_pricing, resolve_provider_model

class BudgetExceeded(RuntimeError):
    pass

@dataclass
class BudgetGuard:
    max_usd: float | None
    model: str
    provider: str = "anthropic"
    reserve_input_tokens: int = 1800
    reserve_output_tokens: int = 160
    spent_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    reserved_usd: float = 0.0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def __post_init__(self):
        self.provider=str(self.provider or "anthropic").strip().lower()
        if self.provider not in {"anthropic","openai","claude_code_subscription"}:
            raise ValueError("provider musí být anthropic | openai | claude_code_subscription")
        self.model=resolve_provider_model(self.provider,self.model)
        if self.max_usd is not None:
            self.max_usd=float(self.max_usd)
            if self.max_usd <= 0: raise ValueError("max_usd musí být > 0")

    def _cost(self, tin:int,tout:int)->float:
        ci,co=provider_pricing(self.provider,self.model)
        return float(tin)/1e6*ci + float(tout)/1e6*co

    @property
    def reserve_usd(self)->float:
        return self._cost(self.reserve_input_tokens,self.reserve_output_tokens)

    def authorize_call(self)->float:
        if self.max_usd is None: return 0.0
        with self._lock:
            reserve=self.reserve_usd
            if self.spent_usd + self.reserved_usd + reserve > self.max_usd + 1e-12:
                raise BudgetExceeded(f"Hard budget cap ${self.max_usd:.4f} reached; no further paid call authorized.")
            self.reserved_usd += reserve
            return reserve

    def charge(self,tin:int,tout:int,reservation:float=0.0)->float:
        with self._lock:
            if reservation: self.reserved_usd=max(0.0,self.reserved_usd-float(reservation))
            self.input_tokens += int(tin or 0); self.output_tokens += int(tout or 0)
            c=self._cost(tin or 0,tout or 0); self.spent_usd += c
            return c

    def cancel(self,reservation:float=0.0)->None:
        if not reservation: return
        with self._lock: self.reserved_usd=max(0.0,self.reserved_usd-float(reservation))

    def snapshot(self)->dict:
        return {"max_usd":self.max_usd,"spent_usd":round(self.spent_usd,6),"provider":self.provider,"model":self.model,
                "remaining_usd":None if self.max_usd is None else round(max(0,self.max_usd-self.spent_usd),6),
                "reserve_per_call_usd":round(self.reserve_usd,6),"reserved_usd":round(self.reserved_usd,6),"token_in":self.input_tokens,"token_out":self.output_tokens}
