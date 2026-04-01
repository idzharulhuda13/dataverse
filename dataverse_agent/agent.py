"""
DataVerse Agent — Entry point for the multi-agent system.

This module provides backward compatibility by re-exporting root_agent
from the new agents package. The Streamlit dashboard and ADK Runner
both import from here.

Architecture:
    orchestrator (root_agent)
    ├── analyst_agent — statistical analysis & business insights
    ├── viz_agent — premium chart creation
    ├── forecast_agent — time-series forecasting (Prophet)
    └── cleaning_agent — data transformations & quality
"""
from dataverse_agent.agents import root_agent

__all__ = ['root_agent']
