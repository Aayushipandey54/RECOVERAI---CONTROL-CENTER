export type ActionCounts = {
  retry_payment: number;
  payment_link: number;
  send_reminder: number;
  retry_mandate: number;
  escalate: number;
  stop: number;
};

export type Dashboard = {
  revenue_at_risk_paise: number;
  revenue_recovered_paise: number;
  recovery_rate: number;
  actions_executed: number;
  stopped_escalated: number;
  open_cases: number;
  action_counts: ActionCounts;
  executor_mode: string;
};

export type Customer = {
  id: string;
  name: string;
  email: string;
  phone: string;
  risk_tier: string;
  payment_history_score: number;
};

export type CaseRow = {
  id: string;
  customer_id: string;
  problem_type: string;
  amount_paise: number;
  failure_reason: string;
  days_overdue: number;
  status: string;
  attempts: number;
  retry_count: number;
  recovery_score: number | null;
  best_action: string | null;
  razorpay_refs: string | null;
  customer?: Customer | null;
};

export type AuditRow = {
  id: number;
  timestamp: string;
  customer_id: string;
  customer_name: string;
  problem: string;
  ai_decision: string;
  action: string;
  result: string;
  case_id: string | null;
  amount_paise: number;
};

export type Policy = {
  max_automatic_retries: number;
  max_recovery_attempts: number;
  human_approval_amount_paise: number;
  human_approval_amount_inr: number;
  rules: string[];
  executor_mode: string;
};

export type AgentRunResult = {
  run_id: number;
  cases_processed: number;
  actions_executed: number;
  recovered_paise: number;
  escalated: number;
  stopped: number;
  notes?: string;
};

export type RevenueLeakCategory = {
  problem_type: string;
  label: string;
  case_count: number;
  revenue_at_risk_paise: number;
  pct_of_total: number;
  avg_recovery_score: number | null;
};

export type RevenueLeakTop = {
  problem_type: string;
  label: string;
  revenue_at_risk_paise: number;
  pct_of_total: number;
  explanation: string;
};

export type RevenueLeakInsight = {
  title: string;
  detail: string;
};

export type RevenueLeakOut = {
  total_revenue_at_risk_paise: number;
  total_cases: number;
  categories: RevenueLeakCategory[];
  top_leak: RevenueLeakTop | null;
  insights: RevenueLeakInsight[];
};

export type SimStrategyResult = {
  id: string;
  label: string;
  estimated_recovery_paise: number;
  estimated_recovery_rate: number;
  cases_considered: number;
  attempted_cases: number;
  stopped_cases: number;
  escalated_cases: number;
};

export type SimulationOut = {
  simulation_id: string;
  is_simulation: boolean;
  label: string;
  strategies: SimStrategyResult[];
  recommended_strategy: string;
  recommendation_reason: string;
  cases_considered: number;
  at_risk_paise: number;
  can_run_agent: boolean;
  run_note: string;
};

const BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  dashboard: () => request<Dashboard>("/api/dashboard"),
  cases: (params?: { status?: string; problem_type?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.problem_type) q.set("problem_type", params.problem_type);
    const qs = q.toString();
    return request<CaseRow[]>(`/api/cases${qs ? `?${qs}` : ""}`);
  },
  audit: () => request<AuditRow[]>("/api/audit?limit=150"),
  policy: () => request<Policy>("/api/policy"),
  runAgent: () => request<AgentRunResult>("/api/agent/run", { method: "POST" }),
  seed: () =>
    request<{ customers: number; cases: number; message: string }>("/api/seed", {
      method: "POST",
    }),
  revenueLeaks: () => request<RevenueLeakOut>("/api/revenue-leaks"),
  simulateRecovery: () =>
    request<SimulationOut>("/api/recovery/simulate", { method: "POST" }),
  getSimulation: (id: string) =>
    request<SimulationOut>(`/api/recovery/simulation/${id}`),
};

export function formatINR(paise: number): string {
  const rupees = paise / 100;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(rupees);
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
