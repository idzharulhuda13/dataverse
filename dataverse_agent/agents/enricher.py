"""
Question Enricher — Single-shot query rewriter using direct Gemini API.

No ADK Runner, no sessions, no streaming. Just a fast, stateless call to
rewrite vague user queries into specific analytical prompts aligned with
the dataset schema.
"""
import io
import os

import pandas as pd
from google import genai
from google.genai import types

from dataverse_agent.prompts import load_prompt

# Load the enricher system prompt once at import time
_ENRICHER_SYSTEM_PROMPT = load_prompt('enricher')

# Lazy-initialised client (created on first call)
_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def enrich_query(user_text: str, df: pd.DataFrame) -> tuple[str, dict]:
    """Rewrite a vague user query into a specific analytical prompt.

    Args:
        user_text: The raw user query.
        df: The current DataFrame for schema context.

    Returns:
        A tuple of (enriched_query_string, usage_metadata_dict).
    """
    # Build compact dataset context
    buf = io.StringIO()
    df.info(buf=buf)
    df_context = f"Columns & types:\n{buf.getvalue()}\n\nSample (first 5 rows):\n{df.head(5).to_string()}"

    user_prompt = (
        f"Raw query: {user_text}\n\n"
        f"Dataset:\n{df_context}"
    )

    response = _get_client().models.generate_content(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=_ENRICHER_SYSTEM_PROMPT,
            temperature=0.0,
        ),
    )
    
    # Extract usage metadata for token tracking
    usage = {
        "prompt_token_count": response.usage_metadata.prompt_token_count,
        "candidates_token_count": response.usage_metadata.candidates_token_count,
        "total_token_count": response.usage_metadata.total_token_count,
    }
    
    return response.text.strip(), usage
