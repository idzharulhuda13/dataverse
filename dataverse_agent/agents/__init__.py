"""
DataVerse Agent Team — Multi-agent architecture.

Exports context-specific orchestrators and specialist agents.
"""
from dataverse_agent.agents.csv_orchestrator import csv_orchestrator
from dataverse_agent.agents.enterprise_orchestrator import enterprise_orchestrator
from dataverse_agent.agents.sql_agent import sql_agent
from dataverse_agent.agents.visual_analyst import visual_analyst_agent
from dataverse_agent.agents.forecast import forecast_agent
from dataverse_agent.agents.cleaning import cleaning_agent

# Export as root_agent for backward compatibility with:
#   - streamlit_agent_dashboard.py
root_agent = csv_orchestrator

# Available specialists for handoffs
TEAM = {
    "sql_agent": sql_agent,
    "visual_analyst_agent": visual_analyst_agent,
    "forecast_agent": forecast_agent,
    "cleaning_agent": cleaning_agent,
}
