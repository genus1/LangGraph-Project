"""Live folder watcher — polls a directory for new log files and runs the pipeline."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime, timezone

VALID_EXTENSIONS = {".log", ".txt", ".csv", ".json"}


def _get_pending_files(watch_dir: str, processed_dir: str) -> list[str]:
    """Return files in watch_dir that haven't been processed yet."""
    if not os.path.isdir(watch_dir):
        return []

    processed_names = set(os.listdir(processed_dir)) if os.path.isdir(processed_dir) else set()
    pending = []

    for fname in os.listdir(watch_dir):
        fpath = os.path.join(watch_dir, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in VALID_EXTENSIONS:
            continue
        if fname in processed_names:
            continue
        pending.append(fpath)

    return sorted(pending)


def _process_file(file_path: str, processed_dir: str) -> dict | None:
    """Read a log file, run the pipeline, save results, and move the file."""
    from graph import run_pipeline

    fname = os.path.basename(file_path)
    os.makedirs(processed_dir, exist_ok=True)

    start = time.time()

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        raw_logs = f.read()

    result = run_pipeline(raw_logs, fname)
    elapsed = time.time() - start

    # Build results with metadata
    output = {
        "filename": fname,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "processing_time_seconds": round(elapsed, 2),
        "log_entries": result.get("log_entries", []),
        "issues": result.get("issues", []),
        "cookbook": result.get("cookbook", ""),
        "jira_tickets": result.get("jira_tickets", []),
        "notification": result.get("notification"),
        "causal_chains": result.get("causal_chains", []),
        "risk_predictions": result.get("risk_predictions", []),
    }

    # Save results JSON
    results_path = os.path.join(processed_dir, f"{fname}.results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    # Move original file to processed
    dest_path = os.path.join(processed_dir, fname)
    shutil.move(file_path, dest_path)

    # Also save to results_history for the dashboard
    from utils.results_store import save_result
    save_result(output, fname, source="watcher")

    return output


def start_watcher(
    watch_dir: str,
    processed_dir: str,
    stop_event: threading.Event,
    poll_interval: int = 5,
) -> None:
    """Poll watch_dir for new files and process them. Runs until stop_event is set."""
    os.makedirs(watch_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    while not stop_event.is_set():
        try:
            pending = _get_pending_files(watch_dir, processed_dir)
            for fpath in pending:
                if stop_event.is_set():
                    break
                try:
                    _process_file(fpath, processed_dir)
                except Exception:
                    # Bad file should not crash the watcher
                    pass
        except Exception:
            pass

        stop_event.wait(timeout=poll_interval)


def stop_watcher(stop_event: threading.Event) -> None:
    """Signal the watcher loop to stop."""
    stop_event.set()
