# Tasks: Root Cause Correlator & Predictive Risk Agents

## Relevant Files

- `devops_incident_suite/models/schemas.py` - Add new Pydantic models (`RiskLevel`, `ChainEvent`, `CausalChain`, `RiskPrediction`) and update `PipelineState`
- `devops_incident_suite/agents/__init__.py` - Export new agent modules
- `devops_incident_suite/agents/root_cause.py` - **NEW** — Root Cause Correlator agent implementation
- `devops_incident_suite/agents/predictive_risk.py` - **NEW** — Predictive Risk agent implementation
- `devops_incident_suite/agents/notification.py` - Update to include risk forecast section in Slack messages
- `devops_incident_suite/graph.py` - Extend `PipelineState`, add new nodes, rewire graph edges
- `devops_incident_suite/app.py` - Add two new UI tabs, update metrics row and progress indicators

### Notes

- Both agents follow the existing pattern: a `run(state, llm)` function that returns a dict of state updates
- Deterministic heuristics run first (pure Python), LLM is called only for refinement/reasoning
- Run the app with `cd devops_incident_suite && streamlit run app.py` to test
- Test each agent against all 5 sample log files in `devops_incident_suite/sample_logs/`

## Instructions for Completing Tasks

**IMPORTANT:** Check off each task by changing `- [ ]` to `- [x]` after completing.

## Tasks

- [ ] 0.0 Create feature branch
  - [ ] 0.1 Create and checkout branch `feature/new-agents` from `main`

- [ ] 1.0 Add Pydantic models and enums for both agents
  - [ ] 1.1 Add `RiskLevel` enum to `schemas.py` with values: `HIGH`, `MEDIUM`, `LOW`
  - [ ] 1.2 Add `Confidence` enum to `schemas.py` with values: `HIGH`, `MEDIUM`, `LOW` (used by RCA agent)
  - [ ] 1.3 Add `ChainEvent` model with fields: `service` (str), `event` (str), `timestamp` (str), `line_number` (int)
  - [ ] 1.4 Add `CausalChain` model with fields: `chain` (list[ChainEvent]), `root_cause` (str), `blast_radius` (int), `affected_services` (list[str]), `confidence` (Confidence), `summary` (str)
  - [ ] 1.5 Add `RiskPrediction` model with fields: `service` (str), `risk_level` (RiskLevel), `prediction` (str), `evidence` (list[str]), `preventive_action` (str), `time_horizon` (str)
  - [ ] 1.6 Update the Pydantic `PipelineState` in `schemas.py` to include `causal_chains: list[CausalChain]` and `risk_predictions: list[RiskPrediction]`

- [ ] 2.0 Implement the Root Cause Correlator agent
  - [ ] 2.1 Create `devops_incident_suite/agents/root_cause.py` with the `run(state, llm)` function signature
  - [ ] 2.2 Implement **timestamp parsing helper** — parse common log timestamp formats into `datetime` objects for delta calculations
  - [ ] 2.3 Implement **time-window grouping** — group log entries (ERROR/CRITICAL/WARN) that fall within a 60-second window of each other
  - [ ] 2.4 Implement **service cross-referencing** — collect all unique service names from `log_entries`, then scan each entry's `message` field for mentions of other services to build an adjacency set
  - [ ] 2.5 Combine time-window groups with service cross-references to produce **correlation candidates** (clusters of entries that are temporally close AND reference each other's services)
  - [ ] 2.6 Write the **LLM prompt** — send correlation candidates to the LLM, instructing it to return a JSON array of causal chains with fields: `chain` (ordered events), `root_cause`, `blast_radius`, `affected_services`, `confidence`, `summary`
  - [ ] 2.7 Parse the LLM JSON response into a list of dicts, with fallback handling for malformed output (return empty list + error message)
  - [ ] 2.8 Return state update dict: `{"causal_chains": [...], "current_agent": "root_cause"}`
  - [ ] 2.9 Handle the empty case — if no correlation candidates exist, return an empty `causal_chains` list

- [ ] 3.0 Implement the Predictive Risk agent
  - [ ] 3.1 Create `devops_incident_suite/agents/predictive_risk.py` with the `run(state, llm)` function signature
  - [ ] 3.2 Implement **frequency acceleration detector** — for each service, collect timestamps of WARN/ERROR entries, compute inter-event gaps, flag if gaps are decreasing (at least 3 data points needed)
  - [ ] 3.3 Implement **numeric trend extractor** — regex patterns to extract values like `(\d+)%` (disk/cpu), `(\d+)\s*ms` (latency), `retry\s*(\d+)` (retry count), `(\d+)/(\d+)` (pool usage) from log messages; detect increasing/decreasing trends per service
  - [ ] 3.4 Implement **known pattern matcher** — detect known escalation signatures: repeated auth failures (3+ in short window = brute-force), incrementing retry counts, disk usage > 80%, connection pool > 75% capacity
  - [ ] 3.5 Combine all detected signals into a structured summary per service (which signal types fired, with evidence)
  - [ ] 3.6 Write the **LLM prompt** — send detected signals to the LLM, instructing it to return a JSON array of risk predictions with fields: `service`, `risk_level`, `prediction`, `evidence`, `preventive_action`, `time_horizon`
  - [ ] 3.7 Parse the LLM JSON response with fallback handling for malformed output (return empty list)
  - [ ] 3.8 Return state update dict: `{"risk_predictions": [...], "current_agent": "predictive_risk"}`
  - [ ] 3.9 Handle the empty case — if no signals detected, return an empty `risk_predictions` list

- [ ] 4.0 Update the LangGraph pipeline state and graph
  - [ ] 4.1 Add `causal_chains: Annotated[list, _merge_lists]` and `risk_predictions: Annotated[list, _merge_lists]` to the `PipelineState` TypedDict in `graph.py`
  - [ ] 4.2 Add imports for the new agent modules (`root_cause`, `predictive_risk`) in `graph.py`
  - [ ] 4.3 Create node wrapper functions `root_cause_node(state)` and `predictive_risk_node(state)` following existing pattern
  - [ ] 4.4 Register both new nodes with `graph.add_node()`
  - [ ] 4.5 Add fan-out edges from `remediation` to both new nodes (`graph.add_edge("remediation", "root_cause")` and `graph.add_edge("remediation", "predictive_risk")`)
  - [ ] 4.6 Rewire notification: remove the direct `remediation → notification` edge; add `predictive_risk → notification` edge so notification runs after predictive risk completes
  - [ ] 4.7 Add `root_cause → END` edge (root cause has no downstream dependents)
  - [ ] 4.8 Verify notification still has `notification → END` edge
  - [ ] 4.9 Update `run_pipeline()` initial state dict to include `"causal_chains": []` and `"risk_predictions": []`

- [ ] 5.0 Update the Notification agent for risk forecast integration
  - [ ] 5.1 Update `notification.py` `run()` to read `risk_predictions` from state
  - [ ] 5.2 Filter for HIGH risk predictions only
  - [ ] 5.3 Append a "Risk Forecast" section to the LLM context when high-risk predictions exist (add them to the `context` JSON passed to the LLM)
  - [ ] 5.4 Update the `SYSTEM_PROMPT` to instruct the LLM to include a risk forecast section when predictions are provided
  - [ ] 5.5 If no high-risk predictions exist, leave the notification behavior unchanged

- [ ] 6.0 Add the "Root Cause Analysis" Streamlit UI tab
  - [ ] 6.1 Add a 6th tab "Root Cause Analysis" to the `st.tabs()` call in `app.py`
  - [ ] 6.2 Display each causal chain as an indented flow with arrow connectors between events (use `st.markdown` with formatted text like `service → service → service`)
  - [ ] 6.3 Highlight the root cause event (bold text)
  - [ ] 6.4 Show confidence badge with color coding (HIGH=green, MEDIUM=yellow, LOW=gray)
  - [ ] 6.5 Show blast radius as a metric (e.g., "4 services affected") and list affected service names
  - [ ] 6.6 Display the chain summary text
  - [ ] 6.7 Handle empty state — show "No causal chains detected" info message

- [ ] 7.0 Add the "Risk Forecast" Streamlit UI tab
  - [ ] 7.1 Add a 7th tab "Risk Forecast" to the `st.tabs()` call in `app.py`
  - [ ] 7.2 Group predictions by risk level (HIGH first, then MEDIUM, then LOW)
  - [ ] 7.3 Color-code each group header (red for HIGH, orange for MEDIUM, yellow for LOW)
  - [ ] 7.4 Display each prediction as an expandable section with: service name, predicted outcome, evidence list, preventive action, and time horizon badge
  - [ ] 7.5 Auto-expand HIGH risk predictions
  - [ ] 7.6 Handle empty state — show "No escalation risks detected" success message

- [ ] 8.0 Update agents `__init__.py` and misc
  - [ ] 8.1 Add `root_cause` and `predictive_risk` imports to `devops_incident_suite/agents/__init__.py`
  - [ ] 8.2 Update the progress bar text in `app.py` to reflect the new agent count (7 agents instead of 5)
  - [ ] 8.3 Update the summary metrics row in `app.py` to include causal chains count and risk predictions count

- [ ] 9.0 End-to-end testing with all 5 sample log files
  - [ ] 9.1 Run the pipeline against `microservices_mixed.log` — verify RCA finds the auth-service cascade and Predictive Risk flags accelerating warnings
  - [ ] 9.2 Run against `kubernetes_cluster.log` — verify both agents produce output
  - [ ] 9.3 Run against `database_outage.log` — verify both agents produce output
  - [ ] 9.4 Run against `security_incident.log` — verify both agents produce output
  - [ ] 9.5 Run against `ci_cd_pipeline.log` — verify both agents produce output
  - [ ] 9.6 Verify the Slack notification includes risk forecast section when high-risk predictions exist
  - [ ] 9.7 Verify all 7 Streamlit tabs render correctly with no errors
