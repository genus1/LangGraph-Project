# PRD: Root Cause Correlator & Predictive Risk Agents

## 1. Introduction/Overview

This PRD covers two new agents being added to the existing DevOps Incident Analysis Suite LangGraph pipeline:

1. **Root Cause Correlator Agent** — Analyzes the detected issues and log entries to identify **causal chains** across services and time. Instead of listing individual symptoms (which the Remediation agent already does), this agent answers: *"What actually caused this incident, and what broke because of it?"*

2. **Predictive Risk Agent** — Analyzes warning-level signals to predict **what's about to break next**. While every existing agent is reactive (analyzing what already happened), this agent is predictive — it identifies escalation patterns and recommends preventive actions before issues become critical.

Both agents run in the existing parallel fan-out after Remediation, alongside Cookbook, JIRA Ticket, and Notification agents.

**Problem they solve:** The current pipeline tells you *what went wrong* and *what to fix*. These agents add two missing perspectives: *why it went wrong* (causal analysis) and *what will go wrong next* (predictive analysis). Together they transform the suite from a reactive incident tool into a proactive analysis platform.

## 2. Goals

1. Add a Root Cause Correlator agent that identifies causal chains linking related issues across services, using time-window grouping and service-name correlation (deterministic first, LLM refinement second).
2. Add a Predictive Risk agent that detects escalation signals (frequency acceleration, numeric trend extraction, known pattern matching) and forecasts which warnings are likely to become critical.
3. Add two new Streamlit UI tabs — "Root Cause Analysis" and "Risk Forecast" — with rich formatting.
4. Integrate the Predictive Risk agent's high-risk predictions into the existing Slack notification.
5. Add new Pydantic models for both agents' output and extend the LangGraph state accordingly.
6. Follow project conventions: deterministic/regex-first, LLM as fallback/refinement, simple agent functions, no over-engineering.

## 3. User Stories

- **As an SRE investigating an incident**, I want to see causal chains showing how a failure in one service cascaded to others, so I can fix the root cause instead of chasing symptoms.
- **As an on-call engineer**, I want to know which warnings are accelerating toward critical so I can take preventive action before the next page fires.
- **As a team lead reviewing an incident**, I want to see the blast radius (how many services were affected) so I can assess the scope of impact.
- **As a DevOps engineer**, I want escalation forecasts with evidence (specific log lines, timing patterns) so I can justify preventive actions to stakeholders.

## 4. Functional Requirements

### 4.1 Root Cause Correlator Agent

1. The agent must consume `log_entries` and `issues` from the pipeline state.
2. The agent must group related events using a **time-window heuristic** — events within a configurable window (default: 60 seconds) that mention the same or related services are candidates for correlation.
3. The agent must use **service-name matching** across log messages to link events from different services that reference each other (e.g., "auth-service" appearing in a payment-service error message).
4. The agent must send the grouped candidates to the LLM to identify directed causal chains (A caused B caused C).
5. The agent must output a list of `CausalChain` objects, each containing:
   - `chain`: ordered list of events in the chain (service, event description, timestamp)
   - `root_cause`: the identified originating event
   - `blast_radius`: count of affected services
   - `affected_services`: list of service names impacted
   - `confidence`: HIGH / MEDIUM / LOW
   - `summary`: one-sentence plain-English explanation
6. If no causal chains are detected (e.g., all issues are independent), the agent must return an empty list and set a "no correlations found" message.

### 4.2 Predictive Risk Agent

7. The agent must consume `log_entries` and `issues` from the pipeline state.
8. The agent must perform three types of **deterministic signal detection** before calling the LLM:
   - **Frequency acceleration**: For each service, check if WARN/ERROR entries are arriving at an increasing rate (e.g., gap between entries is shrinking).
   - **Numeric trend extraction**: Use regex to extract numeric values from log messages (disk %, latency ms, retry counts, connection pool sizes) and detect upward/downward trends.
   - **Known pattern matching**: Match against known escalation signatures — repeated auth failures (brute-force), incrementing retry counts, connection pool depletion, disk usage climbing.
9. The agent must send the detected signals to the LLM to generate risk assessments and preventive actions.
10. The agent must output a list of `RiskPrediction` objects, each containing:
    - `service`: affected service name
    - `risk_level`: HIGH / MEDIUM / LOW
    - `prediction`: what is likely to happen next
    - `evidence`: list of specific log entries/patterns supporting the prediction
    - `preventive_action`: recommended action to prevent escalation
    - `time_horizon`: estimated urgency (e.g., "minutes", "hours", "eventual")
11. If no escalation signals are detected, the agent must return an empty list.

### 4.3 State & Model Updates

12. New Pydantic models must be added to `schemas.py`: `CausalChain`, `ChainEvent`, `RiskPrediction`, and a `RiskLevel` enum (HIGH/MEDIUM/LOW).
13. The `PipelineState` TypedDict in `graph.py` must be extended with `causal_chains` (list, merge reducer) and `risk_predictions` (list, merge reducer).
14. The Pydantic `PipelineState` in `schemas.py` must also be updated for consistency.

### 4.4 Graph Updates

15. Both agents must be added as new nodes in the LangGraph `StateGraph`.
16. Both must fan out from `remediation` in parallel with the existing three agents.
17. Both must converge to `END` (or to a shared join point if the notification agent needs their output).

### 4.5 Notification Integration

18. The existing Notification agent must be updated to include a "Risk Forecast" section in the Slack message when high-risk predictions exist.
19. The notification must run **after** the Predictive Risk agent completes (sequential dependency), not in parallel with it.
20. If no high-risk predictions exist, the notification should remain unchanged.

### 4.6 Streamlit UI Updates

21. Add a new **"Root Cause Analysis"** tab to the Streamlit dashboard.
22. The RCA tab must display each causal chain as a visual flow (using arrows/indentation to show the cascade), with the root cause highlighted.
23. Each chain must show: confidence level, blast radius count, affected services, and summary.
24. Add a new **"Risk Forecast"** tab to the Streamlit dashboard.
25. The Risk Forecast tab must display predictions grouped by risk level (HIGH first), with color coding (red/orange/yellow).
26. Each prediction must show: service name, predicted outcome, evidence, preventive action, and time horizon.

## 5. Non-Goals (Out of Scope)

- **Explicit service dependency map** — The agent infers relationships from log content and timing, not from a pre-configured topology file.
- **Historical trend analysis** — Predictions are based on patterns within the single uploaded log file only, not across multiple uploads or sessions.
- **Real-time monitoring** — This remains a batch analysis tool; no continuous log streaming or alerting.
- **Machine learning models** — Predictions use heuristic rules + LLM reasoning, not trained ML models.
- **Automated remediation execution** — The agents recommend actions but do not execute them.

## 6. Design Considerations

### Updated Architecture Diagram
```
Upload -> Log Classifier -> Remediation -> +-- Cookbook Synthesizer ----+
                                           +-- JIRA Ticket Agent ------+
                                           +-- Root Cause Correlator --+--> Notification Agent --> END
                                           +-- Predictive Risk Agent --+
```

Note: Notification runs after Predictive Risk so it can include risk forecasts in the Slack message. The other four agents (Cookbook, JIRA, Root Cause, Predictive Risk) run in parallel.

### UI Layout — RCA Tab
- Each causal chain displayed as an indented flow with arrow connectors
- Root cause event highlighted (bold or colored)
- Confidence badge (HIGH=green, MEDIUM=yellow, LOW=gray)
- Blast radius shown as a metric (e.g., "4 services affected")

### UI Layout — Risk Forecast Tab
- Predictions grouped under HIGH / MEDIUM / LOW headers
- Color-coded severity (red/orange/yellow)
- Each prediction is an expandable section showing evidence and preventive action
- Time horizon shown as a tag/badge

## 7. Technical Considerations

- **Time-window grouping (RCA):** Use Python's datetime parsing on log timestamps to calculate deltas between events. Group events where `|t1 - t2| < window` (default 60s). This is deterministic — no LLM needed.
- **Service-name cross-referencing (RCA):** Scan log messages for mentions of other known service names (extracted from the `service` field across all log entries). Build an adjacency set deterministically.
- **Frequency analysis (Predictive Risk):** For each service, collect timestamps of WARN/ERROR entries and compute inter-event gaps. If gaps are decreasing (acceleration), flag it.
- **Numeric extraction (Predictive Risk):** Regex patterns like `(\d+)%`, `(\d+)ms`, `retry (\d+)`, `pool.*?(\d+)/(\d+)` to pull trending values from log messages.
- **Graph modification:** The notification node must now depend on the predictive risk node completing. This changes the fan-out slightly — 4 agents parallel after remediation, then notification sequential after predictive risk.
- **Both agents** must follow the existing pattern: simple `run(state, llm)` function, return a dict of state updates, handle JSON parse failures gracefully.

## 8. Success Metrics

1. **Root Cause Correlator** correctly identifies at least one causal chain in 4 of the 5 sample log files.
2. **Predictive Risk Agent** detects at least one escalation signal in each sample log file that contains WARN-level entries.
3. Both agents complete without errors across all 5 sample log files.
4. Causal chains match human-intuitive root causes (e.g., for `microservices_mixed.log`, the auth-service deployment is identified as root cause of the cascade).
5. Risk predictions include concrete evidence (specific log line references) and actionable preventive steps.
6. Slack notifications include the risk forecast section when high-risk predictions exist.
7. Both new UI tabs render correctly with proper formatting, color coding, and expandable sections.

## 9. Open Questions

1. Should the time window for causal correlation be user-configurable in the sidebar, or is a hardcoded 60s default sufficient?
2. Should the RCA tab include a visual graph/diagram (e.g., Mermaid or Graphviz rendered in Streamlit), or is indented text sufficient for the demo?
3. Should the Predictive Risk agent have a configurable sensitivity threshold for what counts as "accelerating"?
