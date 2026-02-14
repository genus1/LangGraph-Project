"""Streamlit frontend for the DevOps Incident Analysis Suite."""

from __future__ import annotations

import sys
import os
import json
import time

import streamlit as st

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph import run_pipeline
from models.schemas import Severity


# --- Page Config ---

st.set_page_config(
    page_title="DevOps Incident Analysis Suite",
    page_icon="🔍",
    layout="wide",
)

st.title("DevOps Incident Analysis Suite")
st.caption("Upload server/ops logs and let AI agents analyze, triage, and recommend fixes.")


# --- Sidebar: Config ---

with st.sidebar:
    st.header("Configuration")

    provider = st.selectbox(
        "LLM Provider",
        ["openrouter", "openai", "anthropic"],
        index=0,
    )
    os.environ["LLM_PROVIDER"] = provider

    if provider == "openrouter":
        model = st.text_input("Model", value=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"))
        os.environ["OPENROUTER_MODEL"] = model
    elif provider == "openai":
        model = st.text_input("Model", value=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        os.environ["OPENAI_MODEL"] = model
    elif provider == "anthropic":
        model = st.text_input("Model", value=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
        os.environ["ANTHROPIC_MODEL"] = model

    st.divider()

    slack_mode = st.radio(
        "Slack Notifications",
        ["Dry Run (mock)", "Live (send via webhook)"],
        index=0,
    )
    if slack_mode.startswith("Live"):
        webhook = st.text_input("Slack Webhook URL", type="password")
        if webhook:
            os.environ["SLACK_WEBHOOK_URL"] = webhook
    else:
        os.environ.pop("SLACK_WEBHOOK_URL", None)

    st.divider()

    # Load sample log
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_logs")
    sample_files = sorted(f for f in os.listdir(sample_dir) if f.endswith(".log"))
    selected_sample = st.selectbox("Sample Logs", sample_files)
    if st.button("Load Sample Log"):
        with open(os.path.join(sample_dir, selected_sample)) as f:
            st.session_state["sample_content"] = f.read()
            st.session_state["sample_name"] = selected_sample


# --- File Upload ---

uploaded_file = st.file_uploader(
    "Upload a log file",
    type=["log", "txt", "csv", "json"],
    help="Supported formats: plain text logs, CSV, JSON",
)

# Determine which content to analyze
raw_logs = None
file_name = None

if uploaded_file is not None:
    raw_logs = uploaded_file.read().decode("utf-8", errors="replace")
    file_name = uploaded_file.name
elif "sample_content" in st.session_state:
    raw_logs = st.session_state["sample_content"]
    file_name = st.session_state.get("sample_name", "sample.log")
    st.info(f"Using sample log: {file_name}")


# --- Analysis ---

if raw_logs and st.button("Analyze Logs", type="primary"):
    # Show raw log preview
    with st.expander("Raw Log Preview", expanded=False):
        st.code(raw_logs[:3000] + ("..." if len(raw_logs) > 3000 else ""), language="log")

    # Run the pipeline with progress
    progress = st.progress(0, text="Starting analysis pipeline...")
    status_container = st.empty()

    start_time = time.time()

    progress.progress(10, text="Running Log Classifier Agent...")
    status_container.info("Agent 1/7: Log Reader/Classifier is parsing your logs...")

    try:
        result = run_pipeline(raw_logs, file_name)
    except Exception as e:
        st.error(f"Pipeline error: {e}")
        st.stop()

    elapsed = time.time() - start_time
    progress.progress(100, text="Analysis complete!")
    status_container.success(f"All agents completed in {elapsed:.1f}s")

    # Store results
    st.session_state["result"] = result

# --- Display Results ---

if "result" in st.session_state:
    result = st.session_state["result"]

    # Summary metrics
    log_entries = result.get("log_entries", [])
    issues = result.get("issues", [])
    jira_tickets = result.get("jira_tickets", [])
    notification = result.get("notification")
    causal_chains = result.get("causal_chains", [])
    risk_predictions = result.get("risk_predictions", [])

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Log Entries", len(log_entries))
    col2.metric("Issues", len(issues))
    col3.metric("Causal Chains", len(causal_chains))
    col4.metric("Risk Predictions", len(risk_predictions))
    col5.metric("JIRA Tickets", len(jira_tickets))
    notify_status = "Sent" if notification and notification.get("sent") else "Dry Run"
    col6.metric("Notification", notify_status)

    st.divider()

    # Tabbed output
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Log Entries",
        "Issues & Remediation",
        "Root Cause Analysis",
        "Risk Forecast",
        "Remediation Cookbook",
        "JIRA Tickets",
        "Slack Notification",
    ])

    # Tab 1: Log Entries
    with tab1:
        st.subheader("Parsed Log Entries")
        if log_entries:
            severity_filter = st.multiselect(
                "Filter by level",
                ["CRITICAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG"],
                default=["CRITICAL", "ERROR", "WARN", "WARNING"],
            )
            filtered = [e for e in log_entries if e.get("level") in severity_filter]
            for entry in filtered:
                level = entry.get("level", "UNKNOWN")
                color = {
                    "CRITICAL": "red", "ERROR": "red",
                    "WARN": "orange", "WARNING": "orange",
                    "INFO": "blue", "DEBUG": "gray",
                }.get(level, "gray")
                st.markdown(
                    f"**:{color}[{level}]** `{entry.get('timestamp', '')}` "
                    f"**[{entry.get('service', '')}]** {entry.get('message', '')}"
                )
        else:
            st.info("No log entries parsed.")

    # Tab 2: Issues & Remediation
    with tab2:
        st.subheader("Detected Issues")
        if issues:
            for i, issue in enumerate(issues, 1):
                sev = issue.get("severity", "MEDIUM")
                icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "⚪")
                with st.expander(f"{icon} [{sev}] {issue.get('issue', 'Unknown')}", expanded=(sev in ("CRITICAL", "HIGH"))):
                    st.markdown(f"**Recommended Fix:** {issue.get('recommended_fix', 'N/A')}")
                    st.markdown(f"**Rationale:** {issue.get('rationale', 'N/A')}")
                    if issue.get("source_entries"):
                        st.caption(f"Related log lines: {issue['source_entries']}")
        else:
            st.success("No actionable issues detected.")

    # Tab 3: Root Cause Analysis
    with tab3:
        st.subheader("Root Cause Analysis")
        if causal_chains:
            for i, chain in enumerate(causal_chains, 1):
                confidence = chain.get("confidence", "MEDIUM")
                conf_color = {"HIGH": "green", "MEDIUM": "orange", "LOW": "gray"}.get(confidence, "gray")
                blast = chain.get("blast_radius", 0)
                affected = chain.get("affected_services", [])

                with st.expander(
                    f"Chain {i}: {chain.get('summary', 'Unknown')} — :{conf_color}[{confidence}]",
                    expanded=(confidence == "HIGH"),
                ):
                    st.markdown(f"**Root Cause:** {chain.get('root_cause', 'Unknown')}")
                    st.markdown(f"**Blast Radius:** {blast} service{'s' if blast != 1 else ''} affected — {', '.join(affected)}")

                    # Display chain as flow
                    events = chain.get("chain", [])
                    if events:
                        st.markdown("**Causal Flow:**")
                        for j, evt in enumerate(events):
                            prefix = "**>>**" if j == 0 else "&nbsp;&nbsp;&nbsp;&nbsp;**->**"
                            line_ref = f" (line {evt.get('line_number')})" if evt.get("line_number") else ""
                            st.markdown(
                                f"{prefix} **[{evt.get('service', '?')}]** "
                                f"{evt.get('event', '')}"
                                f" `{evt.get('timestamp', '')}`{line_ref}"
                            )
        else:
            st.info("No causal chains detected — issues may be independent.")

    # Tab 4: Risk Forecast
    with tab4:
        st.subheader("Risk Forecast")
        if risk_predictions:
            risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            sorted_preds = sorted(risk_predictions, key=lambda r: risk_order.get(r.get("risk_level", "LOW"), 3))

            for pred in sorted_preds:
                risk = pred.get("risk_level", "MEDIUM")
                risk_color = {"HIGH": "red", "MEDIUM": "orange", "LOW": "yellow"}.get(risk, "gray")
                risk_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}.get(risk, "⚪")

                with st.expander(
                    f"{risk_icon} [{risk}] {pred.get('service', 'Unknown')} — {pred.get('prediction', '')[:80]}",
                    expanded=(risk == "HIGH"),
                ):
                    st.markdown(f"**Prediction:** {pred.get('prediction', 'N/A')}")
                    st.markdown(f"**Preventive Action:** {pred.get('preventive_action', 'N/A')}")
                    st.markdown(f"**Time Horizon:** `{pred.get('time_horizon', 'unknown')}`")

                    evidence = pred.get("evidence", [])
                    if evidence:
                        st.markdown("**Evidence:**")
                        for ev in evidence:
                            st.markdown(f"- {ev}")
        else:
            st.success("No escalation risks detected.")

    # Tab 5: Cookbook
    with tab5:
        st.subheader("Remediation Cookbook")
        cookbook = result.get("cookbook", "")
        if cookbook:
            st.markdown(cookbook)
        else:
            st.info("No cookbook generated.")

    # Tab 6: JIRA Tickets
    with tab6:
        st.subheader("Generated JIRA Tickets")
        if jira_tickets:
            for i, ticket in enumerate(jira_tickets, 1):
                with st.expander(f"Ticket {i}: {ticket.get('summary', 'Untitled')}", expanded=True):
                    st.markdown(f"**Priority:** {ticket.get('priority', 'N/A')}")
                    st.markdown(f"**Labels:** {', '.join(ticket.get('labels', []))}")
                    st.markdown(f"**Description:**\n\n{ticket.get('description', 'N/A')}")
                    if ticket.get("steps_to_reproduce"):
                        st.markdown(f"**Steps to Reproduce:**\n\n{ticket['steps_to_reproduce']}")
                    st.caption(f"Status: {ticket.get('status', 'CREATED (mock)')}")

                    # Show raw JSON payload
                    with st.expander("Raw JSON Payload"):
                        st.json(ticket)
        else:
            st.info("No tickets generated (only CRITICAL/HIGH issues produce tickets).")

    # Tab 7: Notification
    with tab7:
        st.subheader("Slack Notification")
        if notification:
            mode = notification.get("mode", "dry-run")
            sent = notification.get("sent", False)

            if sent:
                st.success(f"Message sent to {notification.get('channel', '#devops-alerts')} (mode: {mode})")
            else:
                st.warning(f"Dry run mode — message not sent (mode: {mode})")

            st.markdown("**Message Preview:**")
            st.markdown(notification.get("summary", "No summary"))

            with st.expander("Full Slack Payload"):
                st.json(notification.get("payload", {}))
        else:
            st.info("No notification generated.")

    # Error display
    if result.get("error"):
        st.error(f"Pipeline error: {result['error']}")
