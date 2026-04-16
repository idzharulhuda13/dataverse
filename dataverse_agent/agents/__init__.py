"""
DataVerse Agent Team — Multi-agent architecture.

Exports context-specific orchestrators for CSV and Enterprise modes.
"""
from dataverse_agent.agents.csv_orchestrator import csv_orchestrator
from dataverse_agent.agents.enterprise_orchestrator import enterprise_orchestrator

# Export as root_agent for backward compatibility with:
#   - streamlit_agent_dashboard.py: `from dataverse_agent.agent import root_agent`
#   - ADK Runner: expects a `root_agent` or named agent
root_agent = csv_orchestrator
