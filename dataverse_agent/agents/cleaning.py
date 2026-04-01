"""
Data Cleaning Agent — Data transformation and quality specialist.
"""
import os

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from dataverse_agent.tools import get_data_summary, execute_python_code_fallback
from dataverse_agent.prompts import load_prompt

cleaning_agent = Agent(
    model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
    name='cleaning_agent',
    description=(
        'Suggests and applies data cleaning transformations: handling missing values, '
        'removing duplicates, converting data types, filtering outliers, creating '
        'derived columns, renaming columns, and reshaping data. Use this agent when '
        'the user asks to clean, fix, transform, filter, or prepare the data.'
    ),
    tools=[
        FunctionTool(func=get_data_summary),
        FunctionTool(func=execute_python_code_fallback),
    ],
    instruction=load_prompt('cleaning'),
)
