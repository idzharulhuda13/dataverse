"""
Tests for all DataVerse Pydantic schemas.
Verifies validation, defaults, computed properties, and serialization.
"""
import pytest
from datetime import datetime
from dataverse_agent.schemas import (
    UsageMetadata,
    TraceEvent,
    SessionUsage,
    SandboxResult,
    DataLoadResult,
    TableRegistryEntry,
    SlashCommandAction,
    SlashCommandResult,
    EnricherResult,
    InfographicMetric,
    CalculatedMetric,
    InfographicContent,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UsageMetadata
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestUsageMetadata:
    def test_defaults(self):
        m = UsageMetadata()
        assert m.prompt_token_count == 0
        assert m.candidates_token_count == 0
        assert m.total_token_count == 0

    def test_explicit_values(self):
        m = UsageMetadata(prompt_token_count=100, candidates_token_count=50, total_token_count=150)
        assert m.prompt_token_count == 100
        assert m.candidates_token_count == 50
        assert m.total_token_count == 150

    def test_model_validate_from_dict(self):
        m = UsageMetadata.model_validate({"prompt_token_count": 10, "candidates_token_count": 5})
        assert m.prompt_token_count == 10
        assert m.candidates_token_count == 5

    def test_type_coercion(self):
        """Pydantic v2 coerces compatible types."""
        m = UsageMetadata(prompt_token_count="200")  # type: ignore
        assert m.prompt_token_count == 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TraceEvent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTraceEvent:
    def test_defaults(self):
        event = TraceEvent()
        assert event.event_type == "thought"
        assert event.agent_name == "orchestrator"
        assert event.detail == ""
        assert event.metadata == {}
        assert isinstance(event.timestamp, datetime)

    def test_custom_event(self):
        event = TraceEvent(
            event_type="tool_call",
            agent_name="visual_analyst",
            detail="Calling create_visualization",
            metadata={"tool": "viz"},
        )
        assert event.event_type == "tool_call"
        assert event.agent_name == "visual_analyst"
        assert event.metadata == {"tool": "viz"}

    def test_serializable(self):
        event = TraceEvent(event_type="start", detail="Hello")
        d = event.model_dump()
        assert "timestamp" in d
        assert d["event_type"] == "start"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SessionUsage
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSessionUsage:
    def test_defaults(self):
        u = SessionUsage(session_id="test-123")
        assert u.api_calls == 0
        assert u.turns == 0
        assert u.total_tokens == 0
        assert u.estimated_cost_usd == pytest.approx(0.0)
        assert u.trace == []

    def test_record_api_call_from_model(self):
        u = SessionUsage(session_id="s1")
        meta = UsageMetadata(prompt_token_count=1000, candidates_token_count=500)
        u.record_api_call(meta)
        assert u.api_calls == 1
        assert u.input_tokens == 1000
        assert u.output_tokens == 500

    def test_record_api_call_from_dict(self):
        u = SessionUsage(session_id="s1")
        u.record_api_call({"prompt_token_count": 200, "candidates_token_count": 100})
        assert u.api_calls == 1
        assert u.input_tokens == 200

    def test_total_tokens(self):
        u = SessionUsage(session_id="s1", input_tokens=500, output_tokens=300, image_tokens=100)
        assert u.total_tokens == 900

    def test_estimated_cost(self):
        u = SessionUsage(session_id="s1", input_tokens=1_000_000, output_tokens=1_000_000)
        expected = 0.075 + 0.30
        assert u.estimated_cost_usd == pytest.approx(expected)

    def test_record_turn(self):
        u = SessionUsage(session_id="s1")
        u.record_turn()
        u.record_turn()
        assert u.turns == 2

    def test_record_trace(self):
        u = SessionUsage(session_id="s1")
        u.record_trace("tool_call", "agent", "detail", {"key": "val"})
        assert len(u.trace) == 1
        assert u.trace[0].event_type == "tool_call"

    def test_clear_trace(self):
        u = SessionUsage(session_id="s1")
        u.record_trace("start", "orchestrator", "start")
        u.clear_trace()
        assert u.trace == []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SandboxResult
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSandboxResult:
    def test_defaults(self):
        r = SandboxResult()
        assert r.output is None
        assert r.dataframe is None
        assert r.error is None
        assert r.blocked is False
        assert r.blocked_reason is None

    def test_blocked_result(self):
        r = SandboxResult(blocked=True, blocked_reason="No os allowed")
        assert r.blocked
        assert r.blocked_reason == "No os allowed"

    def test_error_result(self):
        r = SandboxResult(error="ZeroDivisionError: division by zero")
        assert r.error is not None
        assert not r.blocked

    def test_success_with_output(self):
        r = SandboxResult(output="Hello!")
        assert r.output == "Hello!"
        assert r.error is None
        assert not r.blocked

    def test_accepts_dataframe(self):
        import pandas as pd
        df = pd.DataFrame({"a": [1, 2]})
        r = SandboxResult(dataframe=df)
        assert r.dataframe is not None
        assert len(r.dataframe) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DataLoadResult
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDataLoadResult:
    def test_ok_property_success(self):
        import pandas as pd
        r = DataLoadResult(df=pd.DataFrame({"x": [1]}))
        assert r.ok is True
        assert r.error is None

    def test_ok_property_error(self):
        r = DataLoadResult(error="File too large.")
        assert r.ok is False
        assert r.df is None

    def test_defaults_are_none(self):
        r = DataLoadResult()
        assert r.df is None
        assert r.error is None
        assert r.ok is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TableRegistryEntry
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTableRegistryEntry:
    def test_basic_construction(self):
        entry = TableRegistryEntry(
            table_id="mrt_sales",
            display_name="Sales",
            description="Sales data",
            db_schema="main",
            icon="🛒",
            grain="One row per order",
            approx_rows="1000",
            columns=10,
            tags=["sales"],
        )
        assert entry.table_id == "mrt_sales"
        assert entry.tags == ["sales"]

    def test_default_tags(self):
        entry = TableRegistryEntry(
            table_id="t1", display_name="T1", description="desc",
            db_schema="s", icon="X", grain="g", approx_rows="1", columns=1,
        )
        assert entry.tags == []

    def test_registry_import(self):
        from models.duckdb_connector import TABLE_REGISTRY
        assert "mrt_sales" in TABLE_REGISTRY
        entry = TABLE_REGISTRY["mrt_sales"]
        assert isinstance(entry, TableRegistryEntry)
        assert entry.display_name == "Chocolate Sales — Transactions"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SlashCommandResult
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestSlashCommandResult:
    def test_not_handled(self):
        r = SlashCommandResult(handled=False)
        assert not r.handled
        assert r.text is None
        assert r.action is None

    def test_text_response(self):
        r = SlashCommandResult(handled=True, text="Help text here")
        assert r.handled
        assert r.text == "Help text here"
        assert r.action is None

    def test_action_response(self):
        r = SlashCommandResult(
            handled=True,
            action=SlashCommandAction(action="export", args=["arg1"]),
        )
        assert r.handled
        assert r.text is None
        assert r.action.action == "export"
        assert r.action.args == ["arg1"]

    def test_action_defaults(self):
        a = SlashCommandAction(action="clear")
        assert a.args == []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EnricherResult
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestEnricherResult:
    def test_construction(self):
        r = EnricherResult(
            enriched_query="Show revenue by region as a bar chart",
            usage=UsageMetadata(prompt_token_count=100, candidates_token_count=50),
        )
        assert r.enriched_query == "Show revenue by region as a bar chart"
        assert r.usage.prompt_token_count == 100

    def test_serializable(self):
        r = EnricherResult(
            enriched_query="query",
            usage=UsageMetadata(),
        )
        d = r.model_dump()
        assert "enriched_query" in d
        assert "usage" in d


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Infographic Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestInfographicModels:
    def test_infographic_metric_defaults(self):
        m = InfographicMetric(label="Revenue", column="revenue_eur")
        assert m.op == "count"

    def test_infographic_metric_custom_op(self):
        m = InfographicMetric(label="Total Revenue ($)", column="revenue_eur", op="sum")
        assert m.op == "sum"

    def test_calculated_metric(self):
        m = CalculatedMetric(label="Total Revenue", value=1_500_000.0, op="sum")
        assert m.value == 1_500_000.0

    def test_calculated_metric_none_value(self):
        m = CalculatedMetric(label="N/A Metric", value=None)
        assert m.value is None

    def test_infographic_content_defaults(self):
        c = InfographicContent()
        assert c.infographic_title == "Data Analysis Overview"
        assert c.infographic_subtitle == "Key insights from your dataset"
        assert c.chart_headlines == []
        assert c.key_takeaways == []
        assert c.metrics == []
        assert c.calculated_metrics == []

    def test_infographic_content_full(self):
        c = InfographicContent(
            infographic_title="Sales Dashboard",
            infographic_subtitle="Q4 Results",
            chart_headlines=["Chart 1", "Chart 2"],
            key_takeaways=["Revenue grew 15%", "West region leads"],
            conclusion="Strong quarter overall.",
            metrics=[InfographicMetric(label="Revenue", column="rev", op="sum")],
            calculated_metrics=[CalculatedMetric(label="Revenue", value=5e6, op="sum")],
        )
        assert len(c.chart_headlines) == 2
        assert len(c.calculated_metrics) == 1
        assert c.calculated_metrics[0].value == 5e6

    def test_infographic_content_serializable(self):
        c = InfographicContent(infographic_title="Test")
        d = c.model_dump()
        assert d["infographic_title"] == "Test"
        assert "calculated_metrics" in d
