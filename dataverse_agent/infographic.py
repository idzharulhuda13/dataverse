"""
Infographic PDF Generator — Agent-Driven Design

Two-step pipeline:
  1. Send all pinned chart images to Gemini for structured narrative generation
  2. Compose the agent's content + original chart figures into a styled A4 PDF

Uses reportlab Platypus (Flowables) for responsive, document-flow PDF composition.

Public API:
  - generate_infographic_content()  -> dict (agent's structured JSON)
  - render_infographic_pdf()        -> bytes (PDF file)
"""

import io
import json
import textwrap
from datetime import datetime
from typing import Optional

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
  "conclusion": "A 1-2 sentence executive summary tying all findings together."
}}

RULES:
- chart_headlines MUST have exactly {chart_count} entries (one per chart, in order).
- key_takeaways should have 3-5 entries.
- Be specific: use actual numbers, percentages, and category names from the data.
- Do NOT use generic filler text. Every sentence must reference concrete data.
- Return ONLY the JSON object, nothing else.
"""


async def generate_infographic_content(
    runner,
    session_id: str,
    dashboard_items: list[dict],
    data_summary: str,
    dataset_name: str,
    usage_tracker=None,
) -> dict:
    """Send all pinned charts to Gemini and get structured infographic content."""
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

    return _parse_agent_response(response_text, len(dashboard_items))


def _parse_agent_response(raw_text: str, chart_count: int) -> dict:
    """Parse and validate the agent's JSON response with fallback handling."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        content = json.loads(cleaned)
    except json.JSONDecodeError:
        content = _fallback_content(chart_count)

    # Validate and fill missing fields
    if "infographic_title" not in content:
        content["infographic_title"] = "Data Analysis Overview"
    if "infographic_subtitle" not in content:
        content["infographic_subtitle"] = "Key insights from your dataset"
    if "chart_headlines" not in content or len(content["chart_headlines"]) != chart_count:
        content["chart_headlines"] = [f"Chart {i + 1}" for i in range(chart_count)]
    if "key_takeaways" not in content or not content["key_takeaways"]:
        content["key_takeaways"] = ["Analysis reveals notable patterns in the data."]
    if "conclusion" not in content:
        content["conclusion"] = "Further analysis recommended to uncover deeper trends."

    return content


def _fallback_content(chart_count: int) -> dict:
    """Minimal fallback when agent response can't be parsed."""
    return {
        "infographic_title": "Data Analysis Overview",
        "infographic_subtitle": "Key insights from your dataset",
        "chart_headlines": [f"Chart {i + 1}" for i in range(chart_count)],
        "key_takeaways": ["Analysis reveals notable patterns in the data."],
        "conclusion": "Further analysis recommended to uncover deeper trends.",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2: PDF Composition (Platypus Flowables)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _header_footer_template(canvas_obj: canvas.Canvas, doc: BaseDocTemplate, content: dict):
    """Draw the fixed header and footer on every page before flowables are placed."""
    canvas_obj.saveState()
    
    # Background
    canvas_obj.setFillColor(BG_COLOR)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # --- Header ---
    header_h = 75
    # Dark header strip
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, PAGE_H - header_h, PAGE_W, header_h, fill=1, stroke=0)
    # Gold top line
    canvas_obj.setFillColor(GOLD)
    canvas_obj.rect(0, PAGE_H - 4, PAGE_W, 4, fill=1, stroke=0)

    # Title
    title_text = content.get("infographic_title", "").upper()
    title_size = 22
    while canvas_obj.stringWidth(title_text, "Helvetica-Bold", title_size) > PAGE_W - 80 and title_size > 12:
        title_size -= 1
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", title_size)
    canvas_obj.drawCentredString(PAGE_W / 2, PAGE_H - header_h * 0.45, title_text)

    # Subtitle
    sub_text = content.get("infographic_subtitle", "")
    sub_size = 11
    while canvas_obj.stringWidth(sub_text, "Helvetica-Oblique", sub_size) > PAGE_W - 80 and sub_size > 8:
        sub_size -= 1
    canvas_obj.setFillColor(GOLD)
    canvas_obj.setFont("Helvetica-Oblique", sub_size)
    canvas_obj.drawCentredString(PAGE_W / 2, PAGE_H - header_h * 0.72, sub_text)

    # --- Footer ---
    footer_h = 24
    # Dark footer strip
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, PAGE_W, footer_h, fill=1, stroke=0)
    # Gold separator line
    canvas_obj.setFillColor(GOLD)
    canvas_obj.rect(0, footer_h, PAGE_W, 2, fill=1, stroke=0)

    # Text
    generation_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    canvas_obj.setFillColor(CAPTION_COLOR)
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawCentredString(
        PAGE_W / 2, footer_h * 0.35,
        f"Generated by DataVerse  |  {generation_time}"
    )
    
    canvas_obj.restoreState()


def render_infographic_pdf(
    content: dict,
    dashboard_items: list[dict],
    dataset_name: str,
) -> bytes:
    """Compose a full-page infographic PDF from agent content + pinned charts using flowables."""
    pdf_buffer = io.BytesIO()
    
    # Margins: Ensure flowables don't paint over the 75pt header and 24pt footer
    doc = BaseDocTemplate(
        pdf_buffer, 
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=85, bottomMargin=40,
        title=content.get("infographic_title", "DataVerse Infographic")
    )
    
    # We use a single Frame that occupies the area between header and footer
    frame = Frame(
        doc.leftMargin, doc.bottomMargin, 
        doc.width, doc.height, 
        id='normal'
    )
    # create a template with our background/header callback
    template = PageTemplate(
        id='test', 
        frames=frame, 
        onPage=lambda c, d: _header_footer_template(c, d, content)
    )
    doc.addPageTemplates([template])

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

    story = []
    story.append(Spacer(1, 10))

    # --- Charts Grid (Responsive Table) ---
    chart_figures = _prepare_chart_images(dashboard_items)
    headlines = content.get("chart_headlines", [])
    
    if chart_figures:
        # Determine cols based on chart count (max 2)
        cols = 2 if len(chart_figures) > 1 else 1
        col_width = (doc.width - 15) / cols if cols > 1 else doc.width
        
        # Build grid data: [[cell1, cell2], [cell3...]]
        table_data = []
        current_row = []
        
        for i, img_buf in enumerate(chart_figures):
            headline_text = headlines[i] if i < len(headlines) else ""
            
            # Create a Platypus Image
            img_buf.seek(0)
            img = Image(img_buf)
            # Scale image width to fit column width
            aspect = img.imageHeight / float(img.imageWidth)
            img.drawWidth = col_width - 10
            img.drawHeight = (col_width - 10) * aspect
            
            # Put Image and Paragraph into a nested arrangement (a single column Table is perfect for a card)
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
            
            # Wrap row
            if len(current_row) == cols:
                table_data.append(current_row)
                current_row = []
                
        # Handle trailing odd items
        if current_row:
            if cols > 1:
                current_row.append("") # Empty cell to balance the 2-col row
            table_data.append(current_row)
            
        # Add the chart grid Table to story
        grid_table = Table(table_data, colWidths=[col_width + 10]*cols, style=[
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 15),
        ])
        story.append(grid_table)
        story.append(Spacer(1, 10))

    # --- Takeaways Box ---
    takeaways = content.get("key_takeaways", [])
    if takeaways:
        box_story = []
        
        # Add Title Line
        box_story.append(Paragraph("KEY TAKEAWAYS", takeaway_title_style))
        # Add a gold separating line using a narrow Table
        line_table = Table([[""]], colWidths=[120], rowHeights=[2], style=[
            ('BACKGROUND', (0,0), (0,0), GOLD),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ])
        box_story.append(line_table)
        box_story.append(Spacer(1, 10))
        
        # Add Bullets
        for idx, t in enumerate(takeaways[:5]):
            p = Paragraph(f"• &nbsp; {t}", takeaway_bullet_style)
            box_story.append(p)
            
        # Add Conclusion
        conclusion = content.get("conclusion", "")
        if conclusion:
            box_story.append(Paragraph(f"{conclusion}", conclusion_style))
            
        # Wrap everything in a Background Table to act as the Navy Box
        takeaway_card = Table([[box_story]], colWidths=[doc.width], style=[
            ('BACKGROUND', (0,0), (-1,-1), NAVY),
            ('BOX', (0,0), (-1,-1), 0, NAVY), # Border
            ('TOPPADDING', (0,0), (-1,-1), 15),
            ('BOTTOMPADDING', (0,0), (-1,-1), 15),
            ('LEFTPADDING', (0,0), (-1,-1), 20),
            ('RIGHTPADDING', (0,0), (-1,-1), 20),
        ])
        
        story.append(KeepTogether(takeaway_card))

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
