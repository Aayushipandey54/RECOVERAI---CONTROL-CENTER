"""Recovery What-If Simulator — read-only estimates; never calls Act/Razorpay/audit."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.agent.decide import decide
from app.agent.diagnose import diagnose
from app.config import Settings, get_settings
from app.models import Case

# In-memory store for GET /api/recovery/simulation/{id} (no DB schema)
_SIMULATION_STORE: dict[str, dict[str, Any]] = {}

STRATEGY_LABELS = {
    "retry_only": "Retry Only",
    "payment_link": "Payment Link",
    "balanced": "Balanced / Recommended",
}


def _score_fraction(case: Case) -> float:
    if case.recovery_score is not None:
        return max(0.0, min(1.0, float(case.recovery_score) / 100.0))
    return 0.45


def _estimate_amount(case: Case) -> int:
    return int(round(case.amount_paise * _score_fraction(case)))


def _simulate_strategy(
    cases: list[Case],
    strategy_id: str,
    settings: Settings,
) -> dict[str, Any]:
    considered = len(cases)
    attempted = 0
    stopped = 0
    escalated = 0
    estimated_recovery = 0
    at_risk_total = sum(c.amount_paise for c in cases)

    for case in cases:
        customer = case.customer
        diagnosis = diagnose(case, customer)
        score = float(case.recovery_score) if case.recovery_score is not None else 45.0
        decision = decide(case, diagnosis, score, settings)

        # Bounds always apply
        if decision.action == "stop":
            stopped += 1
            continue
        if decision.action == "escalate":
            escalated += 1
            continue

        if strategy_id == "retry_only":
            if decision.action != "retry_payment":
                # Not eligible for retry-only path under existing policy
                continue
            attempted += 1
            estimated_recovery += _estimate_amount(case)
        elif strategy_id == "payment_link":
            # Prefer payment-link path for cases that can act (bounds already cleared)
            attempted += 1
            estimated_recovery += _estimate_amount(case)
        else:
            # balanced — use existing decide action (any allowed recovery action)
            attempted += 1
            estimated_recovery += _estimate_amount(case)

    denom = at_risk_total
    rate = round((estimated_recovery / denom) * 100, 1) if denom else 0.0

    return {
        "id": strategy_id,
        "label": STRATEGY_LABELS[strategy_id],
        "estimated_recovery_paise": estimated_recovery,
        "estimated_recovery_rate": rate,
        "cases_considered": considered,
        "attempted_cases": attempted,
        "stopped_cases": stopped,
        "escalated_cases": escalated,
    }


def _recommend(strategies: list[dict[str, Any]]) -> tuple[str, str]:
    if not strategies:
        return "balanced", "No open cases available to simulate."

    by_id = {s["id"]: s for s in strategies}
    best = max(strategies, key=lambda s: (s["estimated_recovery_paise"], s["id"] == "balanced"))
    recommended = best["id"]

    retry = by_id.get("retry_only")
    link = by_id.get("payment_link")
    bal = by_id.get("balanced")

    parts = [
        f"{best['label']} is recommended with estimated recovery "
        f"₹{best['estimated_recovery_paise'] / 100:,.0f} "
        f"({best['estimated_recovery_rate']:.1f}% of considered at-risk value)."
    ]
    if retry and recommended != "retry_only":
        delta = best["estimated_recovery_paise"] - retry["estimated_recovery_paise"]
        if delta > 0:
            parts.append(
                f"It estimates ₹{delta / 100:,.0f} more recovery than Retry Only "
                f"({retry['attempted_cases']} retry-eligible attempts)."
            )
    if link and recommended != "payment_link":
        if best["estimated_recovery_paise"] >= link["estimated_recovery_paise"]:
            parts.append(
                "It matches or exceeds Payment Link estimates while following "
                "existing policy decisions and bounds."
            )
    if bal:
        parts.append(
            f"Existing bounds would stop {best['stopped_cases']} and escalate "
            f"{best['escalated_cases']} cases under this strategy."
        )
    return recommended, " ".join(parts)


def run_simulation(db: Session) -> dict[str, Any]:
    settings = get_settings()
    cases = (
        db.query(Case)
        .options(joinedload(Case.customer))
        .filter(Case.status.in_(["open", "in_progress"]))
        .all()
    )

    strategies = [
        _simulate_strategy(cases, "retry_only", settings),
        _simulate_strategy(cases, "payment_link", settings),
        _simulate_strategy(cases, "balanced", settings),
    ]
    recommended, reason = _recommend(strategies)

    simulation_id = str(uuid.uuid4())
    payload = {
        "simulation_id": simulation_id,
        "is_simulation": True,
        "label": "SIMULATION",
        "strategies": strategies,
        "recommended_strategy": recommended,
        "recommendation_reason": reason,
        "cases_considered": len(cases),
        "at_risk_paise": sum(c.amount_paise for c in cases),
        "can_run_agent": len(cases) > 0,
        "run_note": (
            "Run Recommended Strategy executes the existing bounded agent workflow "
            "(POST /api/agent/run). Simulation never calls Razorpay or writes audit actions."
            if cases
            else "No open/in-progress cases — agent run would process nothing."
        ),
    }
    _SIMULATION_STORE[simulation_id] = payload
    # Keep store bounded
    if len(_SIMULATION_STORE) > 50:
        oldest = next(iter(_SIMULATION_STORE))
        _SIMULATION_STORE.pop(oldest, None)
    return payload


def get_simulation(simulation_id: str) -> dict[str, Any] | None:
    return _SIMULATION_STORE.get(simulation_id)
