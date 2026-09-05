"""Detect → Diagnose → Decide → Act → Verify → Audit orchestration."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.agent.act import execute_action, serialize_raw
from app.agent.decide import decide
from app.agent.diagnose import diagnose
from app.agent.verify import verify
from app.config import Settings, get_settings
from app.ml.recovery_model import recovery_score
from app.models import Action, AgentRun, AuditLog, Case


def _idempotency_key(case_id: str, action: str, attempt: int) -> str:
    return f"{case_id}:{action}:attempt-{attempt}"


def process_case(db: Session, case: Case, settings: Settings) -> dict:
    customer = case.customer
    diagnosis = diagnose(case, customer)
    score = recovery_score(
        amount_paise=case.amount_paise,
        days_overdue=case.days_overdue,
        failure_reason=case.failure_reason,
        prior_attempts=case.attempts,
        customer_success_rate=customer.payment_history_score,
        problem_type=case.problem_type,
    )
    case.recovery_score = score

    decision = decide(case, diagnosis, score, settings)
    case.best_action = decision.action

    next_attempt = case.attempts + 1
    idem = _idempotency_key(case.id, decision.action, next_attempt)

    existing = db.query(Action).filter(Action.idempotency_key == idem).first()
    if existing:
        audit = AuditLog(
            customer_id=customer.id,
            customer_name=customer.name,
            problem=case.problem_type.replace("_", " ").title(),
            ai_decision=decision.reason + " Duplicate blocked.",
            action=decision.action,
            result="Skipped (duplicate)",
            case_id=case.id,
            amount_paise=case.amount_paise,
        )
        db.add(audit)
        return {
            "case_id": case.id,
            "action": decision.action,
            "result": "duplicate_skipped",
            "recovered_paise": 0,
            "escalated": 0,
            "stopped": 0,
        }

    act = execute_action(case, customer, decision.action, settings)
    verified = verify(decision.action, act)

    # Persist action
    db.add(
        Action(
            case_id=case.id,
            action_type=decision.action,
            decision_reason=decision.reason,
            result=verified.result_label,
            amount_paise=case.amount_paise if verified.recovered else 0,
            idempotency_key=idem,
            razorpay_response=serialize_raw(act.raw),
        )
    )

    case.attempts = next_attempt
    if decision.action == "retry_payment":
        case.retry_count = case.retry_count + 1

    refs = {}
    if case.razorpay_refs:
        try:
            refs = json.loads(case.razorpay_refs)
        except json.JSONDecodeError:
            refs = {}
    if act.reference:
        refs[decision.action] = act.reference
        if act.detail:
            refs["last_detail"] = act.detail
    case.razorpay_refs = json.dumps(refs) if refs else case.razorpay_refs
    case.status = verified.case_status
    case.updated_at = datetime.utcnow()

    db.add(
        AuditLog(
            customer_id=customer.id,
            customer_name=customer.name,
            problem=case.problem_type.replace("_", " ").title(),
            ai_decision=decision.reason,
            action=decision.action.replace("_", " ").title(),
            result=verified.result_label,
            case_id=case.id,
            amount_paise=case.amount_paise,
        )
    )

    return {
        "case_id": case.id,
        "action": decision.action,
        "result": verified.result_label,
        "recovered_paise": case.amount_paise if verified.recovered else 0,
        "escalated": 1 if verified.case_status == "escalated" else 0,
        "stopped": 1 if verified.case_status == "stopped" else 0,
        "provider": act.provider,
    }


def run_agent(db: Session, case_id: str | None = None, limit: int = 50) -> dict:
    settings = get_settings()
    run = AgentRun(started_at=datetime.utcnow())
    db.add(run)
    db.flush()

    q = (
        db.query(Case)
        .options(joinedload(Case.customer))
        .filter(Case.status.in_(["open", "in_progress"]))
    )
    if case_id:
        q = q.filter(Case.id == case_id)

    cases = q.all()
    # Priority: higher recovery score first
    cases.sort(key=lambda c: (c.recovery_score or 0), reverse=True)
    cases = cases[:limit]

    totals = {
        "cases_processed": 0,
        "actions_executed": 0,
        "recovered_paise": 0,
        "escalated": 0,
        "stopped": 0,
    }
    details = []

    for case in cases:
        result = process_case(db, case, settings)
        totals["cases_processed"] += 1
        if result.get("result") != "duplicate_skipped":
            totals["actions_executed"] += 1
        totals["recovered_paise"] += result.get("recovered_paise", 0)
        totals["escalated"] += result.get("escalated", 0)
        totals["stopped"] += result.get("stopped", 0)
        details.append(result)

    run.finished_at = datetime.utcnow()
    run.cases_processed = totals["cases_processed"]
    run.actions_executed = totals["actions_executed"]
    run.recovered_paise = totals["recovered_paise"]
    run.escalated = totals["escalated"]
    run.stopped = totals["stopped"]
    run.notes = f"executor={'razorpay' if settings.razorpay_enabled else 'mock'}; processed={len(details)}"
    db.commit()

    return {
        "run_id": run.id,
        **totals,
        "notes": run.notes,
        "details": details,
    }
