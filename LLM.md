# LLM.md — DataVerse Project Context

> **Last updated:** 2026-04-01
> This file gives LLM coding assistants instant context about the DataVerse project so they can be productive without scanning the entire codebase.

---

## What is DataVerse?

DataVerse is an **AI-powered, conversational data analysis and visualization tool**. Users upload a CSV file and chat with an AI agent to explore, visualize, forecast, and clean their data. It is built with **Streamlit** (frontend), **Google ADK** (agent framework), and the **Google Gemini API** (LLM).

**Live deployment:** [dataverse-app.streamlit.app](https://dataverse-app.streamlit.app/)

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend / UI** | Streamlit (wide layout, `st.chat_message`, `st.pyplot`) |
| **Agent Framework** | Google ADK (`google.adk`) — `Runner`, `Agent`, `FunctionTool` |
| **LLM** | Google Gemini (model from `GEMINI_MODEL` env var, default: `gemini-3.1-flash-lite-preview`) |
| **Data** | Pandas DataFrames (CSV, Excel, Parquet, JSON, TSV) |
| **Visualization** | Seaborn + Matplotlib |
| **Forecasting** | Facebook Prophet |
| **Package Manager** | `uv` (lockfile: `uv.lock`) |
| **Python** | ≥ 3.11 |

### Key Dependencies (`pyproject.toml`)
```
google-adk>=1.27.2, google-genai>=1.68.0, gpt4all>=2.8.2,
matplotlib>=3.10.8, openpyxl>=3.1.0, pandas>=2.3.3, prophet>=1.3.0,
python-dotenv>=1.2.2, seaborn>=0.13.2, streamlit>=1.55.0
```
Dev: `pytest>=9.0.2`

---

## Project Structure

```
DataVerse/
├── streamlit_agent_dashboard.py   ← PRIMARY APP — Multi-agent dashboard (run this)
├── streamlit_chatbot.py           ← Legacy: local GPT4All chatbot (not primary)
├── streamlit_chatbot_api.py       ← Legacy: Gemini API chatbot (not primary)
│
├── dataverse_agent/               ← Agent package
│   ├── __init__.py                ← Imports agent.py
│   ├── agent.py                   ← Re-exports root_agent from agents/
│   ├── tools.py                   ← ADK FunctionTools (create_visualization, get_data_summary, execute_python_code_fallback)
│   ├── messages.py                ← Centralized chat messages (intro, no-csv, session-resume, upload-landing, analyzing)
│   ├── agents/                    ← Multi-agent definitions
│   │   ├── __init__.py            ← Exports orchestrator as root_agent
│   │   ├── orchestrator.py        ← Central router agent (delegates to sub-agents)
│   │   ├── visual_analyst.py      ← Analysis + premium chart creation
│   │   ├── forecast.py            ← Time-series forecasting (Prophet)
│   │   └── cleaning.py            ← Data transformations & quality
│   └── prompts/                   ← Markdown prompt files for each agent
│       ├── __init__.py            ← load_prompt(name) utility
│       ├── orchestrator.md
│       ├── visual_analyst.md
│       ├── forecast.md
│       └── cleaning.md
│
├── models/                        ← Core utilities
│   ├── sandbox.py                 ← 4-layer secure Python execution sandbox
│   ├── utils.py                   ← CSV loading, code extraction, execute_python_code wrapper
│   ├── prompt_template.py         ← Legacy single-agent prompt template
│   └── *.gguf                     ← Local LLM model files (git-ignored)
│
├── tests/
│   └── test_sandbox.py            ← Security test suite for the sandbox
│
├── data/                          ← Sample CSV datasets
├── .streamlit/                    ← Streamlit config + secrets.toml (git-ignored)
├── Makefile                       ← make install/run/clean/tunnel/stop
├── pyproject.toml
└── uv.lock
```

---

## Architecture

### Multi-Agent System

```
User Chat Input
      │
      ▼
┌──────────────────┐
│ Query Enricher   │  ← Direct Gemini API call (not an ADK agent)
│ (stateless)      │  ← Rewrites & aligns query to dataset schema
└──────┬───────────┘
       │ (Enriched Query)
       ▼
┌──────────────────────────────────────┐
│  Orchestrator (root_agent)           │  ← Routes requests to specialists
│  Model: Gemini                       │
│  No direct tools — delegates only    │
└──────┬────────────┬──────────┬───────┘
       │            │          │
       ▼            ▼          ▼
 ┌───────────┐ ┌──────────┐ ┌──────────┐
 │ Visual    │ │ Forecast │ │ Cleaning │
 │ Analyst   │ │ Agent    │ │ Agent    │
 │           │ │          │ │          │
 │ Tools:    │ │ Tools:   │ │ Tools:   │
 │ • viz     │ │ • code   │ │ • summary│
 │ • summary │ │ fallback │ │ • code   │
 │ • code    │ │          │ │ fallback │
 │ fallback  │ │          │ │          │
 └───────────┘ └──────────┘ └──────────┘
```

- **Query Enricher:** Stateless, single-shot Gemini API call (`enrich_query()` in `dataverse_agent/agents/enricher.py`). Rewrites vague user queries into specific analytical prompts aligned with the dataset schema. Not an ADK agent — uses `google.genai.Client` directly for speed.
- **Orchestrator:** Analyzes intent, delegates to the correct sub-agent. Has no tools itself.
- **Visual Analyst:** Stats analysis + chart creation. Has `create_visualization`, `get_data_summary`, `execute_python_code_fallback`.
- **Forecast Agent:** Time-series predictions via Prophet. Has `execute_python_code_fallback` only.
- **Cleaning Agent:** Data transformations (missing values, duplicates, types, filtering). Has `get_data_summary` + `execute_python_code_fallback`. Persists cleaned DataFrames via `final_df` variable capture.

### Agent Configuration
- Each agent is defined in `dataverse_agent/agents/<name>.py`
- Each agent loads its system prompt from `dataverse_agent/prompts/<name>.md`
- Prompt loading: `load_prompt('name')` reads `prompts/<name>.md`
- All agents use the model from `os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview')`

---

## Key Modules Explained

### `dataverse_agent/tools.py` — Agent Tools

Three FunctionTools registered with ADK:

1. **`create_visualization(chart_type, x_column, y_column, hue, title, subtitle)`**
   - Generates Seaborn/Matplotlib charts: bar, line, scatter, hist, box, violin, heatmap, pie
   - Premium styling: custom palette, human-readable axis labels (`_format_label`), human-readable tick formatting (`_human_format`), auto-rotation
   - Stores figures in thread-local `_local.figures` list

2. **`get_data_summary()`**
   - Returns DataFrame info + first 5 rows as text

3. **`execute_python_code_fallback(code)`**
   - Runs arbitrary Python through the sandbox (`models/sandbox.py`)
   - Captures: printed output, matplotlib figures, `final_df` (for cleaning agent persistence)

**Thread-local state management:**
- `set_session_context(df)` — registers DataFrame + fresh figures list for current thread
- `get_session_figures()` — retrieves and clears generated figures
- `get_cleaned_df()` — retrieves cleaned DataFrame from cleaning agent (if any)

### `models/sandbox.py` — 4-Layer Security Sandbox

Public API: `safe_execute(code, df, timeout=30) → SandboxResult`

| Layer | Name | Mechanism |
|---|---|---|
| 1 | Blocklists | `BLOCKED_MODULES` (os, subprocess, socket, etc.), `BLOCKED_BUILTINS` (exec, eval, open, etc.) |
| 2 | AST Analysis | `_SecurityVisitor` walks AST pre-execution: catches blocked imports, `__import__()`, blocked builtins, dunder attribute access |
| 3 | Restricted Namespace | `_build_exec_namespace(df)` — only provides `df`, `pd`, `np`, `plt`, `sns` + safe builtins. `_make_restricted_import()` gates runtime imports to `ALLOWED_MODULES` only |
| 4 | Resource Limits | 30-second thread timeout, 50KB output truncation |

**`SandboxResult` dataclass:** `output`, `dataframe` (final_df), `figure`, `error`, `blocked`, `blocked_reason`

**Whitelisted runtime imports (`ALLOWED_MODULES`):** pandas, numpy, matplotlib, seaborn, prophet, math, statistics, collections, itertools, functools, datetime, re, string, textwrap, decimal, fractions, operator, copy, json, csv

### `models/utils.py` — Utility Functions

- `load_dataframe(file, sheet_name=0)` → `(DataFrame | None, error | None)` — multi-format loader (CSV, Excel, Parquet, JSON, TSV) with 200 MB size limit
- `get_excel_sheet_names(file)` → `list[str]` — returns sheet names for multi-sheet Excel files
- `load_csv(file)` → deprecated alias for `load_dataframe()`
- `execute_python_code(code, df)` → `(output, final_df, figure)` — wrapper around `safe_execute`
- `extract_non_code_text(reply)` — strips code blocks from LLM response
- `extract_python_code_blocks(reply)` — extracts Python code blocks from LLM response
- `make_stop_on_token_callback_exit_code_block()` — GPT4All generation callback (legacy)

### `streamlit_agent_dashboard.py` — Main Application

**Sections:**
1. **Session State Init** — API key from `st.secrets`, ADK `Runner` + `InMemorySessionService`
2. **Sidebar Session Manager** — Create / switch / rename / delete sessions. Each session stores: messages, modified_df, dashboard_items
3. **`_run_agent_and_save()`** — Core function: sends prompt to ADK runner, captures response + figures + cleaned_df. Does a **second pass** for chart insights (sends chart image back to LLM)
4. **Upload-First Landing** — If no data loaded, shows centered file uploader hero. On upload, auto-triggers agent analysis
5. **Chat + Dashboard Layout** — 4:6 column split. Left: chat with pin buttons. Right: 2-column pinned dashboard grid

**Session data structure:**
```python
sessions[sid] = {
    "name": str,
    "created_at": datetime,
    "messages": list[dict],      # {role, content, figure?, insight?, output?}
    "modified_df": DataFrame | None,
    "dashboard_items": list[dict] # {type, figure, code, insight}
}
```

### `dataverse_agent/messages.py` — Chat Messages

Randomized message pools:
- `INTRO_MESSAGES` — Welcome messages
- `NO_CSV_MESSAGES` — Upload prompts
- `SESSION_RESUMED_MESSAGES` — Session switch greetings
- `UPLOAD_LANDING_MESSAGES` — Hero uploader text
- `ANALYZING_DATA_MESSAGES` — Spinner text during auto-analysis

---

## How to Run

```bash
# Install dependencies
uv sync

# Set up secrets
# Create .streamlit/secrets.toml with:
#   GEMINI_API_KEY = "your-key"
#   GEMINI_MODEL = "your-model"

# Run the main dashboard
uv run streamlit run streamlit_agent_dashboard.py

# Or use Makefile
make run
```

### Makefile Commands

| Command | Action |
|---|---|
| `make install` | `uv sync` |
| `make run` | Run `streamlit_agent_dashboard.py` |
| `make clean` | Remove caches, `.venv`, deprecated dirs |
| `make tunnel` | Start ngrok tunnel (fixed domain) |
| `make stop` | Kill Streamlit + ngrok processes |

### Running Tests
```bash
uv run pytest
```
Tests are in `tests/test_sandbox.py` — comprehensive security tests for the sandbox.

---

## Configuration

| Source | Key | Purpose |
|---|---|---|
| `.streamlit/secrets.toml` | `GEMINI_API_KEY` | Google Gemini API key |
| `.streamlit/secrets.toml` | `GEMINI_MODEL` | Gemini model name |
| `.env` (root) | Env vars | General env config |
| `dataverse_agent/.env` | Env vars | Agent-specific env |

---

## Important Patterns & Conventions

1. **Thread-local storage** — The DataFrame and figures are passed between Streamlit's main thread and ADK tool execution via `threading.local()` in `tools.py`
2. **Cleaning agent persistence** — When cleaning agent code assigns to `final_df`, the sandbox captures it via `exec_globals.get("final_df")`, and the dashboard updates `st.session_state.modified_df`
3. **Second-pass insights** — After each chart is generated, the dashboard sends the chart image back to the LLM for a focused data insight (observation + interpretation)
4. **Self-correcting retry** — Errors from tool execution are fed back to the LLM for autonomous code fixing
5. **Prompt-as-markdown** — Agent prompts are `.md` files loaded at import time, not Python strings
6. **Backward compatibility** — `dataverse_agent/agent.py` re-exports `root_agent` from `agents/` so both the dashboard and ADK Runner can import it

---

## Legacy Files (Not Primary)

- `streamlit_chatbot.py` — Original local GPT4All-based chatbot (uses local `.gguf` models)
- `streamlit_chatbot_api.py` — Gemini API direct chatbot (no ADK, no multi-agent)
- `models/prompt_template.py` — Legacy single-agent prompt template (used by legacy chatbots)
- `models/*.gguf` — Local LLM model files (DeepSeek, Mistral, custom Claude distill — git-ignored)

These are kept for reference but **`streamlit_agent_dashboard.py` is the primary application**.
