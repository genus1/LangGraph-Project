# Project Prompt: Multi-Agent DevOps Incident Analysis Suite

## Overview

Build a Multi-Agent DevOps Incident Analysis Suite using Python, Streamlit for the frontend, and LangGraph for agent orchestration. The app lets users upload ops/server log files and automatically analyzes them through a pipeline of collaborating AI agents.

## Architecture

### Streamlit Frontend

Simple UI with:
- File upload widget for log files (text, CSV, JSON)
- A dashboard showing: parsed log entries, detected issues with severity, recommended fixes, and status of notifications sent
- Tabs or expandable sections for each agent's output so the workflow is traceable

### LangGraph Orchestrator

Manages the flow between the following agents in a directed graph.

### Agent Definitions (each agent is a node in the LangGraph graph)

1. **Log Reader/Classifier Agent:** Takes raw log input, parses it into structured records (timestamp, level, service, message), categorizes each entry (ERROR, WARN, INFO, etc.), and extracts key fields. Output: list of structured log entries with classification.

2. **Remediation Agent:** Takes the classified log entries (especially ERRORs and WARNs), and for each detected issue, maps it to a recommended fix and rationale. Use an LLM to reason about the error context and suggest actionable remediation steps. Output: list of {issue, severity, recommended_fix, rationale}.

3. **Cookbook Synthesizer Agent:** Takes the remediation output and creates a consolidated, actionable checklist/runbook. Groups related issues, prioritizes by severity, and formats as a step-by-step remediation cookbook. Output: markdown-formatted checklist.

4. **JIRA Ticket Agent:** For any CRITICAL or HIGH severity issues, generates a structured JIRA ticket payload (summary, description, priority, labels, steps to reproduce). For now, mock the JIRA API call but structure the payload so it's ready for real integration. Output: list of ticket payloads + simulated creation status.

5. **Notification Agent:** Takes the remediation results and cookbook, formats a summary message, and sends it to a Slack channel via webhook. For now, support both a real Slack webhook URL (configurable via env var) and a mock/dry-run mode that just displays what would be sent. Output: notification payload + send status.

### LangGraph Flow

```
Upload → Log Reader/Classifier → Remediation → [Cookbook Synthesizer, JIRA Ticket Agent, Notification Agent]
```

After Remediation, the three downstream agents can run in parallel. The orchestrator collects all outputs and returns them to the Streamlit UI.

## Tech Stack

- Python 3.11+
- Streamlit for UI
- LangGraph for orchestration
- LangChain + ChatOpenAI (or Anthropic Claude) as the LLM backbone for each agent
- Pydantic models for structured data between agents
- python-dotenv for config (API keys, Slack webhook URL)

## Project Structure

```
devops_incident_suite/
├── app.py                  # Streamlit frontend
├── graph.py                # LangGraph orchestrator definition
├── agents/
│   ├── log_classifier.py
│   ├── remediation.py
│   ├── cookbook.py
│   ├── jira_ticket.py
│   └── notification.py
├── models/
│   └── schemas.py          # Pydantic models for state/data
├── utils/
│   └── slack_client.py     # Slack webhook helper
├── sample_logs/
│   └── sample.log          # Example log file for testing
├── requirements.txt
├── .env.example
└── README.md
```

## Requirements

- Each agent should have clear system prompts defining its role and expected output format
- Use Pydantic models to validate data flowing between agents (LogEntry, Issue, Remediation, JiraTicket, SlackNotification, etc.)
- The Streamlit app should show a progress indicator as each agent completes
- Include a sample log file with realistic mixed entries (INFO, WARN, ERROR, CRITICAL) covering scenarios like OOM errors, connection timeouts, disk space warnings, and auth failures
- Make the LLM provider configurable (OpenAI or Anthropic) via env var
