import pandas as pd
from dataverse_agent.tools import get_data_summary, set_session_context

def handle_slash_command(prompt: str, df: pd.DataFrame, usage_stats=None):
    """
    Parses and executes slash commands.
    
    Args:
        prompt: The raw user input starting with '/'.
        df: The current modified_df from session state.
        usage_stats: The SessionUsage object from session state.
        
    Returns:
        tuple: (handled: bool, response: str | dict)
               If handled is True, response is the text to show or a dict for special actions.
    """
    if not prompt.startswith('/'):
        return False, None

    # Sync context for tools (e.g. get_data_summary rely on threading.local)
    if df is not None:
        set_session_context(df)

    parts = prompt.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == '/help':
        help_text = """
### ⚡ Available Slash Commands

| Command | Action |
|---------|--------|
| `/summary` | Show a statistical summary of the current dataset. |
| `/columns` | List all columns and their data types. |
| `/head [N]` | Show the first N rows (default: 5). |
| `/export` | Download the current cleaned dataset as CSV. |
| `/undo` | Revert the last data cleaning operation. |
| `/pin` | Pin the last generated visualization to the dashboard. |
| `/clear` | Clear the current chat history. |
| `/cost` | Show detailed token usage and estimated session cost. |
| `/help` | Show this help menu. |
        """
        return True, help_text

    if cmd == '/summary':
        if df is not None:
            return True, f"### 📊 Data Summary\n\n{get_data_summary()}"
        return True, "No dataset loaded yet."

    if cmd == '/columns':
        if df is not None:
            return True, f"### 📁 Column Definitions\n\n```\n{df.dtypes.to_string()}\n```"
        return True, "No dataset loaded yet."

    if cmd == '/head':
        if df is not None:
            n = int(args[0]) if args and args[0].isdigit() else 5
            return True, f"### 🔍 First {n} Rows\n\n{df.head(n).to_markdown()}"
        return True, "No dataset loaded yet."

    if cmd == '/cost':
        if usage_stats:
            cost_text = f"""
### 💰 Session Usage & Cost

- **API Calls:** {usage_stats.api_calls}
- **Conversation Turns:** {usage_stats.turns}
- **Total Tokens:** {usage_stats.total_tokens:,}
- **Estimated Cost:** `${usage_stats.estimated_cost_usd:.4f}`
            """
            return True, cost_text
        return True, "Usage tracking not available."

    # Special actions that need UI-level handling
    if cmd in ('/export', '/undo', '/pin', '/clear'):
        return True, {"action": cmd[1:], "args": args}

    return True, f"Unknown command: `{cmd}`. Type `/help` for available commands."
