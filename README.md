<p align="center"><h1 align="center">DATAVERSE</h1></p>
<p align="center">
	<em><code>❯ Chat with Your CSV.</code></em>
</p>
<p align="center">
  <a href="https://dataverse-app.streamlit.app/" target="_blank">
      <img alt="Streamlit App" src="https://static.streamlit.io/badges/streamlit_badge_black_white.svg">
  </a>
	<img src="https://img.shields.io/github/license/idzharulhuda13/dataverse?style=default&logo=opensourceinitiative&logoColor=white&color=0080ff" alt="license">
	<img src="https://img.shields.io/github/last-commit/idzharulhuda13/dataverse?style=default&logo=git&logoColor=white&color=0080ff" alt="last-commit">
	<img src="https://img.shields.io/github/languages/top/idzharulhuda13/dataverse?style=default&color=0080ff" alt="repo-top-language">
	<img src="https://img.shields.io/github/languages/count/idzharulhuda13/dataverse?style=default&color=0080ff" alt="repo-language-count">
</p>
<p align="center"><!-- default option, no dependency badges. -->
</p>
<p align="center">
	<!-- default option, no dependency badges. -->
</p>
<br>

##  Table of Contents

- [ Overview](#overview)
- [ Features](#features)
- [ Security & Sandboxing](#security--sandboxing)
- [ Project Structure](#project-structure)
- [ Getting Started](#getting-started)
  - [ Prerequisites](#prerequisites)
  - [ Installation](#installation)
  - [ Usage](#usage)

---

##  Overview

**Dataverse - Data Explorer** (Nano-Dataverse) is an interactive, **AI-powered data analysis and visualization tool** built with **Streamlit** and the **Google Gemini API** (via the **Google ADK Framework**).

This application allows users to upload a **CSV file** and then communicate with a **context-aware chat assistant** to perform complex data exploration tasks. The AI intelligently suggests analyses, uses **structured tools** to create charts, writes and executes safe **Python code fallbacks** (using libraries like **Pandas** and **Seaborn**) on the uploaded DataFrame, and visualizes the results directly within the app. It acts as a powerful, conversational data analyst at your fingertips.

---

##  Features

### Conversational Data Analysis
* **AI Analyst Chat Interface:** Engage with a powerful chat assistant to ask natural language questions about your data.
* **Context-Aware Responses:** The AI is initialized with your DataFrame's structure to provide relevant and precise suggestions from the start.
* **Randomized Welcome Messages:** Every new session greets you with a unique, randomized welcome message for a fresh experience.
* **CSV Upload Guard:** The agent enforces uploading a CSV file before any analysis can begin, ensuring data is always present before queries.

### Multi-Agent Architecture
* **Orchestrator Agent:** The central router that analyzes complex user requests and seamlessly delegates tasks to specialized sub-agents.
* **Specialized Sub-Agents:**
    * **Visual Analyst Agent:** Focuses strictly on statistical analysis and generating premium, highly-accurate visualizations.
    * **Forecasting Agent:** Specializes in time-series predictions, authorized to utilize the `prophet` library inside the execution sandbox.
    * **Cleaning Agent:** Handles data transformations, imputation, filtering, and persisting the cleaned state back to the dashboard session.
* **Improved Predictability:** By giving each agent a narrow scope, a specific set of tools, and a highly tuned system prompt, the AI's behavior becomes much more predictable, safe, and accurate.


### Session Management
* **Persistent Chat Sessions:** Create and switch between multiple independent chat sessions — each with its own conversation history, uploaded dataset, and pinned dashboard items.
* **Session Sidebar:** The sidebar lists all sessions, showing creation time, message count, and data status at a glance.
* **Session Resume Messages:** When you switch back to a previous session, the agent greets you with a contextual "welcome back" message.
* **Rename Sessions:** Customize the name of any active session directly from the sidebar.
* **Delete Sessions:** Remove any non-active session with a single click (keeping at least one session always active).
* **Auto-Save:** Session state is automatically saved after every message exchange.

### Agentic Tool Execution & Visualization
* **Structured Tool Calling:** Powered by the Google ADK Framework, the agent uses structured tools (`create_visualization`, `get_data_summary`, etc.) to interact with the data efficiently instead of relying solely on raw code generation.
* **Self-Correcting Error Recovery:** Includes an intelligent retry loop; if code execution or a tool fails, the error is fed back to the LLM allowing the agent to fix its own code autonomously.
* **4-Layer Sandboxed Execution:** When complex logic requires `execute_python_code_fallback`, code is executed within a **secure sandbox** that features:
    * **AST Static Analysis:** Pre-screens code for malicious patterns before execution.
    * **Gated Imports:** Restricts runtime imports to only safe analytics libraries (pandas, numpy, seaborn, etc.).
    * **Restricted Namespace:** Blocks dangerous built-ins like `eval`, `exec`, and `open`.
    * **Resource Control:** Implements a 30-second execution timeout and output truncation.
* **Live Visualization:** Automatically displays generated **Seaborn/Matplotlib plots** directly in the chat thread.
* **Chart Insights (Second Pass):** After each chart is generated, the agent performs a second AI pass to provide concise, data-driven business insights extracted from the visualization.
* **Code and Output Display:** Shows both the **plain-text response** from the AI *and* the actual **execution output** (or errors) in code blocks for full transparency.

### Dashboard Pinning
* **Pin to Dashboard:** Any generated visualization can be pinned to a live dashboard panel displayed alongside the chat.
* **2-Column Dashboard Layout:** Pinned charts are arranged in a responsive 2-column grid with insights attached.
* **Remove from Dashboard:** Easily remove pinned items directly from the dashboard view.

### Data Management & Tech Stack
* **CSV Upload via Chat Input:** Upload your dataset directly within the chat input box for a seamless workflow.
* **Data Isolation:** Maintains a separate copy of the DataFrame for safe code execution, utilizing thread-local storage.
* **Graceful API Error Handling:** Auto-retries on Gemini 503 demand-spike errors with exponential backoff.
* **Core Technologies:** Built on **Streamlit**, **Google ADK Framework**, **Gemini API**, and **Pandas**.

---

## 🛡️  Security & Sandboxing

The DataVerse agent prioritizes security by running all LLM-generated Python code through a multi-layered sandbox located in `models/sandbox.py`.

*   **Layer 1 (Blocklists):** Hard-coded rejection of 20+ dangerous modules (os, subprocess, socket) and built-ins (exec, eval, open).
*   **Layer 2 (AST Analysis):** Uses Python's Abstract Syntax Tree (AST) to statically analyze code before it ever runs, catching dunder attribute escapes and hidden `__import__` calls.
*   **Layer 3 (Gated Namespace):** Provides a restricted execution environment where only whitelisted analytics libraries (including `pandas`, `seaborn`, and `prophet`) are accessible.
*   **Layer 4 (Resource Limits):** A dedicated thread-based timeout (30s) prevents infinite loops or resource exhaustion from crashing the app.

Any attempt to bypass these restrictions results in a `🛡️ Code blocked` alert in the chat.

---

##  Project Structure

```sh
└── dataverse/
    ├── .adk/
    ├── .python-version
    ├── Makefile
    ├── data/
    │   ├── Sales Funnel.csv
    │   └── check csv dataviz - Sheet1.csv
    ├── dataverse_agent/
    │   ├── __init__.py
    │   ├── agent.py             ← Main entry point for the Multi-Agent Orchestrator
    │   ├── agents/              ← Specialized sub-agents (Cleaning, Forecast, Visual Analyst)
    │   ├── prompts/             ← Specific instruction prompts for each sub-agent
    │   ├── messages.py          ← Centralized chat messages (intro, no-csv, session-resume)
    │   └── tools.py             ← ADK FunctionTools for visualization and code execution
    ├── models/
    │   ├── __init__.py
    │   ├── prompt_template.py
    │   ├── sandbox.py           ← The 4-layer Python execution sandbox
    │   └── utils.py
    ├── tests/
    │   ├── __init__.py
    │   └── test_sandbox.py      ← Comprehensive security test suite
    ├── pyproject.toml
    ├── streamlit_agent_dashboard.py   ← Main AI-powered agent dashboard
    ├── streamlit_chatbot.py
    ├── streamlit_chatbot_api.py
    └── uv.lock
```

---
##  Getting Started

###  Prerequisites

Before getting started with dataverse, ensure your runtime environment meets the following requirements:

- **Programming Language:** Python (>=3.11)
- **Package Manager:** [uv](https://docs.astral.sh/uv/) (Recommended)
- **API Key:** A valid [Google Gemini API key](https://aistudio.google.com/apikey)


###  Installation

Install dataverse using one of the following methods:

**Build from source:**

1. Clone the dataverse repository:
```sh
❯ git clone https://github.com/idzharulhuda13/dataverse
```

2. Navigate to the project directory:
```sh
❯ cd dataverse
```

3. Install the project dependencies:


**Using `uv`** &nbsp; [![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

```sh
❯ uv sync
```

4. Set up your Streamlit secrets by creating `.streamlit/secrets.toml`:
```toml
GEMINI_API_KEY = "your-gemini-api-key"
GEMINI_MODEL   = "your-preferred-gemini-model"
```


###  Usage

Run the AI-powered agent dashboard using the following command:

**Using `streamlit`** &nbsp; [![Streamlit](https://img.shields.io/badge/-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)


```sh
❯ uv run streamlit run streamlit_agent_dashboard.py
```

Or use the provided **Makefile** for convenience:

| Command        | Description                                      |
|----------------|--------------------------------------------------|
| `make install` | Install all project dependencies via `uv sync`   |
| `make run`     | Run the Streamlit agent dashboard                |
| `make clean`   | Remove cache, build artifacts, and `.venv`       |
| `make tunnel`  | Start an ngrok tunnel (fixed domain)             |
| `make all`     | Run the chatbot API app and start ngrok tunnel   |
| `make stop`    | Stop all running Streamlit and ngrok processes   |

```sh
❯ make run
```
