"""Synthetic demo dataset sized for judge-friendly KPIs."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db import Base, engine
from app.ml.recovery_model import recovery_score, train_and_persist
from app.models import Action, AgentRun, AuditLog, Case, Customer

FIRST_NAMES = [
    "Aarav", "Diya", "Kabir", "Ananya", "Rohan", "Isha", "Vivaan", "Meera",
    "Arjun", "Sana", "Kian", "Priya", "Aditya", "Nisha", "Reyansh", "Tara",
    "Shaurya", "Aanya", "Vihaan", "Kavya",
]
LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Reddy", "Nair", "Gupta", "Iyer", "Khan",
    "Mehta", "Joshi", "Chopra", "Das", "Malhotra", "Banerjee", "Pillai",
]

PROBLEM_MIX = [
    ("payment_failed", 0.40),
    ("abandoned_checkout", 0.25),
    ("subscription_failed", 0.15),
    ("overdue_invoice", 0.20),
]

FAILURE_BY_PROBLEM = {
    "payment_failed": ["insufficient_funds", "bank_decline", "network_error", "card_expired"],
    "abandoned_checkout": ["customer_abandoned"],
    "subscription_failed": ["mandate_failed", "insufficient_funds", "bank_decline"],
    "overdue_invoice": ["invoice_overdue", "insufficient_funds"],
}

AMOUNT_BUCKETS = [
    (49900, 199900),      # ₹499–₹1,999
    (200000, 799900),     # ₹2k–₹7,999
    (800000, 1499900),    # ₹8k–₹14,999
    (2500100, 4599900),   # ₹25,001–₹45,999 (escalation band)
]


def _pick_problem(rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    for name, weight in PROBLEM_MIX:
        acc += weight
        if r <= acc:
            return name
    return "payment_failed"


def _pick_amount(rng: random.Random, force_high: bool = False) -> int:
    if force_high:
        lo, hi = AMOUNT_BUCKETS[3]
        return rng.randint(lo, hi)
    # Bias mid amounts so ~35 open cases ≈ ₹1.5–2.2L at risk
    weights = [0.35, 0.50, 0.15, 0.0]
    bucket = rng.choices(AMOUNT_BUCKETS, weights=weights, k=1)[0]
    return rng.randint(bucket[0], bucket[1])


def clear_all(db: Session) -> None:
    db.query(AuditLog).delete()
    db.query(Action).delete()
    db.query(AgentRun).delete()
    db.query(Case).delete()
    db.query(Customer).delete()
    db.commit()


def seed_database(db: Session, n_customers: int = 120, n_cases: int = 140, seed: int = 7) -> dict:
    Base.metadata.create_all(bind=engine)
    clear_all(db)
    train_info = train_and_persist(n=2500)

    rng = random.Random(seed)
    customers: list[Customer] = []
    for i in range(1, n_customers + 1):
        cid = f"C{100 + i}"
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        customers.append(
            Customer(
                id=cid,
                name=name,
                email=f"{name.lower().replace(' ', '.')}{i}@example.com",
                phone=f"+91{rng.randint(7000000000, 9999999999)}",
                risk_tier=rng.choice(["low", "medium", "high"]),
                payment_history_score=round(rng.uniform(0.35, 0.95), 2),
            )
        )
    db.add_all(customers)
    db.flush()

    # Target open-case mix for demo narrative (~35 actionable)
    open_targets = {
        "payment_failed": 15,
        "abandoned_checkout": 8,
        "subscription_failed": 5,
        "overdue_invoice": 7,
    }
    cases: list[Case] = []
    case_idx = 1

    def add_case(
        problem: str,
        status: str,
        attempts: int = 0,
        force_high: bool = False,
        days: int | None = None,
    ) -> None:
        nonlocal case_idx
        cust = rng.choice(customers)
        failure = rng.choice(FAILURE_BY_PROBLEM[problem])
        amount = _pick_amount(rng, force_high=force_high)
        d_overdue = days if days is not None else rng.randint(0, 28)
        score = recovery_score(
            amount_paise=amount,
            days_overdue=d_overdue,
            failure_reason=failure,
            prior_attempts=attempts,
            customer_success_rate=cust.payment_history_score,
            problem_type=problem,
        )
        cases.append(
            Case(
                id=f"CASE-{case_idx:04d}",
                customer_id=cust.id,
                problem_type=problem,
                amount_paise=amount,
                failure_reason=failure,
                days_overdue=d_overdue,
                status=status,
                attempts=attempts,
                retry_count=min(attempts, 2),
                recovery_score=score,
                best_action=None,
                razorpay_refs=None,
                created_at=datetime.utcnow() - timedelta(days=d_overdue),
            )
        )
        case_idx += 1

    # Open cases matching the demo story
    for problem, count in open_targets.items():
        for j in range(count):
            # A few high-amount cases for escalation demo
            force_high = problem == "payment_failed" and j < 2
            # A couple already at attempt boundary for STOP demo
            attempts = 3 if (problem == "payment_failed" and j == 3) else (1 if j % 4 == 0 else 0)
            add_case(problem, "open", attempts=attempts, force_high=force_high)

    # Historical cases only (no extra open) so Control Center matches the demo mix
    remaining = max(0, n_cases - len(cases))
    for _ in range(remaining):
        problem = _pick_problem(rng)
        status = rng.choices(
            ["recovered", "stopped", "escalated"],
            weights=[0.70, 0.18, 0.12],
            k=1,
        )[0]
        attempts = 1 if status == "recovered" else rng.randint(1, 3)
        add_case(problem, status, attempts=attempts)


    db.add_all(cases)
    db.commit()

    return {
        "customers": len(customers),
        "cases": len(cases),
        "open_cases": sum(1 for c in cases if c.status == "open"),
        "model_trained": True,
        "train_accuracy": train_info.get("train_accuracy"),
        "message": "Demo dataset seeded. Click Run Agent to recover revenue.",
    }
