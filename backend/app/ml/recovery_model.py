"""Recovery Score model — sklearn classifier trained on synthetic labels."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "recovery_model.joblib"

PROBLEM_TYPES = [
    "payment_failed",
    "abandoned_checkout",
    "subscription_failed",
    "overdue_invoice",
]
FAILURE_REASONS = [
    "insufficient_funds",
    "bank_decline",
    "network_error",
    "mandate_failed",
    "card_expired",
    "customer_abandoned",
    "invoice_overdue",
]


def _encode(value: str, vocabulary: list[str]) -> int:
    try:
        return vocabulary.index(value)
    except ValueError:
        return 0


def features_from_row(
    amount_paise: int,
    days_overdue: int,
    failure_reason: str,
    prior_attempts: int,
    customer_success_rate: float,
    problem_type: str,
) -> np.ndarray:
    return np.array(
        [
            [
                amount_paise / 100.0,
                days_overdue,
                _encode(failure_reason, FAILURE_REASONS),
                prior_attempts,
                customer_success_rate,
                _encode(problem_type, PROBLEM_TYPES),
            ]
        ],
        dtype=float,
    )


def synthetic_training_matrix(n: int = 2500, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = []
    y = []
    for _ in range(n):
        amount = float(rng.integers(499, 75000))
        days = int(rng.integers(0, 45))
        fr_idx = int(rng.integers(0, len(FAILURE_REASONS)))
        attempts = int(rng.integers(0, 4))
        success = float(rng.uniform(0.2, 0.98))
        pt_idx = int(rng.integers(0, len(PROBLEM_TYPES)))

        # Label heuristic: recoverable if temporary failures + good history + few attempts
        temp = FAILURE_REASONS[fr_idx] in {"insufficient_funds", "network_error", "customer_abandoned"}
        score = 0.0
        score += 0.35 if temp else -0.15
        score += success * 0.4
        score -= attempts * 0.12
        score -= min(days, 30) / 30 * 0.15
        score -= 0.1 if amount > 25000 else 0.0
        label = 1 if score + rng.normal(0, 0.08) > 0.35 else 0

        X.append([amount, days, fr_idx, attempts, success, pt_idx])
        y.append(label)
    return np.array(X, dtype=float), np.array(y, dtype=int)


def train_and_persist(n: int = 2500) -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    X, y = synthetic_training_matrix(n=n)
    model = GradientBoostingClassifier(random_state=42)
    model.fit(X, y)
    payload = {
        "model": model,
        "problem_types": PROBLEM_TYPES,
        "failure_reasons": FAILURE_REASONS,
    }
    joblib.dump(payload, MODEL_PATH)
    train_acc = float(model.score(X, y))
    return {"path": str(MODEL_PATH), "train_accuracy": train_acc, "n_samples": n}


def load_model() -> dict[str, Any] | None:
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


def recovery_score(
    amount_paise: int,
    days_overdue: int,
    failure_reason: str,
    prior_attempts: int,
    customer_success_rate: float,
    problem_type: str,
) -> float:
    """Return Recovery Score 0–100 (probability of successful recovery * 100)."""
    payload = load_model()
    feats = features_from_row(
        amount_paise,
        days_overdue,
        failure_reason,
        prior_attempts,
        customer_success_rate,
        problem_type,
    )
    if payload is None:
        # Heuristic fallback before first train
        temp = failure_reason in {"insufficient_funds", "network_error", "customer_abandoned"}
        base = 55.0 if temp else 35.0
        base += customer_success_rate * 30
        base -= prior_attempts * 12
        base -= min(days_overdue, 30)
        return float(max(5.0, min(95.0, base)))

    model: GradientBoostingClassifier = payload["model"]
    if hasattr(model, "predict_proba"):
        proba = float(model.predict_proba(feats)[0][1])
    else:
        proba = float(model.predict(feats)[0])
    return round(proba * 100.0, 1)
