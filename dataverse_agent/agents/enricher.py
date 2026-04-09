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
from dataverse_agent.schemas import EnricherResult, UsageMetadata

# Load the enricher system prompt once at import time
_ENRICHER_SYSTEM_PROMPT = load_prompt('enricher')

# Lazy-initialised client (created on first call)
_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def enrich_query(
    user_text: str,
    df: pd.DataFrame,
    chat_history: list[dict] | None = None,
    dataset_name: str | None = None,
) -> EnricherResult:
    """Rewrite a vague user query into a specific analytical prompt.

    Args:
        user_text: The raw user query.
        df: The current DataFrame for schema context.
        chat_history: Optional list of recent messages for context.
        dataset_name: Optional human-readable dataset name (used in enterprise mode).

    Returns:
        EnricherResult with .enriched_query (str) and .usage (UsageMetadata).
    """
    # Build compact chat history context
    history_context = ""
    if chat_history:
        history_context = "Conversation History (last 5 turns):\n"
        for msg in chat_history[-5:]:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            history_context += f"- {role}: {content[:500]}\n"
        history_context += "\n"

    # Build compact dataset context
    buf = io.StringIO()
    df.info(buf=buf)
    df_context = f"Columns & types:\n{buf.getvalue()}\n\nSample (first 5 rows):\n{df.head(5).to_string()}"

    # Build statistical grounding context
    stats = []
    for col in df.columns:
        nu = df[col].nunique()
        if pd.api.types.is_numeric_dtype(df[col]):
            mi, ma = df[col].min(), df[col].max()
            stats.append(f"- {col}: {nu} unique values | range: [{mi}, {ma}]")
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            mi, ma = df[col].min(), df[col].max()
            stats.append(f"- {col}: {nu} unique values | range: [{mi}, {ma}]")
        else:
            stats.append(f"- {col}: {nu} unique values")
    grounding_context = "Statistical Grounding:\n" + "\n".join(stats)

    dataset_label = f"Dataset name: {dataset_name}\n" if dataset_name else ""
    user_prompt = (
        f"{history_context}"
        f"Raw user query: {user_text}\n\n"
        f"{dataset_label}"
        f"Dataset:\n{df_context}\n\n"
        f"{grounding_context}"
    )

    response = _get_client().models.generate_content(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=_ENRICHER_SYSTEM_PROMPT,
            temperature=0.0,
        ),
    )

    usage = UsageMetadata(
        prompt_token_count=response.usage_metadata.prompt_token_count,
        candidates_token_count=response.usage_metadata.candidates_token_count,
        total_token_count=response.usage_metadata.total_token_count,
    )

    return EnricherResult(
        enriched_query=response.text.strip(),
        usage=usage,
    )
