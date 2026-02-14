"""Root Cause Correlator Agent — identifies causal chains across services."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage


# Default time window (seconds) for grouping related events
TIME_WINDOW = 60

SYSTEM_PROMPT = """\
You are a Root Cause Correlator Agent for a DevOps incident analysis pipeline.

You receive clusters of temporally-close, cross-referenced log events.
Your job is to identify directed causal chains — which event caused which.

For each causal chain you find, return:
- chain: ordered list of events (earliest/root first), each with service, event, timestamp, line_number
- root_cause: description of the originating event
- blast_radius: number of distinct services affected
- affected_services: list of service names
- confidence: HIGH, MEDIUM, or LOW
- summary: one plain-English sentence explaining the chain

Confidence guidelines:
- HIGH: Clear temporal ordering + explicit cross-service references in log messages
- MEDIUM: Temporal correlation exists but causation is inferred
- LOW: Events are in the same time window but causal link is uncertain

Return a JSON array of chain objects. If events are independent (no causal link), return an empty array [].
Do NOT wrap the JSON in markdown code fences. Return ONLY valid JSON.
"""


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse a YYYY-MM-DD HH:MM:SS timestamp. Returns None on failure."""
    try:
        return datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return None


def _build_time_groups(entries: list[dict], window: int = TIME_WINDOW) -> list[list[dict]]:
    """Group entries that fall within `window` seconds of each other."""
    # Sort by timestamp
    timed = []
    for e in entries:
        dt = _parse_timestamp(e.get("timestamp", ""))
        if dt:
            timed.append((dt, e))
    timed.sort(key=lambda x: x[0])

    if not timed:
        return []

    groups: list[list[dict]] = []
    current_group = [timed[0][1]]
    group_start = timed[0][0]

    for dt, entry in timed[1:]:
        if (dt - group_start).total_seconds() <= window:
            current_group.append(entry)
        else:
            if len(current_group) >= 2:
                groups.append(current_group)
            current_group = [entry]
            group_start = dt

    if len(current_group) >= 2:
        groups.append(current_group)

    return groups


def _find_cross_references(entries: list[dict], all_services: set[str]) -> list[list[dict]]:
    """Find entries that mention other services in their message text."""
    cross_ref_clusters: dict[str, set[int]] = defaultdict(set)

    for i, entry in enumerate(entries):
        msg = entry.get("message", "").lower()
        entry_service = entry.get("service", "").lower()
        for svc in all_services:
            if svc.lower() != entry_service and svc.lower() in msg:
                # This entry references another service
                cross_ref_clusters[svc.lower()].add(i)
                cross_ref_clusters[entry_service].add(i)

    # Build clusters of cross-referencing entries
    if not cross_ref_clusters:
        return []

    seen: set[int] = set()
    clusters = []
    for indices in cross_ref_clusters.values():
        cluster_indices = indices - seen
        if len(cluster_indices) >= 2:
            cluster = [entries[i] for i in sorted(cluster_indices) if i < len(entries)]
            if len(cluster) >= 2:
                clusters.append(cluster)
                seen.update(cluster_indices)

    return clusters


def _merge_candidates(time_groups: list[list[dict]], cross_refs: list[list[dict]]) -> list[list[dict]]:
    """Merge time-window groups with cross-reference clusters. Prefer clusters that appear in both."""
    if not time_groups and not cross_refs:
        return []

    # Use all candidates, deduplicate by entry line numbers
    candidates = []
    seen_sets: list[set[int]] = []

    # Cross-referenced groups that also overlap temporally are strongest
    for cluster in cross_refs:
        line_nums = {e.get("line_number", 0) for e in cluster}
        for tg in time_groups:
            tg_lines = {e.get("line_number", 0) for e in tg}
            overlap = line_nums & tg_lines
            if len(overlap) >= 2:
                merged = {e.get("line_number", 0): e for e in cluster + tg}
                merged_entries = list(merged.values())
                merged_set = set(merged.keys())
                if merged_set not in seen_sets:
                    candidates.append(merged_entries)
                    seen_sets.append(merged_set)

    # If no overlap, use cross-refs (stronger signal than time alone)
    if not candidates:
        for cluster in cross_refs:
            line_nums = {e.get("line_number", 0) for e in cluster}
            if line_nums not in seen_sets:
                candidates.append(cluster)
                seen_sets.append(line_nums)

    # Add time groups that aren't already covered
    if not candidates:
        for tg in time_groups:
            line_nums = {e.get("line_number", 0) for e in tg}
            if line_nums not in seen_sets:
                candidates.append(tg)
                seen_sets.append(line_nums)

    return candidates


def run(state: dict, llm) -> dict:
    """Identify causal chains from log entries and issues."""
    log_entries = state.get("log_entries", [])
    issues = state.get("issues", [])

    if not log_entries:
        return {"causal_chains": [], "current_agent": "root_cause"}

    # Filter to actionable entries
    actionable_levels = {"CRITICAL", "ERROR", "WARN", "WARNING"}
    actionable = [e for e in log_entries if e.get("level", "") in actionable_levels]

    if len(actionable) < 2:
        return {"causal_chains": [], "current_agent": "root_cause"}

    # Collect all service names
    all_services = {e.get("service", "") for e in log_entries if e.get("service", "")}
    all_services.discard("unknown")

    # Deterministic: time-window grouping + service cross-referencing
    time_groups = _build_time_groups(actionable)
    cross_refs = _find_cross_references(actionable, all_services)
    candidates = _merge_candidates(time_groups, cross_refs)

    if not candidates:
        return {"causal_chains": [], "current_agent": "root_cause"}

    # Send candidates to LLM for causal reasoning
    candidates_text = json.dumps(candidates, indent=2, default=str)
    issues_text = json.dumps(issues[:10], indent=2, default=str) if issues else "[]"

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Analyze these correlated event clusters and identify causal chains:\n\n"
                f"Event clusters:\n{candidates_text}\n\n"
                f"Known issues for context:\n{issues_text}"
            )
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
            "causal_chains": [],
            "error": f"Root cause agent returned invalid JSON: {text[:200]}",
            "current_agent": "root_cause",
        }

    # Normalize output
    chains = []
    for item in parsed:
        confidence_raw = item.get("confidence", "MEDIUM").upper()
        if confidence_raw not in {"HIGH", "MEDIUM", "LOW"}:
            confidence_raw = "MEDIUM"

        chain_events = []
        for evt in item.get("chain", []):
            chain_events.append({
                "service": evt.get("service", "unknown"),
                "event": evt.get("event", ""),
                "timestamp": evt.get("timestamp", ""),
                "line_number": evt.get("line_number", 0),
            })

        affected = item.get("affected_services", [])
        chains.append({
            "chain": chain_events,
            "root_cause": item.get("root_cause", ""),
            "blast_radius": item.get("blast_radius", len(affected)),
            "affected_services": affected,
            "confidence": confidence_raw,
            "summary": item.get("summary", ""),
        })

    return {"causal_chains": chains, "current_agent": "root_cause"}
