"""
Visual Analyst Agent — Combined analysis + visualization specialist.

This is the primary agent for all data exploration. It always creates
a visualization alongside its analysis — never returns text-only.
"""
import os

from google.adk.agents import Agent
from dataverse_agent.tools import viz_tool, summary_tool, fallback_tool, table_tool
from dataverse_agent.prompts import load_prompt

visual_analyst_agent = Agent(
    model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
    name='visual_analyst_agent',
    description=(
        'The primary data exploration agent. Analyzes data AND creates premium '
        'visualizations together in one response. Handles statistical analysis, '
        'pattern detection, correlations, comparisons, distributions, outliers, '
        'and all chart types (bar, line, scatter, histogram, box, violin, heatmap, pie). '
        'Use this agent for ANY question about the data — it always shows a chart.'
    ),
    tools=[summary_tool, viz_tool, table_tool, fallback_tool],
    instruction=load_prompt('visual_analyst'),
)
