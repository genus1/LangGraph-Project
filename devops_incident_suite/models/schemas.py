"""Pydantic models for data flowing between agents in the DevOps Incident Analysis pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


# --- Enums ---

class LogLevel(str, Enum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARN = "WARN"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TicketPriority(str, Enum):
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Confidence(str, Enum):
    """Shared confidence/risk level used by RCA and Predictive Risk agents."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# --- Agent I/O Models ---

class LogEntry(BaseModel):
    """A single structured log entry."""
    line_number: int = Field(description="Original line number in the log file")
    timestamp: str = Field(default="", description="Timestamp from the log entry")
    level: LogLevel = Field(description="Log level classification")
    service: str = Field(default="unknown", description="Service or component name")
    message: str = Field(description="Log message content")
    raw: str = Field(description="Original raw log line")


class Issue(BaseModel):
    """A detected issue with severity and recommended fix."""
    issue: str = Field(description="Description of the detected issue")
    severity: Severity = Field(description="Issue severity level")
    recommended_fix: str = Field(description="Actionable remediation step")
    rationale: str = Field(description="Reasoning behind the recommendation")
    source_entries: list[int] = Field(
        default_factory=list,
        description="Line numbers of related log entries",
    )


class JiraTicket(BaseModel):
    """A structured JIRA ticket payload."""
    summary: str = Field(description="Ticket summary/title")
    description: str = Field(description="Detailed ticket description")
    priority: TicketPriority = Field(description="Ticket priority")
    labels: list[str] = Field(default_factory=list)
    steps_to_reproduce: str = Field(default="", description="Steps to reproduce from logs")
    status: str = Field(default="CREATED (mock)", description="Simulated creation status")


class SlackNotification(BaseModel):
    """Slack notification payload."""
    channel: str = Field(default="#devops-alerts")
    summary: str = Field(description="Notification summary text")
    payload: dict = Field(default_factory=dict, description="Full Slack message payload")
    sent: bool = Field(default=False, description="Whether the message was actually sent")
    mode: str = Field(default="dry-run", description="'live' or 'dry-run'")


class ChainEvent(BaseModel):
    """A single event in a causal chain."""
    service: str = Field(description="Service/component name")
    event: str = Field(description="Description of what happened")
    timestamp: str = Field(default="", description="When it happened")
    line_number: int = Field(default=0, description="Source log line number")


class CausalChain(BaseModel):
    """A directed causal chain linking related failure events."""
    chain: list[ChainEvent] = Field(default_factory=list, description="Ordered events in the chain")
    root_cause: str = Field(description="The originating event description")
    blast_radius: int = Field(default=0, description="Number of affected services")
    affected_services: list[str] = Field(default_factory=list, description="Service names impacted")
    confidence: Confidence = Field(default=Confidence.MEDIUM, description="Confidence level")
    summary: str = Field(description="One-sentence explanation of the causal chain")


class RiskPrediction(BaseModel):
    """A predicted escalation risk for a service."""
    service: str = Field(description="Affected service name")
    risk_level: Confidence = Field(description="Risk level (HIGH/MEDIUM/LOW)")
    prediction: str = Field(description="What is likely to happen next")
    evidence: list[str] = Field(default_factory=list, description="Supporting log patterns")
    preventive_action: str = Field(description="Recommended action to prevent escalation")
    time_horizon: str = Field(default="unknown", description="Estimated urgency")


# --- LangGraph Pipeline State ---

def merge_lists(left: list, right: list) -> list:
    """Reducer that merges two lists (used by LangGraph annotations)."""
    return left + right


class PipelineState(BaseModel):
    """Complete state flowing through the LangGraph pipeline."""
    raw_logs: str = ""
    file_name: str = ""
    log_entries: list[LogEntry] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    cookbook: str = ""
    jira_tickets: list[JiraTicket] = Field(default_factory=list)
    notification: SlackNotification | None = None
    causal_chains: list[CausalChain] = Field(default_factory=list)
    risk_predictions: list[RiskPrediction] = Field(default_factory=list)
    current_agent: str = ""
    error: str = ""
