"""
DataVerse Agent — Entry point for the multi-agent system.

Provides a factory to retrieve the appropriate orchestrator based on mode.
"""
from google.adk.agents import Agent
from dataverse_agent.agents.csv_orchestrator import get_csv_orchestrator
from dataverse_agent.agents.enterprise_orchestrator import get_enterprise_orchestrator

def get_orchestrator(enterprise_mode: bool = False) -> Agent:
    """Returns the correct orchestrator agent based on the operation mode."""
    if enterprise_mode:
        return get_enterprise_orchestrator()
    return get_csv_orchestrator()

# Backward compatibility (static instance for initial load)
root_agent = get_csv_orchestrator()

__all__ = ['get_orchestrator', 'root_agent']
