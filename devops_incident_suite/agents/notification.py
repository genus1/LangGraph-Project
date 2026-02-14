"""Notification Agent — formats and sends Slack notifications."""

from __future__ import annotations

import json
import os

from langchain_core.messages import SystemMessage, HumanMessage

from utils.slack_client import send_slack_message


def _get_channel() -> str:
    return os.getenv("SLACK_CHANNEL", "#new-channel")


SYSTEM_PROMPT = """\
You are a Notification Agent for a DevOps incident analysis pipeline.

You receive a list of detected issues and a remediation cookbook.
Your job is to create a concise Slack notification summary.

Format the message for Slack using markdown:
- Lead with an attention-grabbing header based on the highest severity
- List the top issues (max 5) with severity and recommended action
- Keep each issue and its details compact — no blank line between an issue title and its details
- Put a blank line between separate issues for readability
- Include a link placeholder for the full cookbook
- If risk predictions are provided, add a "Risk Forecast" section after the issues listing the HIGH-risk predictions with their preventive actions
- Keep it scannable — ops engineers are busy

Return ONLY the notification text (Slack markdown). No JSON wrapping.
"""


def run(state: dict, llm) -> dict:
    """Format a Slack notification and optionally send it."""
    issues = state.get("issues", [])
    cookbook = state.get("cookbook", "")

    if not issues:
        return {
            "notification": {
                "channel": _get_channel(),
                "summary": "No actionable issues detected.",
                "payload": {},
                "sent": False,
                "mode": "dry-run",
            },
            "current_agent": "notification",
        }

    # Include HIGH risk predictions if available
    risk_predictions = state.get("risk_predictions", [])
    high_risks = [r for r in risk_predictions if r.get("risk_level") == "HIGH"]

    context_data = {"issues": issues, "cookbook_preview": cookbook[:500]}
    if high_risks:
        context_data["risk_predictions"] = high_risks

    context = json.dumps(context_data, indent=2, default=str)

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Create a Slack notification for these findings:\n\n{context}"
        ),
    ])

    summary_text = response.content.strip()

    payload = {
        "channel": _get_channel(),
        "text": summary_text,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary_text},
            }
        ],
    }

    # Try to send via Slack webhook
    sent, mode = send_slack_message(payload)

    return {
        "notification": {
            "channel": _get_channel(),
            "summary": summary_text,
            "payload": payload,
            "sent": sent,
            "mode": mode,
        },
        "current_agent": "notification",
    }
