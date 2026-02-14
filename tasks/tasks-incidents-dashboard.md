# Tasks: Incidents Dashboard

## Relevant Files

- `devops_incident_suite/results_history/` - **NEW** — Directory for all persisted pipeline results
- `devops_incident_suite/utils/results_store.py` - **NEW** — Helper functions to save and load results history
- `devops_incident_suite/utils/watcher.py` - Modify `_process_file()` to also save results to `results_history/`
- `devops_incident_suite/app.py` - Major changes: add dashboard to home screen, auto-save manual runs, remove Live Results tab, revert to 7 tabs
- `.gitignore` - Add `devops_incident_suite/results_history/` entry

### Notes

- All results files use the naming format: `YYYYMMDD_HHMMSS_<original_filename>.results.json`
- Each results file must include a `source` field: `"upload"`, `"sample"`, or `"watcher"`
- The dashboard reads from `results_history/` only — one unified source of truth
- The watcher continues saving to `live_logs/processed/` as before AND copies to `results_history/`
- Run the app with `cd devops_incident_suite && streamlit run app.py` to test
- Date filtering uses the `processed_at` ISO timestamp inside each results JSON

## Instructions for Completing Tasks

**IMPORTANT:** Check off each task by changing `- [ ]` to `- [x]` after completing.

## Tasks

- [ ] 0.0 Create feature branch
  - [ ] 0.1 Create and checkout branch `feature/incidents-dashboard` from `main`

- [ ] 1.0 Create the results_history directory and gitignore
  - [ ] 1.1 Create `devops_incident_suite/results_history/` directory
  - [ ] 1.2 Add a `.gitkeep` file in `results_history/` so the directory is tracked by git
  - [ ] 1.3 Add `devops_incident_suite/results_history/*.json` to `.gitignore` (keep directory, ignore result files)

- [ ] 2.0 Create the results store helper module
  - [ ] 2.1 Create `devops_incident_suite/utils/results_store.py`
  - [ ] 2.2 Implement `save_result(result: dict, filename: str, source: str)` — adds `source` and `processed_at` fields if missing, generates timestamped filename (`YYYYMMDD_HHMMSS_<filename>.results.json`), saves JSON to `results_history/`
  - [ ] 2.3 Implement `load_results(from_date: date, to_date: date) -> list[dict]` — scans `results_history/` for `.results.json` files, parses `processed_at` from each, filters by date range, returns list sorted by processed time (newest first)
  - [ ] 2.4 Implement `get_highest_severity(issues: list) -> str` — scans issues list and returns the highest severity found (CRITICAL > HIGH > MEDIUM > LOW)

- [ ] 3.0 Auto-save pipeline results for manual runs
  - [ ] 3.1 In `app.py`, after `run_pipeline()` completes successfully, call `save_result(result, file_name, source="upload")` for uploaded files
  - [ ] 3.2 For sample log runs, call `save_result(result, file_name, source="sample")`
  - [ ] 3.3 Add `processing_time_seconds` to the saved result (use the `elapsed` variable already computed)

- [ ] 4.0 Auto-save pipeline results from the live watcher
  - [ ] 4.1 In `utils/watcher.py` `_process_file()`, after saving to `live_logs/processed/`, also call `save_result(output, fname, source="watcher")` to copy results to `results_history/`
  - [ ] 4.2 Import `save_result` from `utils.results_store` in `watcher.py`

- [ ] 5.0 Build the Incidents Dashboard on the home screen
  - [ ] 5.1 Add a `st.subheader("Incidents Dashboard")` section on the main page, below the upload widget and above the analysis tabs
  - [ ] 5.2 The dashboard must always be visible — it does NOT depend on `st.session_state["result"]` existing

- [ ] 6.0 Add date range filter
  - [ ] 6.1 Add two `st.date_input` widgets in a row using `st.columns(2)`: "From" (default: `date.today() - timedelta(days=3)`) and "To" (default: `date.today()`)
  - [ ] 6.2 Constrain date pickers: minimum date = 30 days ago, maximum date = today
  - [ ] 6.3 Call `load_results(from_date, to_date)` with the selected dates to get filtered incidents

- [ ] 7.0 Add summary metrics row
  - [ ] 7.1 Display a metrics row above the incidents list with `st.columns(4)`: Total Incidents, Total Issues, CRITICAL/HIGH Issues, Total Causal Chains
  - [ ] 7.2 Compute metrics by aggregating across all filtered results

- [ ] 8.0 Build expandable incident rows
  - [ ] 8.1 Loop through filtered results and display each as an `st.expander` row
  - [ ] 8.2 Expander header shows: filename, processed timestamp, source badge (upload/sample/watcher), highest severity
  - [ ] 8.3 Expanded content shows: issues count, causal chains count, risk predictions count, processing time, severity distribution
  - [ ] 8.4 Add a "Load Full Results" button inside each expander that sets `st.session_state["result"]` and calls `st.rerun()`
  - [ ] 8.5 Handle empty state: show "No incidents found in selected date range" info message

- [ ] 9.0 Remove the Live Results tab
  - [ ] 9.1 Remove "Live Results" from the `st.tabs()` list — revert to 7 tabs
  - [ ] 9.2 Remove the `tab8` variable and all code inside `with tab8:`
  - [ ] 9.3 Verify the remaining 7 tabs still work correctly

- [ ] 10.0 End-to-end testing
  - [ ] 10.1 Verify the dashboard appears on app load with no prior results (empty state message)
  - [ ] 10.2 Run a sample log through the pipeline, verify it auto-saves to `results_history/` with `source: "sample"`
  - [ ] 10.3 Upload a log file, verify it auto-saves to `results_history/` with `source: "upload"`
  - [ ] 10.4 Enable watcher, drop a file in `live_logs/`, verify it appears in `results_history/` with `source: "watcher"`
  - [ ] 10.5 Verify date filter: change "From" to today, confirm only today's incidents show
  - [ ] 10.6 Verify "Load Full Results" button populates all 7 analysis tabs
  - [ ] 10.7 Verify the Live Results tab is gone — only 7 tabs remain
  - [ ] 10.8 Verify summary metrics update correctly when date range changes
