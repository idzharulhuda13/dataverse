# LLM.md — DataVerse Project Context

> **Last updated:** 2026-04-05
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
| **Warehouse** | DuckDB + dbt (`dbt/dataverse/dataverse_warehouse.duckdb`) |
| **Visualization** | Seaborn + Matplotlib |
| **Forecasting** | Facebook Prophet |
| **Package Manager** | `uv` (lockfile: `uv.lock`) |
| **Python** | ≥ 3.11 |

### Key Dependencies (`pyproject.toml`)
```
google-adk>=1.27.2, google-genai>=1.68.0, gpt4all>=2.8.2, dbt-duckdb>=1.10.1,
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
├── dbt/
│   └── dataverse/                 ← dbt models, config, and dataverse_warehouse.duckdb
│
├── dataverse_agent/               ← Agent package
│   ├── __init__.py                ← Imports agent.py
│   ├── agent.py                   ← Re-exports root_agent from agents/
│   ├── tools.py                   ← ADK FunctionTools (create_visualization, get_data_summary, create_table, execute_python_code_fallback)
│   ├── messages.py                ← Centralized chat messages (intro, no-csv, session-resume, upload-landing, analyzing)
│   ├── usage.py                   ← SessionUsage dataclass: token tracking, turn counting, cost estimation, activity trace
│   ├── commands.py                ← Slash command parser & handler (/summary, /export, /undo, /pin, /clear, /cost, /help)
│   ├── agents/                    ← Multi-agent definitions
│   │   ├── __init__.py            ← Exports orchestrator as root_agent
│   │   ├── orchestrator.py        ← Central router agent (delegates to sub-agents)
│   │   ├── visual_analyst.py      ← Analysis + premium chart creation
│   │   ├── forecast.py            ← Time-series forecasting (Prophet)
│   │   ├── cleaning.py            ← Data transformations & quality
│   │   └── enricher.py            ← Stateless query rewriting/alignment (direct Gemini call)
│   ├── infographic.py             ← Agent-driven infographic generation and PDF rendering
│   └── prompts/                   ← Markdown prompt files for each agent
│       ├── __init__.py            ← load_prompt(name) utility
│       ├── orchestrator.md
│       ├── visual_analyst.md
│       ├── forecast.md
│       ├── cleaning.md
│       └── enricher.md
│
├── models/                        ← Core utilities
│   ├── duckdb_connector.py        ← Warehouse table registry and DuckDB loader
│   ├── sandbox.py                 ← 4-layer secure Python execution sandbox
│   ├── utils.py                   ← CSV loading, code extraction, execute_python_code wrapper
│   ├── prompt_template.py         ← Legacy single-agent prompt template
│   └── *.gguf                     ← Local LLM model files (git-ignored)
│
├── tests/
│   ├── stress_test.py             ← Comprehensive agent pipeline benchmarking
│   ├── test_sandbox.py            ← Security test suite for the sandbox
│   ├── test_tools.py              ← ADK tool unit tests
│   ├── test_utils.py              ← DataFrame and string utility unit tests
│   ├── test_load_dataframe.py     ← Multi-format data loading tests
│   ├── test_dashboard.py          ← UI integration tests
│   └── stress_results/            ← Artifacts from stress tests
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

- **Query Enricher:** Stateless, single-shot Gemini API call (`enrich_query()` in `dataverse_agent/agents/enricher.py`). Rewrites vague user queries into specific analytical prompts aligned with the dataset schema. Also accepts `chat_history` (last 5 messages) for context-aware follow-up resolution. Returns a tuple `(enriched_str, usage_dict)` — usage is fed back to `SessionUsage.record_api_call()`. Not an ADK agent — uses `google.genai.Client` directly for speed.
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

Four FunctionTools registered with ADK (exported as `TOOLS` list):

1. **`create_visualization(chart_type, x_column, y_column, hue, estimator, title, subtitle, sort_order)`**
   - Generates Seaborn/Matplotlib charts: bar, line, scatter, hist, box, violin, heatmap, pie, stacked_area, slope
   - Premium styling: custom palette, human-readable axis labels (`_format_label`), human-readable tick formatting (`_human_format`), auto-rotation
   - Smart axis detection: year columns → integer labels; month columns → Jan/Feb/…; percentage columns → % format
   - Bar charts: auto-sort by aggregated value, bar labels, optional error bars
   - Slope charts: two-point comparison by hue; stacked area charts: pivot + stackplot
   - Stores figures in thread-local `_local.figures` list

2. **`get_data_summary()`**
   - Returns DataFrame info + first 5 rows as text

3. **`create_table(table_code, title, subtitle)`**
   - Executes Python code via sandbox; code **must** assign result to `display_df`
   - Stores the resulting DataFrame in `_local.display_df` for interactive chat rendering
   - Used for pivot tables, summaries, and any copyable tabular output

4. **`execute_python_code_fallback(code)`**
   - Runs arbitrary Python through the sandbox (`models/sandbox.py`)
   - Captures: printed output, matplotlib figures
   - `viz_df` → stored as `_local.viz_temp_df` (temp scoped, never persisted)
   - `final_df` → stored as `_local.final_df` (cleaning agent persistence)
   - `display_df` → stored as `_local.display_df` (standalone table for chat)

**Thread-local state management:**
- `set_session_context(df)` — registers DataFrame + fresh figures list + clears `display_df` for current thread
- `get_session_figures()` — retrieves and clears generated figures; also clears `viz_temp_df`
- `get_final_df()` — retrieves and clears persisted DataFrame (`final_df`) from cleaning agent (if any)
- `get_display_df()` — retrieves and clears standalone table (`display_df`) for chat rendering
- `get_session_data_summary()` — generates statistical summary (sum/mean/max/min for numerics, top-5 values for categoricals) for Vision Agent grounding

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
2. **Sidebar** — Account Management (admin login/logout), Session Manager (create/switch/rename/delete), Usage & Budget tracking (guest countdown vs. admin full dashboard), Feature Flags (Observability + Usage Budget toggles — admin only)
3. **`_run_agent_and_save()`** — Core function: budget check → sends prompt to ADK runner → captures response + figures + `final_df` + `display_df` → records token usage → does a **second pass** for chart insights (sends chart image + data grounding summary to LLM) → attaches observability trace
4. **Upload-First Landing** — If no data loaded, shows centered file uploader hero. On upload: Phase 1 (Cleaning Agent auto-clean), Phase 2 (exploratory insights recommendation)
5. **Slash Command Handler** — Intercepts `/command` prefixed messages and routes to `handle_slash_command()` before the normal agent pipeline
6. **Chat + Dashboard Layout** — 4:6 column split. Left: chat with pin buttons, table rendering, trace viewer. Right: 2-column pinned dashboard grid

**Session data structure:**
```python
sessions[sid] = {
    "name": str,
    "created_at": datetime,
    "messages": list[dict],      # {role, content, figure?, insight?, table?, trace?, enriched_query?, action?}
    "modified_df": DataFrame | None,
    "previous_df": DataFrame | None,  # For undo support
    "dashboard_items": list[dict], # {type, figure, code, insight}
    "usage": SessionUsage,        # Token + turn tracking
}
```

**Global session_state keys (beyond sessions dict):**
```python
st.session_state.is_logged_in       # bool — admin auth state
st.session_state.show_observability # bool — show activity trace (admin only)
st.session_state.show_usage_budget  # bool — show budget panel (admin only)
st.session_state.enterprise_mode    # bool — toggle between CSV upload and predefined DuckDB marts
st.session_state.max_budget_turns   # int — turn limit before blocking
st.session_state.original_df        # DataFrame — immutable backup from initial upload (restore point)
```

### `dataverse_agent/messages.py` — Chat Messages

Randomized message pools:
- `INTRO_MESSAGES` — Welcome messages
- `NO_CSV_MESSAGES` — Upload prompts
- `SESSION_RESUMED_MESSAGES` — Session switch greetings
- `UPLOAD_LANDING_MESSAGES` — Hero uploader text
- `ANALYZING_DATA_MESSAGES` — Spinner text during auto-analysis

### `dataverse_agent/usage.py` — Session Usage Tracking

- **`TraceEvent`** dataclass: `timestamp`, `event_type` (start/tool_call/vision_start/vision_complete/complete), `agent_name`, `detail`, `metadata` (tool args, code)
- **`SessionUsage`** dataclass: tracks `api_calls`, `turns`, `input_tokens`, `output_tokens`, `image_tokens`, and `trace: list[TraceEvent]`
  - `.total_tokens` property — sum of all token types
  - `.estimated_cost_usd` property — rough cost using Gemini Flash pricing ($0.075/1M input, $0.30/1M output)
  - `.record_api_call(usage_metadata)` — increments token counters from ADK event metadata
  - `.record_turn()` — increments conversation turn counter
  - `.record_trace(event_type, agent_name, detail, metadata)` — appends a TraceEvent
  - `.clear_trace()` — resets trace list at start of new request

### `dataverse_agent/infographic.py` — Agent-driven Infographic

Handles generating magazine-style infographic PDFs. Two-step pipeline:
1. `generate_infographic_content`: Sends all pinned chart images via Gemini Vision API to get a structured JSON narrative (title, subtitle, takeaways, etc.).
2. `render_infographic_pdf`: Composes the agent-generated narrative and chart figures into a styled A4 PDF utilizing `reportlab`.

### `dataverse_agent/commands.py` — Slash Command System

`handle_slash_command(prompt, df, usage_stats) → (handled: bool, response: str | dict)`

Deterministic operations that bypass the LLM pipeline entirely:

| Command | Behaviour |
|---|---|
| `/help` | Returns formatted command reference table |
| `/summary` | Returns `get_data_summary()` output |
| `/columns` | Returns `df.dtypes` listing |
| `/head [N]` | Returns first N rows as markdown (default 5) |
| `/cost` | Returns token usage + estimated cost from `SessionUsage` |
| `/export` | Returns `{"action": "export"}` for UI download button |
| `/infographic` | Returns `{"action": "infographic"}` for generating a PDF infographic |
| `/undo` | Returns `{"action": "undo"}` — dashboard restores `previous_df` |
| `/pin` | Returns `{"action": "pin"}` — dashboard pins last figure |
| `/clear` | Returns `{"action": "clear"}` — dashboard clears message history |

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
Tests cover: `test_sandbox.py` (security), `test_tools.py` (ADK tools), `test_utils.py` (utilities), `test_load_dataframe.py` (multi-format loading), `test_dashboard.py` (UI integration).

### Running the Stress Test
```bash
uv run python tests/stress_test.py --delay 5
```
Outputs a Markdown report to `tests/stress_results/stress_test_report.md`. Accepts `--dataset`, `--output-dir`, `--questions`, and `--delay` flags.

---

## Configuration

| Source | Key | Purpose |
|---|---|---|
| `.streamlit/secrets.toml` | `GEMINI_API_KEY` | Google Gemini API key |
| `.streamlit/secrets.toml` | `GEMINI_MODEL` | Gemini model name |
| `.streamlit/secrets.toml` | `ADMIN_USERNAME` | Admin login username |
| `.streamlit/secrets.toml` | `ADMIN_PASSWORD` | Admin login password |
| `.env` (root) | Env vars | General env config |
| `dataverse_agent/.env` | Env vars | Agent-specific env |

---

## Important Patterns & Conventions

1. **Thread-local storage** — The DataFrame and figures are passed between Streamlit's main thread and ADK tool execution via `threading.local()` in `tools.py`
2. **Cleaning agent persistence** — When cleaning agent code assigns to `final_df`, the sandbox captures it via `exec_globals.get("final_df")`, and the dashboard retrieves it via `get_final_df()` then updates `st.session_state.modified_df`. A **sanity guard** (`is_safe` check) prevents narrow filtered subsets from overwriting the full dataset.
3. **Undo support** — Before overwriting `modified_df` with a cleaned result, the dashboard saves the previous version into `st.session_state.previous_df`. `/undo` command restores it.
4. **Second-pass insights** — After each chart is generated, the dashboard sends the chart image + `get_session_data_summary()` (numeric/categorical grounding) back to the LLM for a focused data insight (📊 Observation + 💡 Interpretation framework)
5. **Self-correcting retry** — Errors from tool execution are fed back to the LLM for autonomous code fixing
6. **Prompt-as-markdown** — Agent prompts are `.md` files loaded at import time, not Python strings
7. **Backward compatibility** — `dataverse_agent/agent.py` re-exports `root_agent` from `agents/` so both the dashboard and ADK Runner can import it
8. **Slash commands bypass LLM** — `/command` inputs are intercepted by `handle_slash_command()` before enrichment/agent pipeline, providing instant deterministic responses for power users
9. **Usage tracking** — Every `runner.run_async()` event that has `usage_metadata` is recorded by `SessionUsage.record_api_call()`. The enricher also returns usage metadata which is recorded separately. Turns are incremented once per `_run_agent_and_save()` call.
10. **Admin auth gate** — `st.session_state.is_logged_in` (verified against `st.secrets.ADMIN_USERNAME/ADMIN_PASSWORD`) gates access to Observability and Usage/Budget panels. Guest users always see a simplified turn countdown.
11. **Display tables** — `create_table` tool and `display_df` variable in sandbox produce interactive `st.dataframe()` widgets in chat, separate from the persistent session dataset. Tool calls collapse raw execution logs when a table or figure is present.
12. **Enricher chat context** — `enrich_query()` accepts `chat_history` (last 5 messages) to resolve pronouns and follow-up questions relative to previous turns. Returns `(enriched_str, usage_dict)` tuple.

---

## Legacy Files (Not Primary)

- `streamlit_chatbot.py` — Original local GPT4All-based chatbot (uses local `.gguf` models)
- `streamlit_chatbot_api.py` — Gemini API direct chatbot (no ADK, no multi-agent)
- `models/prompt_template.py` — Legacy single-agent prompt template (used by legacy chatbots)
- `models/*.gguf` — Local LLM model files (DeepSeek, Mistral, custom Claude distill — git-ignored)

These are kept for reference but **`streamlit_agent_dashboard.py` is the primary application**.
