# Vibe Check: Root Cause Correlator & Predictive Risk Agents

**Date:** 2026-02-14
**Scope:** PRD and task list review for two new agents
**Files reviewed:** `prd-new-agents.md`, `tasks-new-agents.md`, existing agents, `graph.py`, `schemas.py`, `app.py`

---

## Core Value

Add "why it broke" (causal analysis) and "what's about to break" (predictive analysis) to the existing pipeline. **Both are genuinely useful perspectives that the current 5 agents don't cover.**

## Verdict: Good plan with a few simplification opportunities.

---

## What's Good (KEEP)

- **Deterministic-first approach for both agents** — Time-window grouping, service cross-referencing, frequency analysis, regex extraction all run before LLM. Matches the project's established pattern (log_classifier does the same).
- **Simple `run(state, llm)` functions** — No new base classes, no new frameworks. Both agents follow the exact same pattern as the existing 5.
- **Two new UI tabs** — Clean separation. Each agent gets its own tab, consistent with existing 5-tab layout.
- **Parallel fan-out** — Both new agents run alongside existing ones, not adding sequential bottleneck (except the notification dependency, see below).
- **Task breakdown is actionable** — 62 sub-tasks for 2 agents + graph changes + 2 UI tabs is reasonable. Each sub-task is clear enough for implementation.

## What to Simplify (FLAGS)

### 1. Merge `Confidence` and `RiskLevel` enums — they're identical

Task 1.1 creates `RiskLevel(HIGH, MEDIUM, LOW)` and task 1.2 creates `Confidence(HIGH, MEDIUM, LOW)`. These are the same three values.

**Fix:** Use a single enum. Call it `Confidence` or just reuse a generic name. Both agents reference it.

**Impact:** Removes 1 sub-task, reduces schema surface area.

### 2. Timestamp parsing — keep it dead simple

Task 2.2 says "parse common log timestamp formats into datetime objects." This can easily become a rabbit hole (timezones, ISO 8601 variants, syslog formats, etc.).

**Fix:** The sample logs all use `YYYY-MM-DD HH:MM:SS` format. Support that one format with a single `datetime.strptime()` call, wrapped in a try/except that falls back to string comparison. Don't build a multi-format parser.

**Impact:** Keeps the RCA agent under ~120 lines instead of ballooning.

### 3. Known pattern matcher (task 3.4) — cap at 3-4 patterns

The PRD lists: auth failures, retry counts, disk usage, connection pool. That's 4 patterns. Don't add more "just in case."

**Fix:** Implement exactly those 4. If a sample log doesn't match any, that's fine — the frequency and numeric detectors will still catch signals. The LLM handles the rest.

**Impact:** Keeps the Predictive Risk agent focused. Patterns can always be added in v2.

### 4. Notification rewiring — adds real graph complexity, but worth it

Making notification sequential after predictive_risk (`predictive_risk → notification` instead of `remediation → notification`) is the one architectural change that touches the existing graph structure. It's justified (risk forecasts in Slack are useful), but it's also where bugs will hide.

**Watch out for:** LangGraph needs all parallel branches to either reach END or converge. With 4 parallel nodes (cookbook, jira, root_cause, predictive_risk) and notification chaining off predictive_risk, make sure cookbook/jira/root_cause still go directly to END while predictive_risk → notification → END.

**No simplification needed**, just flagging it as the riskiest change — test this wiring first before building the agents.

### 5. Pydantic models — stay consistent with existing pattern

The previous vibe-check flagged that `schemas.py` models are defined but not validated at runtime (agents pass plain dicts). The new models (`CausalChain`, `ChainEvent`, `RiskPrediction`) should follow the same pattern for consistency — define them for documentation, but agents return dicts.

**Don't:** Add runtime Pydantic validation now just for the new agents while the old ones skip it.

---

## What's NOT Over-Engineered (CONFIRMED OK)

- **62 sub-tasks** — Appropriate granularity for the scope. Not inflated.
- **Two new UI tabs** — 7 tabs total is fine for a demo. Each tab shows a distinct agent output.
- **Three signal detectors in Predictive Risk** — Frequency, numeric trends, and pattern matching are three genuinely different signal types. Not redundant.
- **Time-window + service cross-referencing in RCA** — Two complementary heuristics that serve different purposes. Both needed for meaningful correlation.

## Suggested Task Modifications

| Task | Change | Reason |
|------|--------|--------|
| 1.1 + 1.2 | Merge into single enum (e.g., `Confidence`) | Identical values |
| 2.2 | Scope to single timestamp format + try/except fallback | Avoid parser rabbit hole |
| 3.4 | Hard cap at 4 patterns listed in PRD | Prevent scope creep |
| 4.6 | Implement and test graph rewiring FIRST before agents | Riskiest integration point |

## Defer to v2

- Configurable time window in sidebar (Open Question 1 from PRD) — hardcode 60s
- Mermaid/Graphviz visual diagrams in RCA tab (Open Question 2) — indented text is fine
- Configurable sensitivity thresholds (Open Question 3) — hardcode reasonable defaults
- Additional known escalation patterns beyond the initial 4

## Summary

| Area | Status |
|------|--------|
| Architecture | Clean — extends existing fan-out, no new abstractions |
| Agent design | Consistent — `run(state, llm)` pattern, deterministic-first |
| Graph changes | One tricky rewire (notification dependency) — test early |
| Pydantic models | Keep consistent with existing pattern (documentation, not validation) |
| UI additions | Appropriate — two focused tabs |
| Task count | Reasonable (62 sub-tasks, could drop to ~59 with simplifications) |
| Risk of scope creep | Medium — timestamp parsing and pattern matching are the two areas to watch |

**Overall: 8.5/10 on the vibe scale.** The plan is well-scoped and follows established patterns. The simplifications above are minor — merge one duplicate enum, constrain two areas that could balloon, and test the graph rewiring early. No fundamental rethinking needed.

**Ship the vibe.**
