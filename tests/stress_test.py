"""
DataVerse Agent Stress Test
============================
Automated test harness that runs analytical questions through the full
agent pipeline (Orchestrator → Visual Analyst) WITHOUT Streamlit.

Usage:
    uv run python tests/stress_test.py [--dataset path/to/file.csv] [--output-dir tests/stress_results]

What it does:
    1. Loads a CSV dataset
    2. Initializes the ADK Runner with the root_agent
    3. Runs each stress test question sequentially
    4. Captures: response text, generated figures (saved as PNG), errors, timing
    5. Verifies dataset integrity after each question (detects the final_df bug)
    6. Generates a Markdown report at the end

The test questions are defined in STRESS_TEST_QUESTIONS and can be customized.
"""

import argparse
import asyncio
import io
import os
import re as _re
import sys
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import pandas as pd
from dotenv import load_dotenv

# ── Project imports ──────────────────────────────────────────────────────────
# Add project root to path so we can import from dataverse_agent/models
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.utils import load_dataframe, extract_non_code_text
from models.duckdb_connector import load_table
from dataverse_agent.agent import get_orchestrator
from dataverse_agent.tools import set_session_context, get_session_figures, get_final_df, get_session_data_summary

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class StressTestConfig:
    """Central configuration for the stress test suite."""
    # Data & Paths
    default_dataset: str = "dbt/dataverse/dataverse_warehouse.duckdb"
    default_output_dir: str = "tests/stress_results"
    duckdb_table_name: str = "mrt_sales"

    # Optimization
    skip_cleaning: bool = True  # Set to False if you want to run the cleaning agent by default

    # API & Rate Limiting
    inter_question_delay: int = 5  # seconds
    max_retries: int = 3
    retry_base_delay: int = 45  # seconds

    # Model Settings
    default_model: str = "gemini-3.1-flash-lite-preview"


# Global configuration instance
CONFIG = StressTestConfig()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STRESS TEST QUESTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class TestQuestion:
    """A single stress test question with expected outcomes."""
    id: str
    question: str
    expected_chart_type: str
    checks: list[str] = field(default_factory=list)  # What to verify in the output


# Default questions targeting the Chocolate Sales (mrt_sales) dataset
STRESS_TEST_QUESTIONS: list[TestQuestion] = [
    TestQuestion(
        id="H1",
        question="Analyze store profitability. Use the column that best represents the 'bottom line' profit margin, but only for stores that are in the 'Top 50%' of revenue generators. Show this as a ranked bar chart with mean profit margin labeled.",
        expected_chart_type="bar",
        checks=["chart_generated", "dataset_intact"],
    ),
    TestQuestion(
        id="H2",
        question="Identify 'Dead Brands'—brands that had revenue in the first 3 months of the dataset (June-August 2024) but zero revenue in the last available month (December 2024). Visualize the historical monthly revenue trend for these specific brands as a line chart.",
        expected_chart_type="line",
        checks=["chart_generated", "dataset_intact"],
    ),
    TestQuestion(
        id="H3",
        question="A data entry error caused some 'discount' values greater than 0.5 to be recorded as text (e.g., '60% OFF') in the 'discount_label' column while 'discount' shows 0. Calculate the 'True Net Revenue' (Revenue - (Revenue * Correct Discount)) by reconciling both columns. Show the top 5 brands by True Net Revenue in a bar chart.",
        expected_chart_type="bar",
        checks=["chart_generated", "dataset_intact"],
    ),
    TestQuestion(
        id="H4",
        question="Identify 'Efficiency Leaders': Brands where the average `revenue_per_unit` is a statistical outlier (Z-score > 1.5). For these leaders, visualize their monthly revenue trend over the entire period to check for consistency.",
        expected_chart_type="line",
        checks=["chart_generated", "dataset_intact"],
    ),
    TestQuestion(
        id="H5",
        question="Compare 'Weekend Warrior' brands (those with the highest revenue share on weekends) against 'Weekday Staples'. Generate a slope chart comparing the average daily revenue share between 'Weekend' and 'Weekday' for the top 5 brands with the highest weekend share.",
        expected_chart_type="slope",
        checks=["chart_generated", "dataset_intact"],
    ),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST RESULT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class TestResult:
    """Result of running a single stress test question."""
    question: TestQuestion
    response_text: str = ""
    insight_text: str = ""
    figure_path: Optional[str] = None
    enriched_question: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    chart_generated: bool = False
    error: Optional[str] = None
    duration_seconds: float = 0.0

    # Usage Metrics
    api_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    turns: int = 0

    # Dataset integrity checks
    df_columns_before: list[str] = field(default_factory=list)
    df_columns_after: list[str] = field(default_factory=list)
    df_rows_before: int = 0
    df_rows_after: int = 0
    dataset_intact: bool = True

    # Specific check results
    check_results: dict[str, bool | str] = field(default_factory=dict)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class StressTestRunner:
    """Runs stress test questions through the ADK agent pipeline."""

    def __init__(
        self,
        dataset_path: str,
        output_dir: str,
        inter_question_delay: int = CONFIG.inter_question_delay,
        skip_cleaning: bool = False,
    ):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir)
        self.charts_dir = self.output_dir / "charts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.skip_cleaning = skip_cleaning

        # Suppress verbose ADK framework logging
        logging.getLogger("google.adk").setLevel(logging.ERROR)

        # Load dataset
        print(f"📂 Loading dataset: {self.dataset_path}")
        if self.dataset_path.suffix.lower() == ".duckdb":
            print(f"   🗄️ DuckDB Warehouse detected. Loading '{CONFIG.duckdb_table_name}'...")
            self.original_df = load_table(CONFIG.duckdb_table_name)
        else:
            with open(self.dataset_path, "rb") as f:
                self.original_df, error = load_dataframe(f)
            if error:
                raise RuntimeError(f"Failed to load dataset: {error}")
        print(f"   ✅ Loaded: {len(self.original_df)} rows × {len(self.original_df.columns)} columns")
        print(f"   Columns: {list(self.original_df.columns)}")

        # Working copy (simulates st.session_state.modified_df)
        self.working_df = self.original_df.copy()

        # Initialize ADK Runner
        self.session_service = InMemorySessionService()
        is_enterprise = self.dataset_path.suffix.lower() == ".duckdb"
        self.runner = Runner(
            app_name="dataverse_stress_test",
            agent=get_orchestrator(is_enterprise),
            session_service=self.session_service,
            auto_create_session=True,
        )
        self.session_id = "stress-test-session"
        self.inter_question_delay = inter_question_delay

        self.results: list[TestResult] = []

    async def _send_to_agent(self, prompt: str) -> tuple[str, list[dict], dict]:
        """Send a prompt to the agent with retry-on-rate-limit.
        Returns: (text, tool_calls, usage_stats)
        """
        usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
        for attempt in range(CONFIG.max_retries + 1):
            try:
                final_text = ""
                tool_calls = []
                async for event in self.runner.run_async(
                    user_id="stress_tester",
                    session_id=self.session_id,
                    new_message=types.Content(parts=[types.Part.from_text(text=prompt)]),
                ):
                    # Extract usage metadata
                    if hasattr(event, 'usage_metadata') and event.usage_metadata:
                        usage["input_tokens"] += event.usage_metadata.prompt_token_count
                        usage["output_tokens"] += event.usage_metadata.candidates_token_count
                        # We count one API call per response chunk that carries usage
                        # (Usually ADK sends usage at the end of a completion)
                        usage["api_calls"] += 1

                    if event.content and event.content.parts:
                        for p in event.content.parts:
                            if p.text:
                                final_text += p.text
                            if hasattr(p, "function_call") and p.function_call:
                                args_dict = dict(p.function_call.args) if hasattr(p.function_call, "args") and p.function_call.args else {}
                                tool_calls.append({"name": p.function_call.name, "args": args_dict})
                return final_text, tool_calls, usage
            except Exception as e:
                if "429" in str(e) and attempt < CONFIG.max_retries:
                    delay = CONFIG.retry_base_delay * (attempt + 1)
                    print(f"   ⏳ Rate limited. Retrying in {delay}s (attempt {attempt + 1}/{CONFIG.max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    raise

    async def _generate_insight(self, figure) -> tuple[str, dict]:
        """Second-pass: send chart image to agent for insight generation."""
        img_buf = io.BytesIO()
        figure.savefig(img_buf, format="png")
        img_bytes = img_buf.getvalue()

        # Grounding context (actual data metrics) for the Vision agent
        data_grounding_summary = get_session_data_summary()
        
        insight_prompt = (
            "Provide a focused data insight for this chart based on the summary:\n"
            f"{data_grounding_summary}\n\n"
            "Use the strict framework: **📊 Observation** and **💡 Interpretation**."
        )

        usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}
        for attempt in range(CONFIG.max_retries + 1):
            try:
                text = ""
                async for event in self.runner.run_async(
                    user_id="stress_tester",
                    session_id=self.session_id,
                    new_message=types.Content(parts=[
                        types.Part.from_text(text=insight_prompt),
                        types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    ]),
                ):
                    if hasattr(event, 'usage_metadata') and event.usage_metadata:
                        usage["input_tokens"] += event.usage_metadata.prompt_token_count
                        usage["output_tokens"] += event.usage_metadata.candidates_token_count
                        usage["api_calls"] += 1

                    if event.content and event.content.parts:
                        for p in event.content.parts:
                            if p.text:
                                text += p.text
                return extract_non_code_text(text), usage
            except Exception as e:
                if "429" in str(e) and attempt < CONFIG.max_retries:
                    delay = CONFIG.retry_base_delay * (attempt + 1)
                    print(f"   ⏳ Insight rate limited. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    raise

    def _run_checks(self, result: TestResult, figure) -> None:
        """Run validation checks on the test result."""
        checks = result.question.checks

        for check in checks:
            if check == "chart_generated":
                result.check_results[check] = result.chart_generated

            elif check == "dataset_intact":
                cols_before = set(result.df_columns_before)
                cols_after = set(result.df_columns_after)
                intact = (
                    cols_before == cols_after
                    and result.df_rows_before == result.df_rows_after
                )
                result.check_results[check] = intact
                result.dataset_intact = intact
                if not intact:
                    lost_cols = cols_before - cols_after
                    gained_cols = cols_after - cols_before
                    detail = []
                    if lost_cols:
                        detail.append(f"Lost columns: {lost_cols}")
                    if gained_cols:
                        detail.append(f"Gained columns: {gained_cols}")
                    if result.df_rows_before != result.df_rows_after:
                        detail.append(f"Row count changed: {result.df_rows_before} → {result.df_rows_after}")
                    result.check_results[check + "_detail"] = "; ".join(detail)

            elif check == "all_columns_present":
                original_cols = set(self.original_df.columns)
                current_cols = set(result.df_columns_after)
                result.check_results[check] = original_cols.issubset(current_cols)

            elif check == "no_hallucination":
                # Check if response text contains specific numbers before chart
                # (Heuristic: look for large numbers in the text)
                import re
                numbers_in_text = re.findall(r'\d{4,}', result.response_text)
                has_hallucinated_numbers = len(numbers_in_text) > 2  # Allow dates like 2018
                result.check_results[check] = not has_hallucinated_numbers

            elif check == "bar_labels_valid":
                # Check if any bar label shows "0.8" (the horizontal bar bug)
                if figure:
                    import matplotlib.pyplot as plt
                    bad_labels = False
                    for ax in figure.get_axes():
                        for text in ax.texts:
                            if text.get_text().strip() in ("0.8", "0.9", "0.7"):
                                bad_labels = True
                                break
                    result.check_results[check] = not bad_labels
                else:
                    result.check_results[check] = "N/A (no figure)"

            elif check == "estimator_sum":
                # Heuristic: check if response/insight mentions "total" or "sum"
                combined = (result.response_text + " " + result.insight_text).lower()
                result.check_results[check] = "total" in combined or "sum" in combined or "aggregate" in combined

            elif check == "no_error_bars_on_sum":
                # Visual check — hard to automate perfectly, mark as manual
                result.check_results[check] = "MANUAL_CHECK"

            elif check == "bars_sorted":
                result.check_results[check] = "MANUAL_CHECK"

            elif check == "year_axis_integers":
                result.check_results[check] = "MANUAL_CHECK"

            elif check == "top_n_filtering":
                # Check if exactly 5 items are shown (from bar count or response text)
                result.check_results[check] = "top 5" in result.response_text.lower() or "top five" in result.response_text.lower()

            elif check == "month_axis_labels":
                result.check_results[check] = "MANUAL_CHECK"

            elif check == "min_points_2":
                if figure:
                    # Check if there are at least 2 data points (either in the label or lines)
                    has_min_points = False
                    for ax in figure.get_axes():
                        for line in ax.get_lines():
                            if len(line.get_xdata()) >= 2:
                                has_min_points = True
                                break
                    result.check_results[check] = has_min_points
                else:
                    result.check_results[check] = "N/A (no figure)"

            elif check == "max_points_1000":
                if figure:
                    has_too_many = False
                    for ax in figure.get_axes():
                        # Count collections (scatter plots usually use PathCollection)
                        from matplotlib.collections import PathCollection
                        for coll in ax.collections:
                            if isinstance(coll, PathCollection):
                                if len(coll.get_offsets()) > 1000:
                                    has_too_many = True
                                    break
                    result.check_results[check] = not has_too_many
                else:
                    result.check_results[check] = "N/A (no figure)"

            else:
                result.check_results[check] = "UNKNOWN_CHECK"

    async def run_question(self, question: TestQuestion) -> TestResult:
        """Run a single stress test question through the full pipeline."""
        result = TestResult(question=question)

        # Snapshot dataset state BEFORE
        result.df_columns_before = list(self.working_df.columns)
        result.df_rows_before = len(self.working_df)

        # Set up thread-local context (same as Streamlit does)
        set_session_context(self.working_df)

        print(f"\n{'='*70}")
        print(f"🧪 {question.id}: {question.question}")
        print(f"{'='*70}")

        start_time = time.time()

        try:
            # 1. Generate dataset context
            buf = io.StringIO()
            self.working_df.info(buf=buf)
            ds_info = buf.getvalue()
            ds_head = self.working_df.head(10).to_string()

            # 2. Enrich the query
            print(f"   ✨ Enriching query...")
            from dataverse_agent.agents.enricher import enrich_query
            try:
                enrich_result = enrich_query(question.question, self.working_df)
                enriched_question = enrich_result.enriched_query
                result.enriched_question = enriched_question
                print(f"      Enriched: {enriched_question}")
                
                # Capture enrichment usage
                result.api_calls += 1
                result.turns += 1
                result.input_tokens += enrich_result.usage.prompt_token_count
                result.output_tokens += enrich_result.usage.candidates_token_count
            except Exception as e:
                print(f"      ⚠️ Enrichment failed: {e}. Using raw query.")
                enriched_question = question.question

            # 3. Build final prompt
            llm_prompt = enriched_question

            # 4. Send to agent
            print(f"   🤖 Sending to Orchestrator...")
            response_text, tool_calls, usage = await self._send_to_agent(llm_prompt)
            result.tool_calls = tool_calls
            result.response_text = extract_non_code_text(response_text)
            
            # Record main agent usage
            result.api_calls += usage["api_calls"]
            result.input_tokens += usage["input_tokens"]
            result.output_tokens += usage["output_tokens"]
            result.turns += 1

            # Retrieve generated figures
            figures = get_session_figures()
            figure = figures[-1] if figures else None
            result.chart_generated = figure is not None

            # Check if cleaning agent produced a persisted final_df
            final_df = get_final_df()
            if final_df is not None:
                # Sanity guard (mirroring streamlit_agent_dashboard.py):
                # Only persist if it looks like a full-dataset transformation.
                # A filtered subset (e.g. top-5 rows) should NEVER overwrite the main df.
                is_safe = (
                    self.original_df is None
                    or set(self.original_df.columns).issubset(set(final_df.columns))
                    or len(final_df.columns) >= len(self.working_df.columns)
                )
                if is_safe:
                    self.working_df = final_df
                    set_session_context(final_df)
                else:
                    # Visual Analyst produced a temporary filtered subset — discard it.
                    pass

            # Save figure if generated
            if figure:
                fig_path = self.charts_dir / f"{question.id}_chart.png"
                figure.savefig(str(fig_path), dpi=150, bbox_inches="tight")
                result.figure_path = str(fig_path)
                print(f"   📊 Chart saved: {fig_path}")

                # Second pass: generate insight
                try:
                    result.insight_text, vision_usage = await self._generate_insight(figure)
                    result.api_calls += vision_usage["api_calls"]
                    result.input_tokens += vision_usage["input_tokens"]
                    result.output_tokens += vision_usage["output_tokens"]
                    result.turns += 1
                except Exception as e:
                    result.insight_text = f"[Insight generation failed: {e}]"
            else:
                print(f"   ⚠️  No chart generated!")

        except Exception as e:
            result.error = str(e)
            print(f"   ❌ Error: {e}")

        result.duration_seconds = time.time() - start_time

        # Snapshot dataset state AFTER
        result.df_columns_after = list(self.working_df.columns)
        result.df_rows_after = len(self.working_df)

        # Run validation checks
        self._run_checks(result, figure if result.chart_generated else None)

        # Print quick summary
        if result.dataset_intact:
            print(f"   ✅ Dataset intact: {result.df_rows_after} rows × {len(result.df_columns_after)} cols")
        else:
            detail = result.check_results.get("dataset_intact_detail", "")
            print(f"   🚨 DATASET CORRUPTED! {detail}")

        print(f"   ⏱️  Duration: {result.duration_seconds:.1f}s")
        print(f"   Checks: {result.check_results}")

        self.results.append(result)
        return result

    async def run_all(self, questions: list[TestQuestion] | None = None) -> list[TestResult]:
        """Run all stress test questions sequentially."""
        questions = questions or STRESS_TEST_QUESTIONS

        print(f"\n{'━'*70}")
        print(f"🚀 DataVerse Stress Test — {len(questions)} questions")
        print(f"   Dataset: {self.dataset_path}")
        print(f"   Output:  {self.output_dir}")
        print(f"   Model:   {os.getenv('GEMINI_MODEL', CONFIG.default_model)}")
        print(f"   Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'━'*70}")

        # Initial Cleaning Phase (to mirror Streamlit behavior)
        if not self.skip_cleaning:
            print(f"\n   🧹 Running Initial Cleaning Phase...")
            cleaning_prompt = (
                "[INITIAL-CLEANING]\n\n"
                "[System Context]: The user just uploaded a new dataset. "
                "Analyze the dataset for missing values, duplicate rows, and incorrect data types. "
                "Apply necessary corrections (e.g., filling nulls with median, dropping duplicates) "
                "and SAVE the cleaned result to `final_df` so it persists for the user. "
                "Report a concise summary of what was cleaned."
            )
            set_session_context(self.working_df)
            try:
                cleaning_response, _ = await self._send_to_agent(cleaning_prompt)
                final_df = get_final_df()
                if final_df is not None:
                    self.working_df = final_df
                    # The baseline original_df should also reflect the cleaned version
                    self.original_df = final_df.copy()
                    print(f"   ✨ Cleaning complete. New shape: {self.working_df.shape[0]} rows × {self.working_df.shape[1]} cols")
                    print(f"   Agent summary: {extract_non_code_text(cleaning_response).strip()[:200]}...")
                else:
                    print("   ⚠️ Cleaning phase returned no new DataFrame.")
            except Exception as e:
                print(f"   ❌ Errror during Initial Cleaning Phase: {e}")
        else:
            print(f"\n   ⏩ Skipping Initial Cleaning Phase (data source is already clean).")

        # Track global usage for total report
        self.total_usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0, "turns": 0}

        for i, q in enumerate(questions):
            # Inter-question delay to avoid rate limiting
            if i > 0 and self.inter_question_delay > 0:
                print(f"\n   ⏳ Waiting {self.inter_question_delay}s before next question (rate limit cooldown)...")
                await asyncio.sleep(self.inter_question_delay)

            res = await self.run_question(q)
            
            # Aggregate totals
            self.total_usage["api_calls"] += res.api_calls
            self.total_usage["input_tokens"] += res.input_tokens
            self.total_usage["output_tokens"] += res.output_tokens
            self.total_usage["turns"] += res.turns

            # Check if dataset was corrupted — if so, note it but continue
            # (to see how subsequent questions handle the broken state)
            if not self.results[-1].dataset_intact:
                print(f"\n   ⚠️  Dataset corrupted after {q.id}! Subsequent questions may fail.")
                print(f"   Continuing to test resilience...\n")

        # Generate report
        self._generate_report()

        return self.results

    def _generate_report(self) -> None:
        """Generate a Markdown report of all test results."""
        report_path = self.output_dir / "stress_test_report.md"

        lines = [
            "# DataVerse Stress Test Report",
            "",
            f"> **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> **Dataset:** `{self.dataset_path.name}` ({len(self.original_df)} rows × {len(self.original_df.columns)} cols)",
            f"> **Model:** `{os.getenv('GEMINI_MODEL', CONFIG.default_model)}`",
            "",
            "---",
            "",
            "## Scorecard",
            "",
            "| # | Question | Chart? | Dataset Intact? | Duration | Usage (Calls/Tokens) | Checks |",
            "|---|----------|--------|-----------------|----------|----------------------|--------|",
        ]

        total_pass = 0
        total_fail = 0

        for r in self.results:
            chart_icon = "✅" if r.chart_generated else "❌"
            intact_icon = "✅" if r.dataset_intact else "🚨"

            # Summarize checks
            passed = sum(1 for v in r.check_results.values() if v is True)
            failed = sum(1 for v in r.check_results.values() if v is False)
            manual = sum(1 for v in r.check_results.values() if v == "MANUAL_CHECK")
            total_pass += passed
            total_fail += failed

            check_summary = f"{passed}✅ {failed}❌ {manual}👁️"
            usage_summary = f"{r.api_calls} calls / {r.input_tokens + r.output_tokens:,} tkn"

            lines.append(
                f"| {r.question.id} | {r.question.question[:50]}… | {chart_icon} | {intact_icon} | {r.duration_seconds:.1f}s | {usage_summary} | {check_summary} |"
            )

        lines.extend([
            "",
            f"**Overall: {total_pass} passed, {total_fail} failed, "
            f"{sum(1 for r in self.results for v in r.check_results.values() if v == 'MANUAL_CHECK')} manual checks**",
            "",
            "### Global Resource Usage",
            f"- **Total API Calls:** {self.total_usage['api_calls']}",
            f"- **Total Tokens:** {self.total_usage['input_tokens'] + self.total_usage['output_tokens']:,} (Input: {self.total_usage['input_tokens']:,}, Output: {self.total_usage['output_tokens']:,})",
            f"- **Total Conversation Turns:** {self.total_usage['turns']}",
            "",
            "---",
            "",
        ])

        # Detailed results for each question
        for r in self.results:
            lines.extend([
                f"## {r.question.id}: {r.question.question}",
                "",
                f"**Expected chart:** {r.question.expected_chart_type}  ",
                f"**Chart generated:** {'Yes' if r.chart_generated else 'No'}  ",
                f"**Duration:** {r.duration_seconds:.1f}s  ",
                f"**Dataset intact:** {'Yes' if r.dataset_intact else '🚨 NO'}  ",
                f"**Usage:** {r.api_calls} calls, {r.input_tokens:,} input tokens, {r.output_tokens:,} output tokens, {r.turns} turns  ",
                "",
            ])

            if r.error:
                lines.extend([
                    "### ❌ Error",
                    f"```\n{r.error}\n```",
                    "",
                ])

            # Check results table
            lines.extend([
                "### Check Results",
                "",
                "| Check | Result |",
                "|-------|--------|",
            ])
            for check, value in r.check_results.items():
                if check.endswith("_detail"):
                    continue
                if value is True:
                    icon = "✅ PASS"
                elif value is False:
                    icon = "❌ FAIL"
                elif value == "MANUAL_CHECK":
                    icon = "👁️ Manual"
                else:
                    icon = str(value)
                lines.append(f"| `{check}` | {icon} |")

            # Show detail for failed dataset_intact
            if "dataset_intact_detail" in r.check_results:
                lines.extend([
                    "",
                    f"> **Dataset corruption detail:** {r.check_results['dataset_intact_detail']}",
                ])

            lines.extend([""])
            
            # Enriched Question
            if r.enriched_question:
                lines.extend([
                    "### Enriched Query",
                    f"> {r.enriched_question}",
                    "",
                ])

            # Tool Calls
            if r.tool_calls:
                lines.extend([
                    "### Code / Tools Executed",
                    "",
                ])
                for call in r.tool_calls:
                    lines.append(f"**Tool:** `{call['name']}`")
                    for k, v in call['args'].items():
                        if isinstance(v, str) and '\n' in v:
                            lines.extend([f"**`{k}`**:", "```python", v, "```"])
                        else:
                            lines.append(f"- **`{k}`**: `{v}`")
                lines.append("")

            # Agent response
            lines.extend([
                "### Agent Response (text)",
                "",
                "```",
                r.response_text[:1000] + ("…" if len(r.response_text) > 1000 else ""),
                "```",
                "",
            ])

            # Insight
            if r.insight_text:
                lines.extend([
                    "### Second-Pass Insight",
                    "",
                    "```",
                    r.insight_text[:800] + ("…" if len(r.insight_text) > 800 else ""),
                    "```",
                    "",
                ])

            # Chart image reference
            if r.figure_path:
                lines.extend([
                    "### Generated Chart",
                    f"![{r.question.id} chart](charts/{Path(r.figure_path).name})",
                    "",
                ])

            # Dataset state
            lines.extend([
                "### Dataset State",
                f"- **Before:** {r.df_rows_before} rows × {len(r.df_columns_before)} cols",
                f"- **After:** {r.df_rows_after} rows × {len(r.df_columns_after)} cols",
            ])
            if not r.dataset_intact:
                lost = set(r.df_columns_before) - set(r.df_columns_after)
                if lost:
                    lines.append(f"- **⚠️ Lost columns:** {sorted(lost)}")

            lines.extend(["", "---", ""])

        report_content = "\n".join(lines)

        with open(report_path, "w") as f:
            f.write(report_content)

        print(f"\n{'━'*70}")
        print(f"📋 Report saved: {report_path}")
        print(f"{'━'*70}")

        # Also print summary to console
        print(f"\n📊 SUMMARY: {total_pass} passed, {total_fail} failed")
        for r in self.results:
            status = "✅" if all(v is True or v == "MANUAL_CHECK" for v in r.check_results.values() if not str(v).startswith("N/A")) else "⚠️"
            print(f"   {status} {r.question.id}: chart={'✅' if r.chart_generated else '❌'} | intact={'✅' if r.dataset_intact else '🚨'} | {r.duration_seconds:.1f}s")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(description="DataVerse Agent Stress Test")
    parser.add_argument(
        "--dataset",
        default=CONFIG.default_dataset,
        help=f"Path to the dataset (CSV or DuckDB) (default: {CONFIG.default_dataset})",
    )
    parser.add_argument(
        "--cleaning",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Whether to run the initial cleaning phase. Defaults to False for DuckDB, True for CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=CONFIG.default_output_dir,
        help=f"Directory to save results (default: {CONFIG.default_output_dir})",
    )
    parser.add_argument(
        "--questions",
        nargs="*",
        default=None,
        help="Specific question IDs to run (e.g., Q1 Q3 Q5). Runs all if omitted.",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=CONFIG.inter_question_delay,
        help=f"Seconds to wait between questions (default: {CONFIG.inter_question_delay})",
    )
    args = parser.parse_args()

    # Load environment
    load_dotenv(PROJECT_ROOT / ".env")

    # Load Streamlit secrets as env vars (same pattern as the dashboard)
    secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        import tomllib
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        for key, value in secrets.items():
            if isinstance(value, str):
                os.environ[key] = value

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found. Set it in .streamlit/secrets.toml or .env")
        sys.exit(1)

    # Filter questions if specific IDs requested
    questions = STRESS_TEST_QUESTIONS
    if args.questions:
        selected_ids = set(args.questions)
        questions = [q for q in STRESS_TEST_QUESTIONS if q.id in selected_ids]
        if not questions:
            print(f"❌ No matching questions for IDs: {args.questions}")
            print(f"   Available: {[q.id for q in STRESS_TEST_QUESTIONS]}")
            sys.exit(1)

    # Use config default unless overridden via CLI
    skip_cleaning = not args.cleaning if args.cleaning is not None else CONFIG.skip_cleaning

    # Run
    runner = StressTestRunner(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        inter_question_delay=args.delay,
        skip_cleaning=skip_cleaning,
    )
    asyncio.run(runner.run_all(questions))


if __name__ == "__main__":
    main()
