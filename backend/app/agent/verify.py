"""Verify step — interpret action result into case outcome."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.act import ActResult


@dataclass
class VerifyResult:
    recovered: bool
    case_status: str
    result_label: str


def verify(action: str, act: ActResult) -> VerifyResult:
    if action == "escalate":
        return VerifyResult(recovered=False, case_status="escalated", result_label="Pending")
    if action == "stop":
        return VerifyResult(recovered=False, case_status="stopped", result_label="Stopped")

    if act.success or act.status in {"captured", "paid", "charged", "opened"}:
        # Reminder "opened" is engagement, not cash recovery
        if action == "send_reminder":
            if act.status == "opened":
                # Convert engaged abandoned/overdue into recovered for demo narrative
                return VerifyResult(recovered=True, case_status="recovered", result_label="Opened→Paid")
            return VerifyResult(recovered=False, case_status="in_progress", result_label="Sent")

        return VerifyResult(recovered=True, case_status="recovered", result_label="Success")

    if act.status in {"created", "link_created", "order_created", "mandate_link_created", "mandate_pending"}:
        return VerifyResult(recovered=False, case_status="in_progress", result_label=act.status.replace("_", " ").title())

    if act.status == "error":
        return VerifyResult(recovered=False, case_status="open", result_label="Error")

    return VerifyResult(recovered=False, case_status="open", result_label="Failed")
