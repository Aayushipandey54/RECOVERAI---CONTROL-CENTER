"""Diagnose step — map failure signals into structured diagnosis."""

from __future__ import annotations

from dataclasses import dataclass

from app.models import Case, Customer

TEMPORARY_FAILURES = {"insufficient_funds", "network_error", "customer_abandoned"}
HARD_FAILURES = {"bank_decline", "card_expired", "mandate_failed"}


@dataclass
class Diagnosis:
    problem_type: str
    failure_reason: str
    is_temporary: bool
    severity: str
    summary: str
    features: dict


def diagnose(case: Case, customer: Customer) -> Diagnosis:
    is_temp = case.failure_reason in TEMPORARY_FAILURES
    if case.attempts >= 2 or case.failure_reason in HARD_FAILURES:
        severity = "high"
    elif case.days_overdue > 14 or case.amount_paise > 1_000_000:
        severity = "medium"
    else:
        severity = "low"

    summary = (
        f"{case.problem_type.replace('_', ' ')} due to {case.failure_reason.replace('_', ' ')}; "
        f"{'temporary' if is_temp else 'persistent'} signal; "
        f"{case.attempts} prior attempt(s); ₹{case.amount_paise / 100:,.0f}; "
        f"{case.days_overdue}d overdue"
    )
    return Diagnosis(
        problem_type=case.problem_type,
        failure_reason=case.failure_reason,
        is_temporary=is_temp,
        severity=severity,
        summary=summary,
        features={
            "amount_paise": case.amount_paise,
            "days_overdue": case.days_overdue,
            "prior_attempts": case.attempts,
            "customer_success_rate": customer.payment_history_score,
            "risk_tier": customer.risk_tier,
        },
    )
