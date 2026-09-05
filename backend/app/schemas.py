from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    phone: str
    risk_tier: str
    payment_history_score: float


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    problem_type: str
    amount_paise: int
    failure_reason: str
    days_overdue: int
    status: str
    attempts: int
    retry_count: int
    recovery_score: Optional[float] = None
    best_action: Optional[str] = None
    razorpay_refs: Optional[str] = None
    created_at: Optional[datetime] = None
    customer: Optional[CustomerOut] = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    customer_id: str
    customer_name: str
    problem: str
    ai_decision: str
    action: str
    result: str
    case_id: Optional[str] = None
    amount_paise: int = 0


class ActionCounts(BaseModel):
    retry_payment: int = 0
    payment_link: int = 0
    send_reminder: int = 0
    retry_mandate: int = 0
    escalate: int = 0
    stop: int = 0


class DashboardOut(BaseModel):
    revenue_at_risk_paise: int
    revenue_recovered_paise: int
    recovery_rate: float
    actions_executed: int
    stopped_escalated: int
    open_cases: int
    action_counts: ActionCounts
    executor_mode: str = Field(description="razorpay or mock")


class PolicyOut(BaseModel):
    max_automatic_retries: int
    max_recovery_attempts: int
    human_approval_amount_paise: int
    human_approval_amount_inr: float
    rules: list[str]
    executor_mode: str


class AgentRunOut(BaseModel):
    run_id: int
    cases_processed: int
    actions_executed: int
    recovered_paise: int
    escalated: int
    stopped: int
    notes: Optional[str] = None


class SeedOut(BaseModel):
    customers: int
    cases: int
    model_trained: bool
    message: str


# --- Revenue Leak Radar (additive) ---


class RevenueLeakCategory(BaseModel):
    problem_type: str
    label: str
    case_count: int
    revenue_at_risk_paise: int
    pct_of_total: float
    avg_recovery_score: Optional[float] = None


class RevenueLeakTop(BaseModel):
    problem_type: str
    label: str
    revenue_at_risk_paise: int
    pct_of_total: float
    explanation: str


class RevenueLeakInsight(BaseModel):
    title: str
    detail: str


class RevenueLeakOut(BaseModel):
    total_revenue_at_risk_paise: int
    total_cases: int
    categories: list[RevenueLeakCategory]
    top_leak: Optional[RevenueLeakTop] = None
    insights: list[RevenueLeakInsight] = []


# --- Recovery What-If Simulator (additive) ---


class SimStrategyResult(BaseModel):
    id: str
    label: str
    estimated_recovery_paise: int
    estimated_recovery_rate: float
    cases_considered: int
    attempted_cases: int
    stopped_cases: int
    escalated_cases: int


class SimulationOut(BaseModel):
    simulation_id: str
    is_simulation: bool = True
    label: str = "SIMULATION"
    strategies: list[SimStrategyResult]
    recommended_strategy: str
    recommendation_reason: str
    cases_considered: int
    at_risk_paise: int
    can_run_agent: bool
    run_note: str
