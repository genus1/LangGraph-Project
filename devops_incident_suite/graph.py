"""LangGraph orchestrator — defines the directed agent pipeline."""

from __future__ import annotations

import operator
import os
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents import (
    log_classifier, remediation, cookbook, jira_ticket, notification,
    root_cause, predictive_risk,
)


load_dotenv()


# --- State with reducers for parallel fan-out ---

def _last_value(a, b):
    """Reducer that keeps the latest non-empty value."""
    return b if b else a


def _merge_lists(a: list, b: list) -> list:
    """Reducer that merges two lists."""
    return (a or []) + (b or [])


class PipelineState(TypedDict):
    raw_logs: str
    file_name: str
    log_entries: Annotated[list, _merge_lists]
    issues: Annotated[list, _merge_lists]
    cookbook: Annotated[str, _last_value]
    jira_tickets: Annotated[list, _merge_lists]
    notification: Annotated[Any, _last_value]
    causal_chains: Annotated[list, _merge_lists]
    risk_predictions: Annotated[list, _merge_lists]
    current_agent: Annotated[str, _last_value]
    error: Annotated[str, _last_value]


# --- LLM Factory ---

def get_llm():
    """Create the LLM instance based on environment configuration.

    Supports: openai, anthropic, openrouter (default).
    """
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.2,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=0.2,
        )

    # Default: OpenRouter (OpenAI-compatible API)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.2,
    )


# --- Shared LLM instance ---

_llm = None


def _get_shared_llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


# --- Node wrappers ---

def log_classifier_node(state: dict) -> dict:
    return log_classifier.run(state, _get_shared_llm())


def remediation_node(state: dict) -> dict:
    return remediation.run(state, _get_shared_llm())


def cookbook_node(state: dict) -> dict:
    return cookbook.run(state, _get_shared_llm())


def jira_ticket_node(state: dict) -> dict:
    return jira_ticket.run(state, _get_shared_llm())


def notification_node(state: dict) -> dict:
    return notification.run(state, _get_shared_llm())


def root_cause_node(state: dict) -> dict:
    return root_cause.run(state, _get_shared_llm())


def predictive_risk_node(state: dict) -> dict:
    return predictive_risk.run(state, _get_shared_llm())


# --- Graph Definition ---

def build_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline.

    Flow:
        log_classifier → remediation → [cookbook, jira_ticket, root_cause, predictive_risk] (parallel)
                                        cookbook ──────────→ END
                                        jira_ticket ──────→ END
                                        root_cause ───────→ END
                                        predictive_risk ──→ notification → END
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("log_classifier", log_classifier_node)
    graph.add_node("remediation", remediation_node)
    graph.add_node("cookbook", cookbook_node)
    graph.add_node("jira_ticket", jira_ticket_node)
    graph.add_node("root_cause", root_cause_node)
    graph.add_node("predictive_risk", predictive_risk_node)
    graph.add_node("notification", notification_node)

    # Define edges: sequential then fan-out
    graph.set_entry_point("log_classifier")
    graph.add_edge("log_classifier", "remediation")

    # Fan-out from remediation to four parallel agents
    graph.add_edge("remediation", "cookbook")
    graph.add_edge("remediation", "jira_ticket")
    graph.add_edge("remediation", "root_cause")
    graph.add_edge("remediation", "predictive_risk")

    # Notification runs after predictive_risk (needs risk predictions for Slack)
    graph.add_edge("predictive_risk", "notification")

    # All converge to END
    graph.add_edge("cookbook", END)
    graph.add_edge("jira_ticket", END)
    graph.add_edge("root_cause", END)
    graph.add_edge("notification", END)

    return graph.compile()


def run_pipeline(raw_logs: str, file_name: str = "upload") -> dict:
    """Run the full pipeline and return the final state."""
    global _llm
    _llm = None  # Reset to pick up any env changes

    compiled = build_graph()
    initial_state = {
        "raw_logs": raw_logs,
        "file_name": file_name,
        "log_entries": [],
        "issues": [],
        "cookbook": "",
        "jira_tickets": [],
        "notification": None,
        "causal_chains": [],
        "risk_predictions": [],
        "current_agent": "",
        "error": "",
    }

    result = compiled.invoke(initial_state)
    return result
