"""Revenue Leak Radar — read-only analytics over existing Case rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import Case

AT_RISK_STATUSES = ("open", "in_progress", "escalated")

PROBLEM_LABELS = {
    "payment_failed": "Payment Failures",
    "abandoned_checkout": "Checkout Abandonment",
    "subscription_failed": "Subscription Failures",
    "overdue_invoice": "Overdue Receivables",
}


def _label(problem_type: str) -> str:
    return PROBLEM_LABELS.get(problem_type, problem_type.replace("_", " ").title())


def compute_revenue_leaks(db: Session) -> dict[str, Any]:
    cases = (
        db.query(Case)
        .options(joinedload(Case.customer))
        .filter(Case.status.in_(AT_RISK_STATUSES))
        .all()
    )

    by_type: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        by_type[case.problem_type].append(case)

    total_paise = sum(c.amount_paise for c in cases)
    categories: list[dict[str, Any]] = []

    for problem_type, group in by_type.items():
        revenue = sum(c.amount_paise for c in group)
        scores = [c.recovery_score for c in group if c.recovery_score is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else None
        pct = round((revenue / total_paise) * 100, 1) if total_paise else 0.0
        categories.append(
            {
                "problem_type": problem_type,
                "label": _label(problem_type),
                "case_count": len(group),
                "revenue_at_risk_paise": revenue,
                "pct_of_total": pct,
                "avg_recovery_score": avg_score,
            }
        )

    categories.sort(key=lambda c: c["revenue_at_risk_paise"], reverse=True)

    top_leak: dict[str, Any] | None = None
    if categories:
        top = categories[0]
        top_leak = {
            "problem_type": top["problem_type"],
            "label": top["label"],
            "revenue_at_risk_paise": top["revenue_at_risk_paise"],
            "pct_of_total": top["pct_of_total"],
            "explanation": (
                f"{top['label']} represent the largest share of current revenue at risk "
                f"({top['pct_of_total']:.1f}% · ₹{top['revenue_at_risk_paise'] / 100:,.0f} · "
                f"{top['case_count']} cases)."
            ),
        }

    insights: list[dict[str, str]] = []

    if cases:
        reason_counts = Counter(c.failure_reason for c in cases)
        top_reason, top_reason_n = reason_counts.most_common(1)[0]
        insights.append(
            {
                "title": "Most common failure reason",
                "detail": (
                    f"{top_reason.replace('_', ' ')} appears in {top_reason_n} of "
                    f"{len(cases)} at-risk cases."
                ),
            }
        )

    if categories:
        avg_amounts = []
        for problem_type, group in by_type.items():
            avg_amounts.append(
                (
                    problem_type,
                    sum(c.amount_paise for c in group) / len(group),
                    len(group),
                )
            )
        avg_amounts.sort(key=lambda x: x[1], reverse=True)
        pt, avg_amt, n = avg_amounts[0]
        insights.append(
            {
                "title": "Highest-value problem category",
                "detail": (
                    f"{_label(pt)} has the highest average case value "
                    f"(₹{avg_amt / 100:,.0f} across {n} cases)."
                ),
            }
        )

    scored_cats = [c for c in categories if c["avg_recovery_score"] is not None]
    if scored_cats:
        best = max(scored_cats, key=lambda c: c["avg_recovery_score"])
        insights.append(
            {
                "title": "Recovery opportunity by category",
                "detail": (
                    f"{best['label']} show the strongest average Recovery Score "
                    f"({best['avg_recovery_score']:.0f}/100) among at-risk categories."
                ),
            }
        )

    dated = [c for c in cases if c.created_at is not None]
    if len(dated) >= 5:
        weekday_counts = Counter(c.created_at.strftime("%A") for c in dated)
        day, day_n = weekday_counts.most_common(1)[0]
        insights.append(
            {
                "title": "Time pattern",
                "detail": (
                    f"Most at-risk cases were created on {day} "
                    f"({day_n} of {len(dated)} dated cases)."
                ),
            }
        )

    return {
        "total_revenue_at_risk_paise": total_paise,
        "total_cases": len(cases),
        "categories": categories,
        "top_leak": top_leak,
        "insights": insights,
    }
