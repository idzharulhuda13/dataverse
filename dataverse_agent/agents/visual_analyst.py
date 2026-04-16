"""
Visual Analyst Agent — Combined analysis + visualization specialist.

This is the primary agent for all data exploration. It always creates
a visualization alongside its analysis — never returns text-only.
"""
import os

from google.adk.agents import Agent
from dataverse_agent.tools import viz_tool, summary_tool, fallback_tool, table_tool, stats_tool, weighted_tool
from dataverse_agent.prompts import load_prompt

def get_visual_analyst_agent() -> Agent:
    """Returns a fresh instance of the Visual Analyst Agent."""
    return Agent(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
        name='visual_analyst_agent',
        description=(
            'The primary data exploration agent. Analyzes data AND creates premium '
            'visualizations together in one response. Handles statistical analysis, '
            'pattern detection, correlations, comparisons, distributions, outliers, '
            'and all chart types (bar, line, scatter, histogram, box, violin, heatmap, pie, stacked_area, slope). '
            'Supports advanced features like Bubble Charts (size), Trend Lines, and Quadrant Analysis (reference lines). '
            'Supports specialized statistical tools (stats_tool) for Z-scores/Ranking and weighted_tool for metric splits. '
            'Use this agent for ANY question about the data — it always shows a chart.'
        ),
        tools=[summary_tool, viz_tool, table_tool, fallback_tool, stats_tool, weighted_tool],
        instruction=load_prompt('visual_analyst'),
    )

# Default instance for backward compatibility
visual_analyst_agent = get_visual_analyst_agent()
