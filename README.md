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
- [ Project Structure](#project-structure)
- [ Getting Started](#getting-started)
  - [ Prerequisites](#prerequisites)
  - [ Installation](#installation)
  - [ Usage](#usage)

---

##  Overview

**Dataverse - Data Explorer** (Nano-Dataverse) is an interactive, **AI-powered data analysis and visualization tool** built with **Streamlit** and the **Google Gemini API**.

This application allows users to upload a **CSV file** and then communicate with a **context-aware chat assistant** to perform complex data exploration tasks. The AI (powered by Gemini) intelligently suggests analyses, writes and executes **Python code** (using libraries like **Pandas** and **Seaborn**) on the uploaded DataFrame, and visualizes the results directly within the app. It acts as a powerful, conversational data analyst at your fingertips.

---

##  Features

### Conversational Data Analysis
* **AI Analyst Chat Interface:** Engage with a powerful chat assistant to ask natural language questions about your data.
* **Context-Aware Responses:** The AI is initialized with your DataFrame's structure to provide relevant and precise suggestions from the start.
* **Randomized Welcome Messages:** Every new session greets you with a unique, randomized welcome message for a fresh experience.
* **CSV Upload Guard:** The agent enforces uploading a CSV file before any analysis can begin, ensuring data is always present before queries.

### Session Management
* **Persistent Chat Sessions:** Create and switch between multiple independent chat sessions — each with its own conversation history, uploaded dataset, and pinned dashboard items.
* **Session Sidebar:** The sidebar lists all sessions, showing creation time, message count, and data status at a glance.
* **Session Resume Messages:** When you switch back to a previous session, the agent greets you with a contextual "welcome back" message.
* **Rename Sessions:** Customize the name of any active session directly from the sidebar.
* **Delete Sessions:** Remove any non-active session with a single click (keeping at least one session always active).
* **Auto-Save:** Session state is automatically saved after every message exchange.

### Code Execution & Visualization
* **Intelligent Code Generation:** The AI assistant generates **Python code snippets** (primarily for data manipulation with **Pandas** and visualization with **Seaborn** or **Matplotlib**) in response to user prompts.
* **Secure In-App Execution:** The generated code is automatically executed against the active DataFrame in the Streamlit environment.
* **Live Visualization:** Automatically displays generated **Seaborn/Matplotlib plots** directly in the chat thread.
* **Chart Insights (Second Pass):** After each chart is generated, the agent performs a second AI pass to provide concise, data-driven business insights extracted from the visualization.
* **Code and Output Display:** Shows both the **plain-text response** from the AI *and* the actual **execution output** (or errors) in code blocks for full transparency.

### Dashboard Pinning
* **Pin to Dashboard:** Any generated visualization can be pinned to a live dashboard panel displayed alongside the chat.
* **2-Column Dashboard Layout:** Pinned charts are arranged in a responsive 2-column grid with insights attached.
* **Remove from Dashboard:** Easily remove pinned items directly from the dashboard view.

### Data Management & Tech Stack
* **CSV Upload via Chat Input:** Upload your dataset directly within the chat input box for a seamless workflow.
* **Data Isolation:** Maintains a separate copy of the DataFrame for safe code execution.
* **Graceful API Error Handling:** Auto-retries on Gemini 503 demand-spike errors with exponential backoff.
* **Core Technologies:** Built on **Streamlit**, **Google Gemini API**, and **Pandas**.

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
    │   ├── agent.py
    │   └── messages.py          ← Centralized chat messages (intro, no-csv, session-resume)
    ├── models/
    │   ├── prompt_template.py
    │   └── utils.py
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
