import { useCallback, useEffect, useState } from "react";
import {
  api,
  formatINR,
  formatTime,
  type AuditRow,
  type CaseRow,
  type Dashboard,
  type Policy,
  type RevenueLeakOut,
  type SimulationOut,
} from "./api";

type Tab = "control" | "cases" | "leaks" | "simulator" | "audit" | "policy";

export default function App() {
  const [tab, setTab] = useState<Tab>("control");
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [leaks, setLeaks] = useState<RevenueLeakOut | null>(null);
  const [simulation, setSimulation] = useState<SimulationOut | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [problemFilter, setProblemFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [simBusy, setSimBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    const [d, c, a, p] = await Promise.all([
      api.dashboard(),
      api.cases({
        status: statusFilter || undefined,
        problem_type: problemFilter || undefined,
      }),
      api.audit(),
      api.policy(),
    ]);
    setDash(d);
    setCases(c);
    setAudit(a);
    setPolicy(p);
  }, [statusFilter, problemFilter]);

  useEffect(() => {
    refresh().catch((e: Error) => setError(e.message));
  }, [refresh]);

  useEffect(() => {
    if (tab !== "leaks") return;
    api
      .revenueLeaks()
      .then(setLeaks)
      .catch((e: Error) => setError(e.message));
  }, [tab]);

  async function runAgent() {
    setBusy(true);
    setToast(null);
    setError(null);
    try {
      const result = await api.runAgent();
      await refresh();
      if (tab === "leaks") {
        setLeaks(await api.revenueLeaks());
      }
      setSimulation(null);
      setToast(
        `Agent run #${result.run_id}: ${result.actions_executed} actions · recovered ${formatINR(result.recovered_paise)} · escalated ${result.escalated} · stopped ${result.stopped}`
      );
      setTab("audit");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Agent run failed");
    } finally {
      setBusy(false);
    }
  }

  async function reseeds() {
    setBusy(true);
    setToast(null);
    setError(null);
    try {
      const r = await api.seed();
      await refresh();
      setLeaks(null);
      setSimulation(null);
      setToast(r.message);
      setTab("control");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed failed");
    } finally {
      setBusy(false);
    }
  }

  async function simulateRecovery() {
    setSimBusy(true);
    setToast(null);
    setError(null);
    try {
      const result = await api.simulateRecovery();
      setSimulation(result);
      setToast("Simulation complete — estimates only; no payments or audit actions were executed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setSimBusy(false);
    }
  }

  async function runRecommended() {
    if (!simulation?.can_run_agent) {
      setError(
        simulation?.run_note ||
          "Cannot run agent: no open cases or policy prevents execution."
      );
      return;
    }
    setToast(null);
    setError(null);
    await runAgent();
  }

  const counts = dash?.action_counts;
  const recommended = simulation?.strategies.find(
    (s) => s.id === simulation.recommended_strategy
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <h1>
            <span className="brand-mark">◉</span>RECOVERAI CONTROL CENTER
          </h1>
          <p className="tag">
            Detect → Diagnose → Leak Radar → Simulate → Act → Recover → Audit
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={runAgent} disabled={busy}>
            {busy ? "Running…" : "Run Agent"}
          </button>
          <button className="btn btn-ghost" onClick={reseeds} disabled={busy}>
            Reset Demo Data
          </button>
        </div>
      </header>

      <nav className="tabs">
        {(
          [
            ["control", "Control Center"],
            ["cases", "Cases"],
            ["leaks", "Revenue Leak Radar"],
            ["simulator", "Recovery Simulator"],
            ["audit", "Audit Trail"],
            ["policy", "Policy / Bounds"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            className={`tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {toast && <div className="toast">{toast}</div>}
      {error && <div className="toast error">{error}</div>}

      {tab === "control" && (
        <section className="panel">
          {!dash ? (
            <div className="toast">{error ? error : "Loading Control Center…"}</div>
          ) : (
            <>
              <div className="kpi-board">
                <div className="kpi-header">RECOVERAI CONTROL CENTER</div>
                <div className="kpi-grid">
                  <div className="kpi-cell">
                    <div className="kpi-label">Revenue At Risk</div>
                    <div className="kpi-value warn">{formatINR(dash.revenue_at_risk_paise)}</div>
                  </div>
                  <div className="kpi-cell">
                    <div className="kpi-label">Revenue Recovered</div>
                    <div className="kpi-value good">{formatINR(dash.revenue_recovered_paise)}</div>
                  </div>
                  <div className="kpi-cell">
                    <div className="kpi-label">Recovery Rate</div>
                    <div className="kpi-value">{dash.recovery_rate.toFixed(1)}%</div>
                  </div>
                  <div className="kpi-cell">
                    <div className="kpi-label">Actions Executed</div>
                    <div className="kpi-value">{dash.actions_executed}</div>
                  </div>
                  <div className="kpi-cell">
                    <div className="kpi-label">Stopped / Escalated</div>
                    <div className="kpi-value">{dash.stopped_escalated}</div>
                  </div>
                </div>
              </div>

              <h2 className="section-title">AI Actions</h2>
              <div className="action-grid">
                <div className="action-item">
                  <span>✓ Payment Retry</span>
                  <strong>{counts?.retry_payment ?? 0}</strong>
                </div>
                <div className="action-item">
                  <span>✓ Payment Link</span>
                  <strong>{counts?.payment_link ?? 0}</strong>
                </div>
                <div className="action-item">
                  <span>✓ Reminder</span>
                  <strong>{(counts?.send_reminder ?? 0) + (counts?.retry_mandate ?? 0)}</strong>
                </div>
                <div className="action-item escalate">
                  <span>→ Human Escalation</span>
                  <strong>{(counts?.escalate ?? 0) + (counts?.stop ?? 0)}</strong>
                </div>
              </div>

              <div className="meta-row">
                <span className={`pill dot ${dash.executor_mode === "mock" ? "mock" : ""}`}>
                  executor: {dash.executor_mode}
                </span>
                <span className="pill">open cases: {dash.open_cases}</span>
                <span className="pill">loop: detect → diagnose → decide → act → verify → audit</span>
              </div>
            </>
          )}
        </section>
      )}

      {tab === "cases" && (
        <section className="panel">
          <div className="filters">
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="open">open</option>
              <option value="in_progress">in_progress</option>
              <option value="recovered">recovered</option>
              <option value="escalated">escalated</option>
              <option value="stopped">stopped</option>
            </select>
            <select value={problemFilter} onChange={(e) => setProblemFilter(e.target.value)}>
              <option value="">All problems</option>
              <option value="payment_failed">payment_failed</option>
              <option value="abandoned_checkout">abandoned_checkout</option>
              <option value="subscription_failed">subscription_failed</option>
              <option value="overdue_invoice">overdue_invoice</option>
            </select>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Customer</th>
                  <th>Problem</th>
                  <th>Amount</th>
                  <th>Score</th>
                  <th>Attempts</th>
                  <th>Status</th>
                  <th>Best Action</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">{c.id}</td>
                    <td>
                      {c.customer?.name ?? c.customer_id}
                      <div className="decision">{c.failure_reason}</div>
                    </td>
                    <td>{c.problem_type.replaceAll("_", " ")}</td>
                    <td className="mono">{formatINR(c.amount_paise)}</td>
                    <td className="mono">{c.recovery_score?.toFixed(0) ?? "—"}</td>
                    <td className="mono">{c.attempts}</td>
                    <td>
                      <span className={`status ${c.status}`}>{c.status}</span>
                    </td>
                    <td className="mono">{c.best_action?.replaceAll("_", " ") ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "leaks" && (
        <section className="panel">
          {!leaks ? (
            <div className="toast">Loading Revenue Leak Radar…</div>
          ) : (
            <>
              <div className="feature-banner">
                <div>
                  <h2 className="feature-title">Revenue Leak Radar</h2>
                  <p className="feature-sub">
                    Analytics only — no payments or recovery actions are executed here.
                  </p>
                </div>
                <div className="feature-total">
                  <span>Total Revenue At Risk</span>
                  <strong>{formatINR(leaks.total_revenue_at_risk_paise)}</strong>
                  <small>{leaks.total_cases} at-risk cases</small>
                </div>
              </div>

              {leaks.top_leak && (
                <div className="top-leak-card">
                  <div className="top-leak-label">TOP REVENUE LEAK</div>
                  <div className="top-leak-name">{leaks.top_leak.label}</div>
                  <div className="top-leak-amount">
                    {formatINR(leaks.top_leak.revenue_at_risk_paise)} at risk (
                    {leaks.top_leak.pct_of_total.toFixed(1)}%)
                  </div>
                  <p className="top-leak-why">{leaks.top_leak.explanation}</p>
                </div>
              )}

              <h2 className="section-title">Leak by problem type</h2>
              <div className="leak-list">
                {leaks.categories.map((cat) => (
                  <div className="leak-row" key={cat.problem_type}>
                    <div className="leak-row-head">
                      <span>{cat.label}</span>
                      <strong className="mono">
                        {formatINR(cat.revenue_at_risk_paise)} · {cat.pct_of_total.toFixed(1)}%
                      </strong>
                    </div>
                    <div className="leak-bar-track">
                      <div
                        className="leak-bar-fill"
                        style={{ width: `${Math.max(cat.pct_of_total, 2)}%` }}
                      />
                    </div>
                    <div className="leak-row-meta">
                      <span>{cat.case_count} cases</span>
                      {cat.avg_recovery_score != null && (
                        <span>avg score {cat.avg_recovery_score.toFixed(0)}</span>
                      )}
                    </div>
                  </div>
                ))}
                {leaks.categories.length === 0 && (
                  <div className="toast">No at-risk cases. Reset Demo Data or wait for new failures.</div>
                )}
              </div>

              {leaks.insights.length > 0 && (
                <>
                  <h2 className="section-title">Data-backed insights</h2>
                  <ul className="insight-list">
                    {leaks.insights.map((ins) => (
                      <li key={ins.title}>
                        <strong>{ins.title}</strong>
                        <span>{ins.detail}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </section>
      )}

      {tab === "simulator" && (
        <section className="panel">
          <div className="feature-banner">
            <div>
              <h2 className="feature-title">Recovery What-If Simulator</h2>
              <p className="feature-sub">
                Simulation / Estimated — never calls Razorpay, never writes recovery audit actions.
              </p>
            </div>
            <button className="btn btn-primary" onClick={simulateRecovery} disabled={simBusy || busy}>
              {simBusy ? "Simulating…" : "Simulate Recovery"}
            </button>
          </div>

          <div className="sim-badge">SIMULATION / ESTIMATED</div>

          {!simulation ? (
            <div className="toast">
              Click Simulate Recovery to compare Retry Only, Payment Link, and Balanced strategies on
              current open cases.
            </div>
          ) : (
            <>
              <div className="sim-grid">
                {simulation.strategies.map((s) => (
                  <div
                    key={s.id}
                    className={`sim-card ${
                      s.id === simulation.recommended_strategy ? "recommended" : ""
                    }`}
                  >
                    <div className="sim-card-label">
                      {s.id === simulation.recommended_strategy ? "AI RECOMMENDED · " : ""}
                      {s.label.toUpperCase()}
                    </div>
                    <div className="sim-metric">
                      <span>Estimated Recovery</span>
                      <strong>{formatINR(s.estimated_recovery_paise)}</strong>
                    </div>
                    <div className="sim-metric">
                      <span>Estimated Recovery Rate</span>
                      <strong>{s.estimated_recovery_rate.toFixed(1)}%</strong>
                    </div>
                    <div className="sim-meta">
                      Cases considered: {s.cases_considered}
                      <br />
                      Attempted: {s.attempted_cases} · Stopped: {s.stopped_cases} · Escalated:{" "}
                      {s.escalated_cases}
                    </div>
                  </div>
                ))}
              </div>

              <div className="recommend-box">
                <div className="top-leak-label">Recommended Strategy</div>
                <div className="top-leak-name">
                  {(recommended?.label ?? simulation.recommended_strategy).toUpperCase()}
                </div>
                {recommended && (
                  <div className="top-leak-amount">
                    Estimated Recovery: {formatINR(recommended.estimated_recovery_paise)}
                  </div>
                )}
                <p className="top-leak-why">{simulation.recommendation_reason}</p>
                <p className="run-note">{simulation.run_note}</p>
                <button
                  className="btn btn-primary"
                  onClick={runRecommended}
                  disabled={busy || !simulation.can_run_agent}
                >
                  {busy ? "Running…" : "Run Recommended Strategy"}
                </button>
                {!simulation.can_run_agent && (
                  <p className="decision">
                    Agent cannot run: no open/in-progress cases under current policy state.
                  </p>
                )}
              </div>
            </>
          )}
        </section>
      )}

      {tab === "audit" && (
        <section className="panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Customer</th>
                  <th>Problem</th>
                  <th>AI Decision</th>
                  <th>Action</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((row) => (
                  <tr key={row.id}>
                    <td className="mono">{formatTime(row.timestamp)}</td>
                    <td>
                      {row.customer_id}
                      <div className="decision">{row.customer_name}</div>
                    </td>
                    <td>{row.problem}</td>
                    <td className="decision">{row.ai_decision}</td>
                    <td className="mono">{row.action}</td>
                    <td className="mono">{row.result}</td>
                  </tr>
                ))}
                {audit.length === 0 && (
                  <tr>
                    <td colSpan={6}>No audit rows yet. Click Run Agent.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "policy" && policy && (
        <section className="panel">
          <h2 className="section-title">Bounded · Compliant · Auditable</h2>
          <ul className="policy-list">
            {policy.rules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
          <div className="meta-row">
            <span className="pill">max retries: {policy.max_automatic_retries}</span>
            <span className="pill">max attempts: {policy.max_recovery_attempts}</span>
            <span className="pill">
              human approval: &gt; {formatINR(policy.human_approval_amount_paise)}
            </span>
            <span className={`pill dot ${policy.executor_mode === "mock" ? "mock" : ""}`}>
              {policy.executor_mode}
            </span>
          </div>
        </section>
      )}
    </div>
  );
}
