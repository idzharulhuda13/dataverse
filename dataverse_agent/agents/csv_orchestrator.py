"""
CSV Orchestrator Agent — Routes ad-hoc CSV exploration requests to specialists.
"""
import os

from google.adk.agents import Agent
from dataverse_agent.agents.visual_analyst import get_visual_analyst_agent
from dataverse_agent.agents.forecast import get_forecast_agent
from dataverse_agent.agents.cleaning import get_cleaning_agent
from dataverse_agent.tools import table_tool
from dataverse_agent.prompts import load_prompt

def get_csv_orchestrator() -> Agent:
    """Returns a fresh instance of the CSV Orchestrator."""
    return Agent(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
        name='csv_orchestrator',
        description=(
            'The primary analyst for ad-hoc CSV exploration, cleaning, and visualization. '
            'Routes to specialists for data preparation, charts, or forecasting.'
        ),
        sub_agents=[get_visual_analyst_agent(), get_forecast_agent(), get_cleaning_agent()],
        tools=[table_tool],
        instruction=load_prompt('csv_orchestrator'),
    )

# Static instances are no longer safe to share, but we'll provide one for init
csv_orchestrator = get_csv_orchestrator()
