"""
Enterprise Orchestrator Agent — Routes warehouse data requests to specialists.
"""
import os

from google.adk.agents import Agent
from dataverse_agent.agents.sql_agent import get_sql_agent
from dataverse_agent.agents.visual_analyst import get_visual_analyst_agent
from dataverse_agent.agents.forecast import get_forecast_agent
from dataverse_agent.tools import table_tool
from dataverse_agent.prompts import load_prompt

def get_enterprise_orchestrator() -> Agent:
    """Returns a fresh instance of the Enterprise Orchestrator."""
    return Agent(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
        name='enterprise_orchestrator',
        description=(
            'The senior analyst for integrated enterprise data. Handles SQL querying, '
            'business visualization, and forecasting for warehouse-scale data.'
        ),
        sub_agents=[get_sql_agent(), get_visual_analyst_agent(), get_forecast_agent()],
        tools=[table_tool],
        instruction=load_prompt('enterprise_orchestrator'),
    )

# Static instances are no longer safe to share, but we'll provide one for init
enterprise_orchestrator = get_enterprise_orchestrator()
