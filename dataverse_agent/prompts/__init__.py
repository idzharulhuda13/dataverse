"""
External prompt loader for DataVerse multi-agent system.

Prompts are stored as .md files alongside this module.
Each agent loads its own prompt at import time.
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt from a .md file in the prompts directory.
    
    Args:
        name: The prompt filename without extension (e.g., 'orchestrator').
        
    Returns:
        The prompt content as a string.
        
    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()
