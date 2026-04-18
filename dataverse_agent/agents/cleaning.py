"""
Data Cleaning Agent — Data transformation and quality specialist.
"""
import os

from google.adk.agents import Agent
from google.genai import types
from dataverse_agent.tools import summary_tool, fallback_tool, stats_tool
from dataverse_agent.prompts import load_prompt

def get_cleaning_agent() -> Agent:
    """Returns a fresh instance of the Cleaning Agent."""
    return Agent(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
        generate_content_config=types.GenerateContentConfig(temperature=0.0),
        name='cleaning_agent',
        description=(
            'Suggests and applies data cleaning transformations: handling missing values, '
            'removing duplicates, converting data types, filtering outliers, creating '
            'derived columns (like Z-scores using stats_tool), renaming columns, and reshaping data. '
            'Use this agent when the user asks to clean, fix, transform, filter, or prepare the data.'
        ),
        tools=[summary_tool, fallback_tool, stats_tool],
        instruction=load_prompt('cleaning'),
    )

# Default instance for backward compatibility
cleaning_agent = get_cleaning_agent()
