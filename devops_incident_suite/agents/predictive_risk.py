"""Predictive Risk Agent — detects escalation signals and forecasts risks."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage


SYSTEM_PROMPT = """\
You are a Predictive Risk Agent for a DevOps incident analysis pipeline.

You receive detected escalation signals from log analysis. Each signal includes:
- The service affected
- The type of signal (frequency_acceleration, numeric_trend, known_pattern)
- Supporting evidence (specific log entries and values)

Your job is to assess each signal and predict what will happen next if no action is taken.

For each risk prediction, return:
- service: affected service name
- risk_level: HIGH, MEDIUM, or LOW
- prediction: what will likely happen next (be specific)
- evidence: list of evidence strings (log excerpts, values)
- preventive_action: concrete step to prevent escalation
- time_horizon: "minutes", "hours", or "eventual"

Risk level guidelines:
- HIGH: Imminent failure likely (accelerating errors, resources near exhaustion)
- MEDIUM: Degradation probable if trend continues (slow climb, intermittent warnings)
- LOW: Worth monitoring but not urgent (single signals, stable patterns)

Return a JSON array. If no risks are predicted, return [].
Do NOT wrap the JSON in markdown code fences. Return ONLY valid JSON.
"""

# Regex patterns for extracting numeric values from log messages
NUMERIC_PATTERNS = {
    "disk_percent": re.compile(r"(\d+)%"),
    "latency_ms": re.compile(r"(\d+)\s*ms"),
    "retry_count": re.compile(r"retry\s*(\d+)", re.IGNORECASE),
    "pool_usage": re.compile(r"(\d+)/(\d+)\s*connections?", re.IGNORECASE),
    "rate_value": re.compile(r"(\d+)/(\d+)\s*req", re.IGNORECASE),
}

# Known escalation pattern signatures
KNOWN_PATTERNS = {
    "brute_force": re.compile(
        r"(failed.*(?:auth|login|credentials)|brute\s*force|locked|failed\s*attempts)",
        re.IGNORECASE,
    ),
    "disk_critical": re.compile(r"disk.*(\d+)%", re.IGNORECASE),
    "pool_exhaustion": re.compile(r"(connection\s*pool|pool\s*utilization)", re.IGNORECASE),
    "circuit_breaker": re.compile(r"(circuit\s*breaker|retries?\s*exhausted)", re.IGNORECASE),
}


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse a YYYY-MM-DD HH:MM:SS timestamp."""
    try:
        return datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return None


def _detect_frequency_acceleration(entries_by_service: dict[str, list[dict]]) -> list[dict]:
    """Detect services where WARN/ERROR entries are arriving at an increasing rate."""
    signals = []

    for service, entries in entries_by_service.items():
        timestamps = []
        for e in entries:
            dt = _parse_timestamp(e.get("timestamp", ""))
            if dt:
                timestamps.append((dt, e))
        timestamps.sort(key=lambda x: x[0])

        if len(timestamps) < 3:
            continue

        # Compute gaps between consecutive entries
        gaps = []
        for i in range(1, len(timestamps)):
            gap = (timestamps[i][0] - timestamps[i - 1][0]).total_seconds()
            gaps.append(gap)

        # Check if gaps are decreasing (acceleration)
        if len(gaps) >= 2:
            decreasing = sum(1 for i in range(1, len(gaps)) if gaps[i] < gaps[i - 1])
            if decreasing >= len(gaps) // 2 and decreasing >= 1:
                evidence = [
                    f"Event gaps: {[f'{g:.0f}s' for g in gaps]}",
                    f"Latest entries: {[e.get('message', '')[:80] for _, e in timestamps[-3:]]}",
                ]
                signals.append({
                    "service": service,
                    "signal_type": "frequency_acceleration",
                    "evidence": evidence,
                    "entry_count": len(timestamps),
                })

    return signals


def _detect_numeric_trends(entries_by_service: dict[str, list[dict]]) -> list[dict]:
    """Extract numeric values from log messages and detect upward trends."""
    signals = []

    for service, entries in entries_by_service.items():
        # Collect numeric values per pattern
        pattern_values: dict[str, list[tuple[str, float]]] = defaultdict(list)

        for e in entries:
            msg = e.get("message", "")
            ts = e.get("timestamp", "")

            for name, pattern in NUMERIC_PATTERNS.items():
                match = pattern.search(msg)
                if match:
                    try:
                        val = float(match.group(1))
                        pattern_values[name].append((ts, val))
                    except (ValueError, IndexError):
                        pass

        # Check for upward trends (at least 2 values, last > first)
        for name, values in pattern_values.items():
            if len(values) >= 2:
                first_val = values[0][1]
                last_val = values[-1][1]
                if last_val > first_val:
                    signals.append({
                        "service": service,
                        "signal_type": "numeric_trend",
                        "metric": name,
                        "evidence": [
                            f"{name}: {first_val} -> {last_val} (trending up)",
                            f"From entries at {values[0][0]} to {values[-1][0]}",
                        ],
                    })

    return signals


def _detect_known_patterns(entries_by_service: dict[str, list[dict]]) -> list[dict]:
    """Match against known escalation signatures."""
    signals = []

    for service, entries in entries_by_service.items():
        # Brute force: 3+ auth failures in service's entries
        auth_failures = [
            e for e in entries if KNOWN_PATTERNS["brute_force"].search(e.get("message", ""))
        ]
        if len(auth_failures) >= 3:
            signals.append({
                "service": service,
                "signal_type": "known_pattern",
                "pattern": "brute_force",
                "evidence": [
                    f"{len(auth_failures)} auth failure entries detected",
                    f"Sample: {auth_failures[0].get('message', '')[:80]}",
                ],
            })

        # Disk usage > 80%
        for e in entries:
            disk_match = KNOWN_PATTERNS["disk_critical"].search(e.get("message", ""))
            if disk_match:
                try:
                    pct = int(disk_match.group(1))
                    if pct > 80:
                        signals.append({
                            "service": service,
                            "signal_type": "known_pattern",
                            "pattern": "disk_critical",
                            "evidence": [
                                f"Disk usage at {pct}% (threshold: 80%)",
                                f"Entry: {e.get('message', '')[:80]}",
                            ],
                        })
                        break  # One signal per service per pattern
                except (ValueError, IndexError):
                    pass

        # Connection pool > 75%
        for e in entries:
            pool_match = KNOWN_PATTERNS["pool_exhaustion"].search(e.get("message", ""))
            if pool_match:
                # Try to extract ratio
                ratio_match = re.search(r"(\d+)/(\d+)", e.get("message", ""))
                if ratio_match:
                    try:
                        current = int(ratio_match.group(1))
                        total = int(ratio_match.group(2))
                        if total > 0 and (current / total) > 0.75:
                            signals.append({
                                "service": service,
                                "signal_type": "known_pattern",
                                "pattern": "pool_exhaustion",
                                "evidence": [
                                    f"Pool at {current}/{total} ({100 * current // total}%)",
                                    f"Entry: {e.get('message', '')[:80]}",
                                ],
                            })
                            break
                    except (ValueError, IndexError):
                        pass

        # Circuit breaker / retries exhausted
        for e in entries:
            if KNOWN_PATTERNS["circuit_breaker"].search(e.get("message", "")):
                signals.append({
                    "service": service,
                    "signal_type": "known_pattern",
                    "pattern": "circuit_breaker",
                    "evidence": [
                        f"Circuit breaker or retry exhaustion detected",
                        f"Entry: {e.get('message', '')[:80]}",
                    ],
                })
                break

    return signals


def run(state: dict, llm) -> dict:
    """Detect escalation signals and predict risks."""
    log_entries = state.get("log_entries", [])

    if not log_entries:
        return {"risk_predictions": [], "current_agent": "predictive_risk"}

    # Group entries by service (WARN/ERROR/CRITICAL only)
    actionable_levels = {"CRITICAL", "ERROR", "WARN", "WARNING"}
    entries_by_service: dict[str, list[dict]] = defaultdict(list)
    for e in log_entries:
        if e.get("level", "") in actionable_levels:
            svc = e.get("service", "unknown")
            entries_by_service[svc].append(e)

    if not entries_by_service:
        return {"risk_predictions": [], "current_agent": "predictive_risk"}

    # Run all three detectors
    freq_signals = _detect_frequency_acceleration(entries_by_service)
    trend_signals = _detect_numeric_trends(entries_by_service)
    pattern_signals = _detect_known_patterns(entries_by_service)

    all_signals = freq_signals + trend_signals + pattern_signals

    if not all_signals:
        return {"risk_predictions": [], "current_agent": "predictive_risk"}

    # Send to LLM for risk assessment
    signals_text = json.dumps(all_signals, indent=2, default=str)

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Assess these escalation signals and predict risks:\n\n{signals_text}"
        ),
    ])

    text = response.content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "risk_predictions": [],
            "error": f"Predictive risk agent returned invalid JSON: {text[:200]}",
            "current_agent": "predictive_risk",
        }

    # Normalize output
    predictions = []
    for item in parsed:
        risk_raw = item.get("risk_level", "MEDIUM").upper()
        if risk_raw not in {"HIGH", "MEDIUM", "LOW"}:
            risk_raw = "MEDIUM"

        predictions.append({
            "service": item.get("service", "unknown"),
            "risk_level": risk_raw,
            "prediction": item.get("prediction", ""),
            "evidence": item.get("evidence", []),
            "preventive_action": item.get("preventive_action", ""),
            "time_horizon": item.get("time_horizon", "unknown"),
        })

    return {"risk_predictions": predictions, "current_agent": "predictive_risk"}
