"""Decide step — policy engine + hard stopping rules (bar requirements)."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.diagnose import Diagnosis
from app.config import Settings
from app.models import Case


@dataclass
class Decision:
    action: str
    reason: str
    allowed: bool
    bound_triggered: str | None = None


def decide(case: Case, diagnosis: Diagnosis, score: float, settings: Settings) -> Decision:
    """
    Policy:
      temporary / insufficient funds → retry_payment
      repeated failures → payment_link
      abandoned checkout → send_reminder
      subscription mandate fail → retry_mandate
      high amount / exhausted attempts → escalate or stop
    """
    attempts = case.attempts
    retries = case.retry_count

    # Bound: max recovery attempts → STOP
    if attempts >= settings.max_recovery_attempts:
        return Decision(
            action="stop",
            reason=(
                f"Diagnose: {diagnosis.failure_reason}. Score={score:.0f}. "
                f"Attempts={attempts}/{settings.max_recovery_attempts}. "
                f"Policy→stop. Bounds: MAX_ATTEMPTS."
            ),
            allowed=False,
            bound_triggered="max_recovery_attempts",
        )

    # Bound: amount requiring human approval
    if case.amount_paise > settings.human_approval_amount_paise:
        return Decision(
            action="escalate",
            reason=(
                f"Diagnose: {diagnosis.failure_reason}. Score={score:.0f}. "
                f"Amount=₹{case.amount_paise / 100:,.0f} > ₹{settings.human_approval_amount_paise / 100:,.0f}. "
                f"Policy→escalate. Bounds: HUMAN_APPROVAL."
            ),
            allowed=False,
            bound_triggered="human_approval_amount",
        )

    # Problem-specific policy
    if case.problem_type == "abandoned_checkout":
        action = "send_reminder"
    elif case.problem_type == "subscription_failed":
        action = "retry_mandate" if diagnosis.failure_reason == "mandate_failed" else "payment_link"
    elif case.problem_type == "overdue_invoice":
        action = "payment_link" if attempts >= 1 else "send_reminder"
    else:
        # payment_failed
        if attempts == 0 and diagnosis.is_temporary and retries < settings.max_automatic_retries:
            action = "retry_payment"
        elif attempts >= 1 or not diagnosis.is_temporary:
            action = "payment_link"
        elif retries >= settings.max_automatic_retries:
            action = "payment_link"
        else:
            action = "retry_payment"

    # Bound: max automatic retries for retry_payment
    if action == "retry_payment" and retries >= settings.max_automatic_retries:
        action = "payment_link"
        bound_note = "MAX_RETRIES→payment_link"
    else:
        bound_note = "OK"

    reason = (
        f"Diagnose: {diagnosis.failure_reason} "
        f"({'temp' if diagnosis.is_temporary else 'hard'}). "
        f"Score={score:.0f}. Attempts={attempts}/{settings.max_recovery_attempts}. "
        f"Policy→{action}. Bounds: {bound_note}."
    )
    return Decision(action=action, reason=reason, allowed=True, bound_triggered=None)
