"""Act step — Razorpay test SDK or deterministic mock executor."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.models import Case, Customer


@dataclass
class ActResult:
    success: bool
    status: str
    provider: str
    reference: str | None
    detail: str
    raw: dict[str, Any]


def _mock_outcome(case: Case, action: str) -> ActResult:
    """Deterministic mock so demo KPIs are stable across runs."""
    key = f"{case.id}:{action}:{case.attempts}"
    digest = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    if action in {"escalate", "stop"}:
        return ActResult(
            success=False,
            status="pending_human" if action == "escalate" else "stopped",
            provider="policy",
            reference=None,
            detail=f"Bounded action {action} recorded",
            raw={"action": action},
        )

    if action == "send_reminder":
        opened = digest % 10 < 7
        return ActResult(
            success=opened,
            status="opened" if opened else "sent",
            provider="mock",
            reference=f"msg_{case.id}_{case.attempts}",
            detail="Personalized reminder dispatched (mock notification)",
            raw={"channel": "email+sms", "opened": opened},
        )

    # Payment-like actions: higher success for temporary failures / later attempts with links
    temp = case.failure_reason in {"insufficient_funds", "network_error", "customer_abandoned"}
    if action == "retry_payment":
        ok = temp and (digest % 10 < 6)
        status = "captured" if ok else "failed"
    elif action == "payment_link":
        ok = digest % 10 < 7
        status = "paid" if ok else "created"
        # "created" still means action executed; recovery only if paid
    elif action == "retry_mandate":
        ok = digest % 10 < 5
        status = "charged" if ok else "mandate_pending"
    else:
        ok = False
        status = "unknown"

    recovered = status in {"captured", "paid", "charged"}
    return ActResult(
        success=recovered,
        status=status,
        provider="mock",
        reference=f"mock_{action}_{case.id}_{case.attempts + 1}",
        detail=f"Mock {action} → {status}",
        raw={"action": action, "status": status, "case_id": case.id},
    )


def _razorpay_client(settings: Settings):
    import razorpay

    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def _razorpay_act(case: Case, customer: Customer, action: str, settings: Settings) -> ActResult:
    client = _razorpay_client(settings)
    amount = case.amount_paise
    notes = {"case_id": case.id, "customer_id": customer.id, "recoverai": "true"}

    try:
        if action == "retry_payment":
            order = client.order.create(
                {
                    "amount": amount,
                    "currency": "INR",
                    "payment_capture": 1,
                    "notes": notes,
                    "receipt": f"retry_{case.id}_{case.attempts + 1}"[:40],
                }
            )
            # Test mode: create payment link as recoverable path after order
            link = client.payment_link.create(
                {
                    "amount": amount,
                    "currency": "INR",
                    "accept_partial": False,
                    "description": f"RecoverAI retry for {case.id}",
                    "customer": {"name": customer.name, "email": customer.email, "contact": customer.phone},
                    "notify": {"sms": False, "email": False},
                    "reminder_enable": False,
                    "notes": notes,
                }
            )
            return ActResult(
                success=False,
                status="order_created",
                provider="razorpay",
                reference=link.get("id") or order.get("id"),
                detail=f"Order {order.get('id')} + payment link {link.get('short_url')}",
                raw={"order": order, "payment_link": link},
            )

        if action == "payment_link":
            link = client.payment_link.create(
                {
                    "amount": amount,
                    "currency": "INR",
                    "accept_partial": False,
                    "description": f"RecoverAI recovery link for {case.id}",
                    "customer": {"name": customer.name, "email": customer.email, "contact": customer.phone},
                    "notify": {"sms": False, "email": False},
                    "reminder_enable": True,
                    "notes": notes,
                }
            )
            return ActResult(
                success=False,
                status="link_created",
                provider="razorpay",
                reference=link.get("id"),
                detail=link.get("short_url") or "payment link created",
                raw=link,
            )

        if action == "retry_mandate":
            # Subscriptions need prior plan IDs in live setups; fall back to payment link in test
            link = client.payment_link.create(
                {
                    "amount": amount,
                    "currency": "INR",
                    "description": f"RecoverAI mandate recovery for {case.id}",
                    "customer": {"name": customer.name, "email": customer.email, "contact": customer.phone},
                    "notify": {"sms": False, "email": False},
                    "notes": {**notes, "intent": "mandate_retry"},
                }
            )
            return ActResult(
                success=False,
                status="mandate_link_created",
                provider="razorpay",
                reference=link.get("id"),
                detail=f"Mandate recovery via link {link.get('short_url')}",
                raw=link,
            )

        if action == "send_reminder":
            return ActResult(
                success=True,
                status="opened",
                provider="razorpay+mock",
                reference=f"reminder_{case.id}",
                detail="Reminder logged (Razorpay notify disabled in demo; mock open=true)",
                raw={"notified": True},
            )

        return ActResult(
            success=False,
            status=action,
            provider="razorpay",
            reference=None,
            detail=f"No Razorpay call for {action}",
            raw={},
        )
    except Exception as exc:  # noqa: BLE001 — surface provider errors into audit
        return ActResult(
            success=False,
            status="error",
            provider="razorpay",
            reference=None,
            detail=str(exc),
            raw={"error": str(exc)},
        )


def execute_action(case: Case, customer: Customer, action: str, settings: Settings | None = None) -> ActResult:
    settings = settings or get_settings()
    if action in {"escalate", "stop"}:
        return _mock_outcome(case, action)
    if settings.razorpay_enabled:
        return _razorpay_act(case, customer, action, settings)
    return _mock_outcome(case, action)


def serialize_raw(raw: dict[str, Any]) -> str:
    return json.dumps(raw, default=str)[:4000]
