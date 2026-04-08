from __future__ import annotations
import traceback
import sys
from typing import Optional, Any
from pydantic import BaseModel

class MitigationGuidance(BaseModel):
    """User-friendly guidance for a specific error."""
    friendly_message: str
    suggested_actions: list[str]
    technical_details: Optional[str] = None

class MitigationManager:
    """Central registry and logic for error categorization and mitigation."""

    # Mapping of common error patterns to friendly summaries and actions
    ERROR_MAP = {
        "ValueError": "I couldn't process some of the data values in your request.",
        "KeyError": "One of the columns or data fields you mentioned wasn't found in this dataset.",
        "SyntaxError": "There was a small logic issue while preparing the analysis.",
        "EmptyDataError": "The dataset or the specific slice I was looking at appears to be empty.",
        "AttributeError": "I encountered an unexpected data structure while performing the analysis.",
        "ServerError": "The AI engine is currently experiencing high demand or is temporarily unavailable.",
        "ClientError": "There was an issue with the request sent to the AI engine.",
        "APIError": "A general connection issue occurred with the AI service.",
        "Exception": "An unexpected issue occurred during the analysis phase."
    }

    SUGGESTED_ACTIONS = [
        "Refresh the page and try your request again.",
        "Wait a minute for the system to stabilize before retrying.",
        "Try rephrasing your question or simplifying the visualization request.",
        "If the issue persists, please reach out to the project creator."
    ]

    @classmethod
    def get_guidance(cls, error: Exception | str) -> MitigationGuidance:
        """Produce user-friendly guidance from a technical exception."""
        error_name = type(error).__name__ if isinstance(error, Exception) else "Exception"
        error_msg = str(error)
        
        # Determine the friendly summary
        summary = cls.ERROR_MAP.get(error_name, cls.ERROR_MAP["Exception"])
        
        # Special logic for certain common error sub-patterns
        if "not found in axis" in error_msg or "column" in error_msg.lower():
            summary = cls.ERROR_MAP["KeyError"]
        elif "empty" in error_msg.lower():
            summary = cls.ERROR_MAP["EmptyDataError"]

        # Capture technical details for observability
        tech_details = None
        if isinstance(error, Exception):
            tech_details = "".join(traceback.format_exception(*sys.exc_info()))
        else:
            tech_details = error_msg

        return MitigationGuidance(
            friendly_message=summary,
            suggested_actions=cls.SUGGESTED_ACTIONS,
            technical_details=tech_details
        )

    @classmethod
    def log_technical_error(cls, error: Exception | str, context: str = "General"):
        """Log the full technical error to the terminal for developers."""
        print(f"\n--- [TRAPPED ERROR: {context}] ---")
        if isinstance(error, Exception):
            traceback.print_exc()
        else:
            print(f"Error: {error}")
        print("-----------------------------------\n")

def error_guardrail(context: str = "Tool"):
    """Decorator to wrap functions and provide unified error mitigation."""
    def decorator(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                MitigationManager.log_technical_error(e, context=f"{context}.{func.__name__}")
                # Return a structured error string that UI/Agent can recognize
                guidance = MitigationManager.get_guidance(e)
                return f"ERROR_MITIGATION_TRIGGERED: {guidance.model_dump_json()}"
        return wrapper
    return decorator
