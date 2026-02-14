# Vibe Check: Incidents Dashboard

**Date:** 2026-02-14
**Scope:** PRD and task list review for the Incidents Dashboard feature
**Files reviewed:** `prd-incidents-dashboard.md`, `tasks-incidents-dashboard.md`, existing `app.py`, `utils/watcher.py`

---

## Core Value

**See past incidents immediately on app load, filter by date, load any result into the analysis view.** This is real value — it turns the app from a one-shot tool into a persistent incident history.

## Verdict: Clean plan. One simplification, rest is solid.

---

## What's Good (KEEP)

- **File-based storage** — JSON files in a directory. No database, no migrations, no new dependencies. The right call for a demo/tooling app.
- **Single source of truth** — `results_history/` is the one place the dashboard reads from. Watcher still writes to `live_logs/processed/` for backward compat, but dashboard ignores it. Clean.
- **Timestamped filenames** — `YYYYMMDD_HHMMSS_<name>.results.json` means `sorted(os.listdir())` gives chronological order for free. No need to open files just to sort.
- **`source` field** — Simple string tag (`upload`/`sample`/`watcher`) to distinguish origin. No enum, no schema change, just a string in the JSON.
- **Dashboard always visible** — Smart UX. Users see value on first load instead of a blank upload screen.
- **Removing Live Results tab** — Good. It was redundant once the dashboard exists. Consolidation, not addition.
- **`results_store.py` as a helper module** — Right amount of abstraction. Three functions that are called from two places (app.py and watcher.py). That justifies the module.

## What to Simplify (FLAGS)

### 1. `load_results()` reads every JSON file on every Streamlit rerun — fine for now, but be aware

The task says "scan `results_history/` for `.results.json` files, parse `processed_at` from each." This means opening and parsing every JSON on every Streamlit interaction.

**For <100 files:** Zero problem. Streamlit reruns in milliseconds.
**For 1000+ files:** Would need caching. But the PRD says 30 days of data, and you'd need 33+ incidents per day to hit 1000. Not a v1 concern.

**Fix:** None needed now. Just don't add caching or indexing prematurely. If it gets slow, add `@st.cache_data` later.

### 2. `get_highest_severity()` helper (Task 2.4) — inline it

A one-liner helper function for something used once in the dashboard. This is a micro-abstraction.

**Fix:** Just inline it where needed:
```python
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
highest = min((i.get("severity", "LOW") for i in issues), key=lambda s: SEVERITY_ORDER.get(s, 4), default="—")
```

If you keep it in `results_store.py` for readability, that's fine too — it's not over-engineering, just slightly unnecessary.

**Impact:** Trivial either way. Not blocking.

### 3. Date picker min_date constraint (Task 6.2) — skip it

Task says "constrain date pickers: minimum date = 30 days ago." Streamlit's `st.date_input` doesn't enforce this well — users can still type arbitrary dates. If they pick 60 days ago and there are no results, they'll just see the empty state. That's fine.

**Fix:** Set `min_value` for visual guidance but don't add validation logic. The `load_results()` function naturally returns nothing for dates with no files.

**Impact:** No code change needed, just don't over-validate.

---

## What's NOT Over-Engineered (CONFIRMED OK)

- **30 sub-tasks** — Appropriate for scope (new module + major app.py restructure + watcher change + tab removal).
- **Separate `results_store.py`** — Two callers (app.py + watcher.py) sharing save/load logic justifies the module.
- **Summary metrics row** — 4 aggregated numbers above the list. Simple `sum()` across results. No heavy computation.
- **Expandable rows** — Existing pattern already used in Live Results tab and analysis tabs. Copy-paste with tweaks.

## Suggested Task Modifications

| Task | Change | Reason |
|------|--------|--------|
| 0.0 | Ask user if they want a new branch or stay on `main` | Previous features used `feature/new-agents` |
| 2.4 | Optional — inline `get_highest_severity()` if preferred | One-liner used once |
| 6.2 | Keep `min_value` for visual guidance, skip validation logic | Empty state handles it naturally |

## Defer to v2

- `@st.cache_data` on `load_results()` if performance becomes an issue
- Free-text search across incident filenames
- Visual trend charts (issues over time)
- Auto-cleanup of results older than 30 days

## Summary

| Area | Status |
|------|--------|
| Storage approach | File-based JSON — zero new dependencies |
| New module | `results_store.py` — justified (2 callers) |
| Dashboard UX | Always-visible, date-filtered, expandable rows |
| Tab changes | Remove tab 8, revert to 7 tabs |
| Watcher impact | One extra `save_result()` call in `_process_file()` |
| app.py impact | Moderate — add save calls + dashboard section + remove tab 8 |
| Task count | 30 sub-tasks — appropriate for scope |
| Risk of scope creep | Low — well-bounded, no new dependencies |

**Overall: 9/10 on the vibe scale.** The plan is focused: one new module, one new directory, surgical changes to two existing files, and a tab removal. No new dependencies, no database, no premature optimization. The dashboard gives the app real persistent value without adding complexity.

**Ship the vibe.**
