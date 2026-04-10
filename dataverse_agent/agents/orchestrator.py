"""
Orchestrator Agent — Routes user requests to specialist sub-agents.

This is the entry point for all user interactions. The ADK framework
automatically handles delegation based on each sub-agent's description.
"""
import os

from google.adk.agents import Agent
from dataverse_agent.agents.visual_analyst import visual_analyst_agent
from dataverse_agent.agents.forecast import forecast_agent
from dataverse_agent.agents.cleaning import cleaning_agent
from dataverse_agent.agents.sql_agent import sql_agent
from dataverse_agent.tools import table_tool
from dataverse_agent.prompts import load_prompt

orchestrator = Agent(
    model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
    name='orchestrator',
    description=(
        'The main DataVerse assistant that understands user intent and delegates '
        'to specialist agents for analysis, visualization, forecasting, and data cleaning.'
    ),
    sub_agents=[visual_analyst_agent, forecast_agent, cleaning_agent, sql_agent],
    tools=[table_tool],
    instruction=load_prompt('orchestrator'),
)
