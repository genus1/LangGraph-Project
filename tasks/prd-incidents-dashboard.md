# PRD: Incidents Dashboard

## 1. Introduction/Overview

Add an **Incidents Dashboard** to the main home screen of the DevOps Incident Analysis Suite. The dashboard is the first thing users see when they open the app — a historical view of all previously processed incidents (both from manual pipeline runs and the live folder watcher). It replaces the current "cold start" experience where users see only an upload widget.

**Problem it solves:** Currently, once a pipeline run is complete, the results are lost when the session ends (manual runs) or buried in JSON files (watcher results). There is no way to browse, filter, or revisit past incidents. DevOps teams need a persistent, date-filterable view of all incidents their system has analyzed.

## 2. Goals

1. Show a persistent incidents dashboard on the app's home screen, visible immediately on load — before any file is uploaded or analyzed.
2. Auto-save every pipeline run (manual upload, sample log, and live watcher) as a `.results.json` file so all incidents are available for the dashboard.
3. Provide date-range filtering with a "from" and "to" date picker, defaulting to the last 3 days.
4. Retain up to 30 days of historical data on the dashboard.
5. Display summary metrics and allow loading any past incident into the full 7-tab analysis view.
6. Consolidate the existing "Live Results" tab (tab 8) into the dashboard — the dashboard replaces it.

## 3. User Stories

- **As an SRE**, I want to see recent incidents as soon as I open the app, so I can quickly check what's happened in the last few days without running a new analysis.
- **As a DevOps engineer**, I want to filter incidents by date range, so I can focus on a specific time window when investigating a recurring issue.
- **As a team lead**, I want to see all incidents — both manually uploaded and auto-processed by the watcher — in one place, so I have a complete picture of analyzed incidents.
- **As a developer**, I want to click on any past incident and load its full results into the analysis tabs, so I can drill into the details without re-running the pipeline.

## 4. Functional Requirements

### 4.1 Results Persistence

1. Create a `results_history/` directory inside `devops_incident_suite/` to store all pipeline results.
2. Every pipeline run (manual upload, sample log, or live watcher) must auto-save a `.results.json` file to `results_history/`.
3. The filename format must include a timestamp for easy sorting: `YYYYMMDD_HHMMSS_<original_filename>.results.json`.
4. The watcher should continue saving to `live_logs/processed/` as it does today, but **also** copy the `.results.json` to `results_history/` so all results are in one place.
5. Each results file must include a `source` field indicating origin: `"upload"`, `"sample"`, or `"watcher"`.

### 4.2 Dashboard — Home Screen

6. The dashboard must be displayed on the main home screen **always** — it is the first thing users see when the app loads.
7. The existing upload widget and "Analyze Logs" button remain above or alongside the dashboard (the upload workflow is unchanged).
8. The 7 analysis tabs only appear **after** a result is loaded (either from a new pipeline run or by clicking "Load" on a dashboard incident).

### 4.3 Date Range Filter

9. Display a date range filter at the top of the dashboard with two date pickers: "From" and "To".
10. Default "From" date: **3 days ago** from today.
11. Default "To" date: **today**.
12. The dashboard only shows incidents whose `processed_at` timestamp falls within the selected date range.
13. The date pickers should allow selection of any date within the last 30 days.

### 4.4 Dashboard Content

14. Show **summary metrics** at the top of the dashboard: total incidents in range, total issues found, total CRITICAL/HIGH severity issues, total causal chains.
15. Below the metrics, display a **list of incidents** sorted by processed time (newest first).
16. Each incident row must show: filename, processed timestamp, source (upload/sample/watcher), issues count, causal chains count, risk predictions count, and highest severity found.
17. Each incident row must be expandable to show a summary breakdown: severity distribution, top issues, processing time.
18. Each expanded row must have a **"Load Full Results"** button that loads the incident into `st.session_state["result"]` so the 7 analysis tabs populate with it.

### 4.5 Remove Live Results Tab

19. Remove the "Live Results" tab (tab 8) from the tabbed output section — its functionality is now fully covered by the dashboard.
20. The tabs should go back to 7: Log Entries, Issues & Remediation, Root Cause Analysis, Risk Forecast, Remediation Cookbook, JIRA Tickets, Slack Notification.

## 5. Non-Goals (Out of Scope)

- **Search/text filter** — No free-text search across incidents for v1. Date filtering is sufficient.
- **Delete/archive incidents** — No ability to remove incidents from the dashboard.
- **Charts/graphs** — No visual trend charts for v1. Tabular list with metrics is sufficient.
- **Cross-incident correlation** — No comparing or linking incidents across files.
- **Database storage** — File-based JSON storage only, no SQLite or other DB.

## 6. Design Considerations

### Home Screen Layout
```
┌──────────────────────────────────────────────────┐
│  DevOps Incident Analysis Suite                  │
│  Upload server/ops logs and let AI agents...     │
│                                                  │
│  [Upload a log file]              [Analyze Logs] │
│                                                  │
│  ─── Incidents Dashboard ─────────────────────── │
│  From: [2026-02-11]  To: [2026-02-14]           │
│                                                  │
│  Total: 5 incidents | 32 issues | 8 CRIT/HIGH   │
│                                                  │
│  ▸ live_auth_outage.log — 2026-02-14 17:58      │
│    🏷️ watcher | Issues: 5 | Chains: 3 | Risks: 3│
│  ▸ caching_layer.log — 2026-02-14 15:30         │
│    🏷️ upload  | Issues: 4 | Chains: 3 | Risks: 3│
│  ...                                             │
│                                                  │
│  ─── Analysis Tabs (shown after loading) ─────── │
│  [Log Entries] [Issues] [RCA] [Risk] [Cookbook]...│
└──────────────────────────────────────────────────┘
```

## 7. Technical Considerations

- **Storage location:** `devops_incident_suite/results_history/` — add to `.gitignore`.
- **Watcher integration:** The watcher's `_process_file()` in `utils/watcher.py` must also save a copy of results to `results_history/`.
- **Manual run integration:** After `run_pipeline()` completes in `app.py`, auto-save the result to `results_history/`.
- **Date parsing:** Parse `processed_at` (ISO 8601) from each `.results.json` to filter by date range.
- **Performance:** Scanning JSON files on every Streamlit rerun is fine for <1000 files. No caching needed for v1.
- **Existing Live Results tab:** Remove tab 8 entirely. The sidebar "Files processed" metric in the watcher section remains unchanged.

## 8. Success Metrics

1. Dashboard loads immediately on app start and shows incidents within the default 3-day range.
2. All pipeline runs (upload, sample, watcher) produce a `.results.json` in `results_history/`.
3. Date filtering works correctly — changing "From"/"To" updates the displayed incidents.
4. "Load Full Results" button populates the 7 analysis tabs with the selected incident's data.
5. No regression in existing functionality (upload, sample logs, watcher, Slack).

## 9. Open Questions

1. Should incidents from sample logs (run during development/testing) be visually distinguished from production watcher incidents? (Suggested: yes — the `source` tag handles this.)
