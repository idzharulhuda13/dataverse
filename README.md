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

**DataVerse** is an AI-powered, conversational data analysis tool. Upload a dataset, ask questions in plain English, and get instant charts, summaries, forecasts, and cleaned data — all inside a Streamlit chat interface powered by **Google Gemini** and the **Google ADK** multi-agent framework.

---

##  Features

| Capability | What it does |
|---|---|
| 💬 **Chat with your data** | Ask questions in plain English — no SQL or code needed. Supports CSV, Excel, Parquet, JSON, and TSV. |
| 📊 **Instant visualizations** | Generates bar, line, scatter, heatmap, forecast charts and more, directly in the chat. |
| 🧹 **Auto data cleaning** | On upload, the agent automatically detects and fixes missing values, duplicates, and type issues. |
| 🔮 **Time-series forecasting** | Predict future trends using Prophet with a simple natural language request. |
| 📌 **Pinnable dashboard** | Pin any chart to a live 2-column dashboard alongside the chat. |
| ⚡ **Slash commands** | Power shortcuts like `/summary`, `/export`, `/undo`, and `/cost` for instant, zero-latency actions. |
| 🗂️ **Multiple sessions** | Create, switch, and manage independent chat sessions — each with its own data and history. |
| 🔒 **Secure sandbox** | All AI-generated code runs inside a 4-layer sandbox. Dangerous operations are blocked before they run. |
| 🔍 **Admin observability** | Admins can enable a real-time agent activity trace and monitor token usage, cost, and turn budget. |

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
    │   ├── agents/              ← Specialized sub-agents (Cleaning, Forecast, Visual Analyst, Enricher)
    │   ├── prompts/             ← Specific instruction prompts for each agent
    │   ├── messages.py          ← Centralized chat messages (intro, no-csv, session-resume)
    │   └── tools.py             ← ADK FunctionTools for visualization and code execution
    ├── models/
    │   ├── __init__.py
    │   ├── prompt_template.py
    │   ├── sandbox.py           ← The 4-layer Python execution sandbox
    │   └── utils.py
    ├── tests/
    │   ├── __init__.py
    │   ├── stress_test.py       ← End-to-end agent pipeline stress tester
    │   ├── test_sandbox.py      ← Comprehensive security test suite
    │   ├── test_tools.py        ← ADK tool unit tests
    │   ├── test_utils.py        ← DataFrame and string utility unit tests
    │   ├── test_load_dataframe.py ← Multi-format data loading tests
    │   └── test_dashboard.py    ← UI integration tests
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
ADMIN_USERNAME = "your-admin-username"
ADMIN_PASSWORD = "your-admin-password"
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
