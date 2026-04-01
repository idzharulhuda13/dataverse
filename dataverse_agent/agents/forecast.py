"""
Forecast Agent — Time-series forecasting specialist using Prophet.
"""
import os

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from dataverse_agent.tools import execute_python_code_fallback
from dataverse_agent.prompts import load_prompt

forecast_agent = Agent(
    model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
    name='forecast_agent',
    description=(
        'Handles time-series forecasting and predictions using Facebook Prophet. '
        'Use this agent when the user asks to forecast, predict future values, '
        'analyze trends over time, or perform any time-series analysis. '
        'Requires a date/time column and a numeric target column in the dataset.'
    ),
    tools=[
        FunctionTool(func=execute_python_code_fallback),
    ],
    instruction=load_prompt('forecast'),
)
