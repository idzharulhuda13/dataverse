"""Tests for the infographic PDF generator module."""

import pytest
import io
import matplotlib
matplotlib.use("Agg")  # Use non-interactive backend for testing
import matplotlib.pyplot as plt

from dataverse_agent.infographic import (
    render_infographic_pdf,
    _parse_agent_response,
    _fallback_content,
    _prepare_chart_images,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_mock_figure(title="Mock Chart"):
    """Create a simple matplotlib figure for testing."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["A", "B", "C"], [10, 20, 30])
    ax.set_title(title)
    return fig


def _make_mock_dashboard_items(count=2):
    """Create a list of mock dashboard items."""
    items = []
    for i in range(count):
        items.append({
            "type": "figure",
            "figure": _make_mock_figure(f"Chart {i + 1}"),
            "insight": f"This is insight {i + 1} about the data.",
        })
    return items


def _make_mock_content(chart_count=2):
    """Create a mock agent response content dict."""
    return {
        "infographic_title": "Sales Performance Overview",
        "infographic_subtitle": "Key trends from quarterly data analysis",
        "chart_headlines": [f"Headline for chart {i + 1}" for i in range(chart_count)],
        "key_takeaways": [
            "Revenue grew 15% quarter-over-quarter",
            "Electronics category dominates at 43% share",
            "Customer retention improved by 8% in Q3",
        ],
        "conclusion": "The data reveals strong growth with concentration in electronics. Diversification is recommended.",
    }


# ── PDF Rendering Tests ──────────────────────────────────────────────────────


class TestRenderInfographicPdf:
    """Tests for render_infographic_pdf()."""

    def test_returns_valid_pdf_bytes(self):
        """Output should be valid PDF (starts with %PDF-)."""
        items = _make_mock_dashboard_items(2)
        content = _make_mock_content(2)

        pdf_bytes = render_infographic_pdf(
            content=content,
            dashboard_items=items,
            dataset_name="test_data.csv",
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_single_chart(self):
        """Should handle a single pinned chart."""
        items = _make_mock_dashboard_items(1)
        content = _make_mock_content(1)

        pdf_bytes = render_infographic_pdf(
            content=content,
            dashboard_items=items,
            dataset_name="single_chart.csv",
        )

        assert pdf_bytes[:5] == b"%PDF-"

    def test_many_charts_multipage(self):
        """5+ charts should produce a multi-page PDF (>4 charts per page)."""
        items = _make_mock_dashboard_items(6)
        content = _make_mock_content(6)

        pdf_bytes = render_infographic_pdf(
            content=content,
            dashboard_items=items,
            dataset_name="large_dataset.csv",
        )

        assert pdf_bytes[:5] == b"%PDF-"
        # Multi-page PDFs are larger than single-page
        single_items = _make_mock_dashboard_items(1)
        single_content = _make_mock_content(1)
        single_pdf = render_infographic_pdf(
            content=single_content,
            dashboard_items=single_items,
            dataset_name="small.csv",
        )
        assert len(pdf_bytes) > len(single_pdf)

    def test_no_insights(self):
        """Should handle items without insight text."""
        items = [{"type": "figure", "figure": _make_mock_figure()}]
        content = _make_mock_content(1)

        pdf_bytes = render_infographic_pdf(
            content=content,
            dashboard_items=items,
            dataset_name="no_insights.csv",
        )

        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_contains_title(self):
        """PDF metadata should contain the infographic title."""
        items = _make_mock_dashboard_items(1)
        content = _make_mock_content(1)

        pdf_bytes = render_infographic_pdf(
            content=content,
            dashboard_items=items,
            dataset_name="test.csv",
        )

        # The title should be in the PDF metadata
        pdf_str = pdf_bytes.decode("latin-1")
        assert "Sales Performance Overview" in pdf_str


# ── Agent Response Parsing Tests ─────────────────────────────────────────────


class TestParseAgentResponse:
    """Tests for _parse_agent_response()."""

    def test_valid_json(self):
        """Should parse valid JSON correctly."""
        raw = '{"infographic_title": "Test", "infographic_subtitle": "Sub", "chart_headlines": ["H1"], "key_takeaways": ["T1"], "conclusion": "C"}'
        result = _parse_agent_response(raw, 1)

        assert result["infographic_title"] == "Test"
        assert result["infographic_subtitle"] == "Sub"
        assert len(result["chart_headlines"]) == 1
        assert result["conclusion"] == "C"

    def test_json_with_markdown_fencing(self):
        """Should strip ```json ... ``` fencing."""
        raw = '```json\n{"infographic_title": "Fenced", "infographic_subtitle": "Sub", "chart_headlines": ["H1", "H2"], "key_takeaways": ["T1"], "conclusion": "C"}\n```'
        result = _parse_agent_response(raw, 2)

        assert result["infographic_title"] == "Fenced"
        assert len(result["chart_headlines"]) == 2

    def test_invalid_json_fallback(self):
        """Should return fallback content for unparseable responses."""
        raw = "This is not JSON at all."
        result = _parse_agent_response(raw, 3)

        assert result["infographic_title"] == "Data Analysis Overview"
        assert len(result["chart_headlines"]) == 3

    def test_missing_fields_filled(self):
        """Should fill in missing required fields."""
        raw = '{"infographic_title": "Only Title"}'
        result = _parse_agent_response(raw, 2)

        assert result["infographic_title"] == "Only Title"
        assert "infographic_subtitle" in result
        assert len(result["chart_headlines"]) == 2
        assert len(result["key_takeaways"]) >= 1
        assert "conclusion" in result

    def test_wrong_headline_count_corrected(self):
        """Should replace chart_headlines if count doesn't match."""
        raw = '{"infographic_title": "T", "chart_headlines": ["H1"]}'
        result = _parse_agent_response(raw, 3)

        # Should be corrected to 3 entries
        assert len(result["chart_headlines"]) == 3


# ── Fallback Content Tests ───────────────────────────────────────────────────


class TestFallbackContent:
    """Tests for _fallback_content()."""

    def test_correct_chart_count(self):
        result = _fallback_content(4)
        assert len(result["chart_headlines"]) == 4

    def test_has_all_required_fields(self):
        result = _fallback_content(1)
        assert "infographic_title" in result
        assert "infographic_subtitle" in result
        assert "chart_headlines" in result
        assert "key_takeaways" in result
        assert "conclusion" in result


# ── Chart Image Preparation Tests ────────────────────────────────────────────


class TestPrepareChartImages:
    """Tests for _prepare_chart_images()."""

    def test_converts_figures_to_bytesio(self):
        items = _make_mock_dashboard_items(2)
        images = _prepare_chart_images(items)

        assert len(images) == 2
        # Each should be a BytesIO with PNG data
        for img in images:
            assert isinstance(img, io.BytesIO)
            img.seek(0)
            header = img.read(4)
            # PNG magic bytes
            assert header == b"\x89PNG"

    def test_skips_items_without_figures(self):
        items = [
            {"type": "figure", "figure": _make_mock_figure()},
            {"type": "figure", "figure": None},
        ]
        images = _prepare_chart_images(items)
        assert len(images) == 1
