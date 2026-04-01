"""
DataVerse Agent Team — Multi-agent architecture.

Exports the orchestrator as `root_agent` for backward compatibility
with the Streamlit dashboard and ADK Runner.
"""
from dataverse_agent.agents.orchestrator import orchestrator

# Export as root_agent for backward compatibility with:
#   - streamlit_agent_dashboard.py: `from dataverse_agent.agent import root_agent`
#   - ADK Runner: expects a `root_agent` or named agent
root_agent = orchestrator
