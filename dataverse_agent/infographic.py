"""
Infographic PDF Generator — Agent-Driven Design

Two-step pipeline:
  1. Send all pinned chart images to Gemini for structured narrative generation
  2. Compose the agent's content + original chart figures into a styled A4 PDF

Uses reportlab Platypus (Flowables) for responsive, document-flow PDF composition.

Public API:
  - generate_infographic_content()  -> InfographicContent (Pydantic model)
  - render_infographic_pdf()        -> bytes (PDF file)
"""

import io
import json
import textwrap
from datetime import datetime
from typing import Optional

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm, cm
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, SimpleDocTemplate,
    Paragraph, Table, TableStyle, Spacer, Image, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from dataverse_agent.schemas import (
    InfographicContent,
    InfographicMetric,
    CalculatedMetric,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONSTANTS — Infographic Theme
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NAVY = HexColor("#2D3A4A")
TEAL = HexColor("#4A7C8F")
LIGHT_TEAL = HexColor("#7BA7A9")
GOLD = HexColor("#D4A574")
BG_COLOR = HexColor("#FAFBFC")
CARD_BG = HexColor("#FFFFFF")
TEXT_COLOR = HexColor("#1E293B")
CAPTION_COLOR = HexColor("#64748B")
GRID_COLOR = HexColor("#E2E8F0")
DARK_BG = HexColor("#1E293B")
WHITE = HexColor("#FFFFFF")

PAGE_W, PAGE_H = A4  # 595.27, 841.89 points
MARGIN = 40
CONTENT_W = PAGE_W - 2 * MARGIN


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1: Agent Content Generation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INFOGRAPHIC_PROMPT = """\
You are a data storytelling expert creating an infographic summary.

You are given {chart_count} charts from a data analysis session on the dataset "{dataset_name}".
Each chart may have an existing insight. Below is a statistical summary of the dataset:

{data_summary}

---

Analyze ALL the charts together and produce a cohesive infographic narrative.
Return ONLY valid JSON (no markdown fencing, no extra text) with this exact schema:

{{
  "infographic_title": "A compelling, specific title for this infographic (max 8 words)",
  "infographic_subtitle": "A one-line subtitle that frames the analysis scope (max 15 words)",
  "chart_headlines": [
    "A short, punchy headline for chart 1 (max 10 words)",
    "A short, punchy headline for chart 2 (max 10 words)"
  ],
  "key_takeaways": [
    "First key insight from ALL charts combined (1 sentence)",
    "Second key insight (1 sentence)",
    "Third key insight (1 sentence)"
  ],
  "conclusion": "A 1-2 sentence executive summary tying all findings together.",
  "metrics": [
     {{"label": "Metric title with unit if known (e.g. Total Revenue ($))", "column": "column_name", "op": "sum|mean|count|nunique"}}
  ]
}}

RULES:
- metrics should have 2-6 entries (relevant KPIs with different operations).
- metrics[].op MUST be one of: sum, mean, count, nunique, max, min.
- metrics[].column MUST be a valid column from the Data Summary.
- chart_headlines MUST have exactly {chart_count} entries (one per chart, in order).
- key_takeaways should have 3-5 entries.
- Be specific: use actual numbers, percentages, and category names from the data.
- MUST include units in metric labels (e.g., "($)", "(kg)", "(%)") if evident from column names or summary.
- Prefer "sum" (Total) for high-level business metrics like Revenue, Sales, and Volume.
- Do NOT use generic filler text. Every sentence must reference concrete data.
- Return ONLY the JSON object, nothing else.
"""


async def generate_infographic_content(
    runner,
    session_id: str,
    dashboard_items: list[dict],
    data_summary: str,
    dataset_name: str,
    df: pd.DataFrame,
    usage_tracker=None,
) -> InfographicContent:
    """Send all pinned charts to Gemini and get structured infographic content.

    Returns:
        InfographicContent Pydantic model with all narrative fields and calculated metrics.
    """
    from google.genai import types

    image_parts = []
    for i, item in enumerate(dashboard_items):
        fig = item.get("figure")
        if fig is None:
            continue
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        png_bytes = buf.getvalue()
        buf.close()

        insight = item.get("insight", "")
        chart_context = f"[Chart {i + 1}]"
        if insight:
            chart_context += f" Existing insight: {insight}"
        image_parts.append(types.Part.from_text(text=chart_context))
        image_parts.append(types.Part.from_bytes(data=png_bytes, mime_type="image/png"))

    prompt_text = INFOGRAPHIC_PROMPT.format(
        chart_count=len(dashboard_items),
        dataset_name=dataset_name,
        data_summary=data_summary or "No summary available.",
    )

    all_parts = [types.Part.from_text(text=prompt_text)] + image_parts

    response_text = ""
    async for event in runner.run_async(
        user_id="default",
        session_id=session_id,
        new_message=types.Content(parts=all_parts),
    ):
        if usage_tracker and hasattr(event, "usage_metadata") and event.usage_metadata:
            usage_tracker.record_api_call({
                "prompt_token_count": event.usage_metadata.prompt_token_count,
                "candidates_token_count": event.usage_metadata.candidates_token_count,
                "total_token_count": event.usage_metadata.total_token_count,
            })

        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    response_text += p.text

    content = _parse_agent_response(response_text, len(dashboard_items))

    # Deterministically calculate metric values from the actual dataframe
    content.calculated_metrics = _calculate_metric_values(df, content.metrics)

    return content


def _calculate_metric_values(
    df: pd.DataFrame,
    metrics: list[InfographicMetric],
) -> list[CalculatedMetric]:
    """Calculate deterministic values for the agent-suggested metrics."""
    results: list[CalculatedMetric] = []
    for m in metrics:
        label = m.label
        col = m.column
        op = m.op

        value = None
        if not col or col not in df.columns:
            value = len(df)
            label = "Total Records"
        else:
            try:
                if op == "sum":
                    value = df[col].sum()
                elif op == "mean":
                    value = df[col].mean()
                elif op == "nunique":
                    value = df[col].nunique()
                elif op == "max":
                    value = df[col].max()
                elif op == "min":
                    value = df[col].min()
                else:  # count
                    value = df[col].count()
            except Exception:
                value = len(df)
                label = "Total Records"

        # Special handling for percentages
        if value is not None and any(x in str(col).lower() for x in ['%', 'growth', 'rate']):
            if isinstance(value, (int, float)):
                label = label if "%" in label else f"{label} (%)"

        results.append(CalculatedMetric(label=label, value=value, op=op))

    return results


def _parse_agent_response(raw_text: str, chart_count: int) -> InfographicContent:
    """Parse and validate the agent's JSON response into an InfographicContent model."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError:
        return _fallback_content(chart_count)

    # Ensure chart_headlines has the right count
    headlines = raw.get("chart_headlines", [])
    if len(headlines) != chart_count:
        headlines = [f"Chart {i + 1}" for i in range(chart_count)]

    # Parse metrics safely
    raw_metrics = raw.get("metrics", [])
    metrics: list[InfographicMetric] = []
    for m in raw_metrics:
        if isinstance(m, dict) and "label" in m and "column" in m:
            try:
                metrics.append(InfographicMetric.model_validate(m))
            except Exception:
                pass

    return InfographicContent(
        infographic_title=raw.get("infographic_title", "Data Analysis Overview"),
        infographic_subtitle=raw.get("infographic_subtitle", "Key insights from your dataset"),
        chart_headlines=headlines,
        key_takeaways=raw.get("key_takeaways") or ["Analysis reveals notable patterns in the data."],
        conclusion=raw.get("conclusion", "Further analysis recommended to uncover deeper trends."),
        metrics=metrics,
    )


def _fallback_content(chart_count: int) -> InfographicContent:
    """Minimal fallback when agent response can't be parsed."""
    return InfographicContent(
        chart_headlines=[f"Chart {i + 1}" for i in range(chart_count)],
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2: PDF Composition (Platypus Flowables)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _header_footer_template(canvas_obj: canvas.Canvas, doc: BaseDocTemplate, content: InfographicContent):
    """Draw the fixed header and footer on every page before flowables are placed."""
    canvas_obj.saveState()

    # Background
    canvas_obj.setFillColor(BG_COLOR)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # --- Header ---
    header_h = 75
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, PAGE_H - header_h, PAGE_W, header_h, fill=1, stroke=0)
    canvas_obj.setFillColor(GOLD)
    canvas_obj.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)

    # Title
    title_text = content.infographic_title.upper()
    title_size = 22
    while canvas_obj.stringWidth(title_text, "Helvetica-Bold", title_size) > PAGE_W - 80 and title_size > 12:
        title_size -= 1
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", title_size)
    canvas_obj.drawCentredString(PAGE_W / 2, PAGE_H - header_h * 0.45, title_text)

    # Subtitle
    sub_text = content.infographic_subtitle
    sub_size = 11
    while canvas_obj.stringWidth(sub_text, "Helvetica-Oblique", sub_size) > PAGE_W - 80 and sub_size > 8:
        sub_size -= 1
    canvas_obj.setFillColor(GOLD)
    canvas_obj.setFont("Helvetica-Oblique", sub_size)
    canvas_obj.drawCentredString(PAGE_W / 2, PAGE_H - header_h * 0.72, sub_text)

    # --- Footer ---
    footer_h = 24
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, PAGE_W, footer_h, fill=1, stroke=0)
    canvas_obj.setFillColor(GOLD)
    canvas_obj.rect(0, footer_h, PAGE_W, 2, fill=1, stroke=0)

    generation_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    canvas_obj.setFillColor(CAPTION_COLOR)
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawCentredString(
        PAGE_W / 2, footer_h * 0.35,
        f"Generated by DataVerse  |  {generation_time}"
    )

    canvas_obj.restoreState()


def render_infographic_pdf(
    content: InfographicContent,
    dashboard_items: list[dict],
    dataset_name: str,
) -> bytes:
    """Compose a single-page scrolling infographic PDF (dynamic height)."""
    from dataverse_agent.tools import _human_format

    # ── 1. Setup Base Layout ───
    A4_WIDTH = A4[0]
    LEFT_MARGIN = 36
    RIGHT_MARGIN = 36
    CONTENT_WIDTH = A4_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

    HEADER_H = 90
    FOOTER_H = 25

    pdf_buffer = io.BytesIO()
    styles = getSampleStyleSheet()

    # Custom styles
    headline_style = ParagraphStyle(
        name='Headline',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=NAVY,
        alignment=TA_CENTER,
        leading=10,
    )
    takeaway_title_style = ParagraphStyle(
        name='TakeawayTitle',
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=GOLD,
        spaceAfter=8,
    )
    takeaway_bullet_style = ParagraphStyle(
        name='TakeawayBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=WHITE,
        leading=13,
        leftIndent=15,
        firstLineIndent=-15,
        spaceAfter=6,
    )
    conclusion_style = ParagraphStyle(
        name='Conclusion',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        textColor=LIGHT_TEAL,
        leading=11,
        spaceBefore=10,
    )
    metric_value_style = ParagraphStyle(
        name='MetricValue',
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=NAVY,
        alignment=TA_CENTER,
    )
    metric_label_style = ParagraphStyle(
        name='MetricLabel',
        fontName='Helvetica',
        fontSize=7.5,
        textColor=CAPTION_COLOR,
        alignment=TA_CENTER,
        leading=9,
    )

    story = []
    story.append(Spacer(1, 8))

    # --- Metrics Bar (KPI Cards) ---
    metrics = content.calculated_metrics
    if metrics:
        count = len(metrics)
        cols = min(count, 4)
        gap = 6
        card_w = (CONTENT_WIDTH - (gap * (cols - 1))) / cols

        table_rows = []
        current_row = []

        for i, m in enumerate(metrics):
            try:
                val = m.value
                if val is None:
                    val_text = "N/A"
                else:
                    try:
                        val_text = _human_format(val)
                    except Exception:
                        val_text = str(val)

                label_text = str(m.label).upper()

                border_colors = [TEAL, GOLD, NAVY, LIGHT_TEAL, GOLD, TEAL]
                b_color = border_colors[i % len(border_colors)]

                card_content = [
                    [Paragraph(label_text, metric_label_style)],
                    [Paragraph(val_text, metric_value_style)]
                ]

                card_table = Table(card_content, colWidths=[card_w], style=[
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
                    ('LINEABOVE', (0,0), (-1,0), 2, b_color),
                    ('BOX', (0,0), (-1,-1), 0.5, GRID_COLOR),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ])

                current_row.append(card_table)
            except Exception:
                continue

            if len(current_row) == cols:
                table_rows.append(current_row)
                current_row = []

        if current_row:
            while len(current_row) < cols:
                current_row.append("")
            table_rows.append(current_row)

        metrics_grid = Table(
            table_rows,
            colWidths=[card_w + (gap if i < cols-1 else 0) for i in range(cols)],
            style=[
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]
        )
        story.append(metrics_grid)
        story.append(Spacer(1, 10))

    # --- Charts Grid (Responsive Table) ---
    chart_figures = _prepare_chart_images(dashboard_items)
    headlines = content.chart_headlines

    if chart_figures:
        cols = 2 if len(chart_figures) > 1 else 1
        col_width = (CONTENT_WIDTH - 15) / cols if cols > 1 else CONTENT_WIDTH

        table_data = []
        current_row = []

        for i, img_buf in enumerate(chart_figures):
            headline_text = headlines[i] if i < len(headlines) else ""

            img_buf.seek(0)
            img = Image(img_buf)
            aspect = img.imageHeight / float(img.imageWidth)
            img.drawWidth = col_width - 10
            img.drawHeight = (col_width - 10) * aspect

            card_data = [
                [img],
                [Spacer(1, 5)],
                [Paragraph(headline_text, headline_style)]
            ]
            card_table = Table(card_data, colWidths=[col_width], style=[
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BACKGROUND', (0,0), (-1,-1), CARD_BG),
                ('BOX', (0,0), (-1,-1), 0.5, GRID_COLOR),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 2),
                ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ])

            current_row.append(card_table)

            if len(current_row) == cols:
                table_data.append(current_row)
                current_row = []

        if current_row:
            if cols > 1:
                current_row.append("")
            table_data.append(current_row)

        grid_table = Table(table_data, colWidths=[col_width + 10]*cols, style=[
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 15),
        ])
        story.append(grid_table)
        story.append(Spacer(1, 10))

    # --- Takeaways Box ---
    takeaways = content.key_takeaways
    if takeaways:
        box_story = []

        box_story.append(Paragraph("KEY TAKEAWAYS", takeaway_title_style))
        line_table = Table([[""]], colWidths=[120], rowHeights=[2], style=[
            ('BACKGROUND', (0,0), (0,0), GOLD),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ])
        box_story.append(line_table)
        box_story.append(Spacer(1, 10))

        for idx, t in enumerate(takeaways[:5]):
            p = Paragraph(f"• &nbsp; {t}", takeaway_bullet_style)
            box_story.append(p)

        conclusion = content.conclusion
        if conclusion:
            box_story.append(Paragraph(f"{conclusion}", conclusion_style))

        takeaway_card = Table([[box_story]], colWidths=[CONTENT_WIDTH], style=[
            ('BACKGROUND', (0,0), (-1,-1), NAVY),
            ('BOX', (0,0), (-1,-1), 0, NAVY),
            ('TOPPADDING', (0,0), (-1,-1), 15),
            ('BOTTOMPADDING', (0,0), (-1,-1), 15),
            ('LEFTPADDING', (0,0), (-1,-1), 20),
            ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ])

        story.append(takeaway_card)

    # ── 3. Calculate Dynamic Height ───
    current_h = 0
    for flowable in story:
        w, h = flowable.wrap(CONTENT_WIDTH, 1000000)
        current_h += h
        if isinstance(flowable, Spacer):
            current_h += 2

    final_height = max(current_h + HEADER_H + FOOTER_H + 60, A4[1])

    # Pre-define header styles for canvas drawing
    header_title_style = ParagraphStyle(
        name='HeaderTitle', fontName='Helvetica-Bold', fontSize=18, textColor=HexColor("#FFFFFF"),
        alignment=TA_CENTER, leading=22,
    )
    header_subtitle_style = ParagraphStyle(
        name='HeaderSubtitle', fontName='Helvetica', fontSize=9, textColor=HexColor("#FFFFFF"),
        alignment=TA_CENTER, leading=11,
    )

    # ── 4. Build Custom Document ───
    doc = BaseDocTemplate(
        pdf_buffer,
        pagesize=(A4_WIDTH, final_height),
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=HEADER_H + 10,
        bottomMargin=FOOTER_H + 10,
        title=content.infographic_title,
    )

    def draw_fixed_elements(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, final_height - HEADER_H, A4_WIDTH, HEADER_H, fill=1)

        title_text = content.infographic_title.upper()
        p_title = Paragraph(title_text, header_title_style)
        w, h = p_title.wrap(CONTENT_WIDTH, HEADER_H)
        p_title.drawOn(canvas, LEFT_MARGIN, final_height - 15 - h)

        subtitle_text = content.infographic_subtitle.upper()
        p_sub = Paragraph(subtitle_text, header_subtitle_style)
        w_s, h_s = p_sub.wrap(CONTENT_WIDTH, HEADER_H)
        p_sub.drawOn(canvas, LEFT_MARGIN, final_height - 15 - h - 5 - h_s)

        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, A4_WIDTH, FOOTER_H, fill=1)
        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.setFont('Helvetica-Oblique', 8)
        canvas.drawString(LEFT_MARGIN, 9, f"GENERATED BY DATAVERSE AI • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        canvas.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    template = PageTemplate(id='ScrollingPage', frames=frame, onPage=draw_fixed_elements)
    doc.addPageTemplates([template])

    doc.build(story)

    return pdf_buffer.getvalue()


def _prepare_chart_images(dashboard_items: list[dict]) -> list:
    """Convert each pinned figure to a BytesIO PNG buffer."""
    images = []
    for item in dashboard_items:
        fig = item.get("figure")
        if fig is None:
            continue
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                    facecolor="#FFFFFF", edgecolor="none")
        buf.seek(0)
        images.append(buf)
    return images
