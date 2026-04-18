"""
SQL Agent — Specialist in writing and executing warehouse SQL.
"""
import os

from google.adk.agents import Agent
from google.genai import types
from dataverse_agent.tools import sql_tool, summary_tool
from dataverse_agent.prompts import load_prompt

def get_sql_agent() -> Agent:
    """Returns a fresh instance of the SQL Agent."""
    return Agent(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
        generate_content_config=types.GenerateContentConfig(temperature=0.2),
        name='sql_agent',
        description=(
            'Specialist in database querying for BigQuery and DuckDB. '
            'Generates and executes SQL to fetch aggregated data required for analysis. '
            'Use this agent when the user asks a question that requires querying external '
            'databases or large-scale data warehouses.'
        ),
        tools=[sql_tool, summary_tool],
        instruction=load_prompt('sql_agent'),
    )

# Default instance for backward compatibility
sql_agent = get_sql_agent()
