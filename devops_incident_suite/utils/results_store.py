"""Results store — save and load pipeline results for the incidents dashboard."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone

_RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_history")

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def save_result(result: dict, filename: str, source: str) -> str:
    """Save a pipeline result to results_history/.

    Adds `source` and `processed_at` if not already present.
    Returns the path to the saved file.
    """
    os.makedirs(_RESULTS_DIR, exist_ok=True)

    if "processed_at" not in result:
        result["processed_at"] = datetime.now(timezone.utc).isoformat()
    if "source" not in result:
        result["source"] = source
    if "filename" not in result:
        result["filename"] = filename

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = filename.replace("/", "_").replace("\\", "_")
    out_name = f"{ts}_{safe_name}.results.json"
    out_path = os.path.join(_RESULTS_DIR, out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    return out_path


def load_results(from_date: date, to_date: date) -> list[dict]:
    """Load results from results_history/ filtered by date range.

    Returns a list of result dicts sorted by processed_at (newest first).
    """
    if not os.path.isdir(_RESULTS_DIR):
        return []

    results = []
    for fname in os.listdir(_RESULTS_DIR):
        if not fname.endswith(".results.json"):
            continue

        fpath = os.path.join(_RESULTS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        processed_at = data.get("processed_at", "")
        try:
            dt = datetime.fromisoformat(processed_at)
            result_date = dt.date()
        except (ValueError, TypeError):
            continue

        if from_date <= result_date <= to_date:
            data["_result_file"] = fname
            results.append(data)

    results.sort(key=lambda r: r.get("processed_at", ""), reverse=True)
    return results
