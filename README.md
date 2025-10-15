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
* **Persistent Chat History:** Maintains the full history of the conversation within the Streamlit session.

### Code Execution & Visualization
* **Intelligent Code Generation:** The AI assistant generates **Python code snippets** (primarily for data manipulation with **Pandas** and visualization with **Seaborn** or **Matplotlib**) in response to user prompts.
* **Secure In-App Execution:** The generated code is automatically executed against the active DataFrame in the Streamlit environment.
* **Live Visualization:** Automatically displays generated **Seaborn/Matplotlib plots** directly in the chat thread.
* **Code and Output Display:** Shows both the **plain-text response** from the AI *and* the actual **execution output** (or errors) in code blocks for full transparency.

### Data Management & Tech Stack
* **Simple CSV Upload:** Easily upload your data using Streamlit's file uploader.
* **Efficient Caching:** Utilizes Streamlit's caching to efficiently manage and load the DataFrame.
* **Data Isolation:** Maintains a separate copy of the DataFrame for safe code execution.
* **Core Technologies:** Built on **Streamlit**, **Google Gemini API**, and **Pandas**.

---

##  Project Structure

```sh
└── dataverse/
    ├── Makefile
    ├── data
    │   ├── Sales Funnel.csv
    │   └── check csv dataviz - Sheet1.csv
    ├── deprecated
    │   ├── app-v01.py
    │   ├── app-v02.py
    │   ├── app-v03.py
    │   └── back to basic.ipynb
    ├── models
    │   ├── prompt_template.py
    │   └── utils.py
    ├── requirements.txt
    ├── streamlit_chatbot.py
    └── streamlit_chatbot_api.py
```

---
##  Getting Started

###  Prerequisites

Before getting started with dataverse, ensure your runtime environment meets the following requirements:

- **Programming Language:** Python
- **Package Manager:** Pip


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


**Using `pip`** &nbsp; [<img align="center" src="https://img.shields.io/badge/Pip-3776AB.svg?style={badge_style}&logo=pypi&logoColor=white" />](https://pypi.org/project/pip/)

```sh
❯ pip install -r requirements.txt
```




###  Usage
Run dataverse using the following command:
**Using `streamlit`** &nbsp; [![Streamlit](https://img.shields.io/badge/-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)


```sh
❯ streamlit run streamlit_chatbot_api.py
```
