"""
DataVerse Pydantic Schemas — Centralized Type Definitions

All shared data models live here to avoid circular imports.
Each module imports only the schemas it needs from this file.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# USAGE & TRACING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class UsageMetadata(BaseModel):
    """Token usage from a single Gemini API call."""
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0


class TraceEvent(BaseModel):
    """A single step in the agent's thought process or tool usage."""
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str = "thought"  # "thought" | "start" | "tool_call" | "vision_start" | "vision_complete" | "complete"
    agent_name: str = "orchestrator"
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionUsage(BaseModel):
    """Tracks token usage and cost for a single DataVerse session."""
    session_id: str
    api_calls: int = 0
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    image_tokens: int = 0
    error_count: int = 0
    retry_count: int = 0
    trace: list[TraceEvent] = Field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.image_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """
        Rough estimate based on Gemini Flash pricing:
        - $0.075 / 1M input tokens
        - $0.30 / 1M output tokens
        """
        INPUT_COST = 0.075
        OUTPUT_COST = 0.30
        return (self.input_tokens / 1_000_000) * INPUT_COST + \
               (self.output_tokens / 1_000_000) * OUTPUT_COST

    def record_api_call(self, usage: UsageMetadata | dict) -> None:
        """Record usage from a single API request. Accepts UsageMetadata or raw dict."""
        if isinstance(usage, dict):
            usage = UsageMetadata.model_validate(usage)
        self.api_calls += 1
        self.input_tokens += usage.prompt_token_count
        self.output_tokens += usage.candidates_token_count

    def record_turn(self) -> None:
        """Record a completed conversation turn (User + Assistant)."""
        self.turns += 1

    def record_error(self) -> None:
        """Record a technical error occurrence."""
        self.error_count += 1

    def record_retry(self) -> None:
        """Record a silent agent retry attempt."""
        self.retry_count += 1

    def record_trace(
        self,
        event_type: str,
        agent_name: str,
        detail: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add an event to the activity trace."""
        self.trace.append(TraceEvent(
            event_type=event_type,
            agent_name=agent_name,
            detail=detail,
            metadata=metadata or {},
        ))

    def clear_trace(self) -> None:
        """Clear trace history (e.g., at start of new request)."""
        self.trace = []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SANDBOX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SandboxResult(BaseModel):
    """Result of a sandboxed code execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    output: Optional[str] = None
    dataframe: Optional[Any] = None   # pd.DataFrame — Any to avoid import cycle
    display_df: Optional[Any] = None  # pd.DataFrame
    figure: Optional[Any] = None       # matplotlib.figure.Figure
    error: Optional[str] = None
    blocked: bool = False
    blocked_reason: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA LOADING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DataLoadResult(BaseModel):
    """Result of loading a data file into a DataFrame."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    df: Optional[Any] = None    # pd.DataFrame
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.df is not None and self.error is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DUCKDB REGISTRY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TableRegistryEntry(BaseModel):
    """Metadata for a registered DuckDB warehouse table."""
    table_id: str
    display_name: str
    description: str
    db_schema: str          # renamed from 'schema' to avoid shadowing BaseModel.schema()
    icon: str
    grain: str
    approx_rows: str
    columns: int
    tags: list[str] = Field(default_factory=list)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SLASH COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SlashCommandAction(BaseModel):
    """A special UI-level action triggered by a slash command."""
    action: str
    args: list[str] = Field(default_factory=list)


class SlashCommandResult(BaseModel):
    """Return type of handle_slash_command()."""
    handled: bool
    text: Optional[str] = None       # Text response to display in chat
    action: Optional[SlashCommandAction] = None  # Special UI action


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENRICHER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EnricherResult(BaseModel):
    """Return type of enrich_query()."""
    enriched_query: str
    usage: UsageMetadata


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INFOGRAPHIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class InfographicMetric(BaseModel):
    """An agent-suggested metric definition (from JSON response)."""
    label: str
    column: str
    op: str = "count"  # "sum" | "mean" | "count" | "nunique" | "max" | "min"


class CalculatedMetric(BaseModel):
    """A metric with its deterministically calculated value."""
    label: str
    value: Optional[Any] = None
    op: str = "count"


class InfographicContent(BaseModel):
    """Structured narrative content generated by the agent for the infographic."""
    infographic_title: str = "Data Analysis Overview"
    infographic_subtitle: str = "Key insights from your dataset"
    chart_headlines: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    conclusion: str = "Further analysis recommended to uncover deeper trends."
    metrics: list[InfographicMetric] = Field(default_factory=list)
    calculated_metrics: list[CalculatedMetric] = Field(default_factory=list)
