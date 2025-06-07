# app.py
import streamlit as st
import pandas as pd
from gpt4all import GPT4All #type: ignore
from models.prompt_template import prompt_analyst_template
from models.utils import execute_python_code
import io
import re

# ── 1. PAGE CONFIG & TITLE ─────────────────────────────────────────────────────
st.set_page_config(page_title="Local‐GPT4All Chat", layout="centered")
st.title("Chat with a Local GPT4All Model (using chat_session)")

# ── 2. CACHE DATAFRAME LOAD & INTROSPECTION ───────────────────────────────────
@st.cache_data
def load_df(path: str) -> pd.DataFrame:
    return pd.read_csv(path) # type: ignore

@st.cache_data
def get_df_info(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.info(buf=buf)
    return buf.getvalue()

@st.cache_data
def get_df_head(df: pd.DataFrame, n: int = 10) -> str:
    return df.head(n).to_string() #type: ignore

df        = load_df('data/Sales Funnel.csv')
df_info   = get_df_info(df)
df_head   = get_df_head(df)

# Keep track of the original/modified DataFrame
if "modified_df" not in st.session_state:
    st.session_state.modified_df = df.copy()

# ── 3. BUILD SYSTEM PROMPT (ONCE) ───────────────────────────────────────────────
if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = prompt_analyst_template.format(
        df_info=df_info,
        df_head=df_head
    )

# ── 4. CACHE & LOAD GPT4All MODEL ─────────────────────────────────────────────
GPT4All_MODEL_NAME = "oh-dcft-v3.1-claude-3-5-sonnet-20241022.Q8_0.gguf"
GPT4All_MODEL_PATH = "models/"
@st.cache_resource
def load_model():
    return GPT4All(
        GPT4All_MODEL_NAME,
        model_path=GPT4All_MODEL_PATH,
        allow_download=False
    )

if "model" not in st.session_state:
    st.session_state.model = load_model()

# ── 5. INITIALIZE chat_session (ONCE) ──────────────────────────────────────────
def stop_on_token_callback(token_id: int, token_string: str) -> bool:
    in_code_block = False
    if '```python' in token_string:
        in_code_block = not in_code_block
        return in_code_block
    return True
    
if "session" not in st.session_state:
    cm = st.session_state.model.chat_session(system_prompt=st.session_state.system_prompt)
    st.session_state.session = cm.__enter__()
    st.session_state.session_cm = cm

# ── 6. RENDER & HANDLE CHAT ────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": st.session_state.session.generate("initiate conversation")
        }
    ]

for msg in st.session_state.messages: # type: ignore
    with st.chat_message(msg["role"]): # type: ignore
        st.markdown(msg["content"]) # type: ignore
        if "figure" in msg:
            st.pyplot(msg["figure"])

if prompt := st.chat_input("Type your question..."):
    st.session_state.messages.append({"role": "user", "content": prompt}) # type: ignore
    with st.chat_message("user"):
        st.markdown(prompt)

    reply = st.session_state.session.generate(prompt, callback=stop_on_token_callback) # type: ignore
    # print(f"\n\nGenerated reply: {reply}")  # Debugging output
                # Extract the response excluding code blocks
    # Extract all code blocks and remove them from the reply, preserving non-code text
    code_pattern = r'```(?:python)?\n(.*?)\n```'
    response_without_code = re.sub(code_pattern, '', reply, flags=re.DOTALL | re.IGNORECASE).strip()

    figure = None  # Ensure figure is always defined

    with st.chat_message("assistant"):
        st.markdown(response_without_code)

        # Extract and execute Python code if present
        code_blocks = [
            match.group(1)
            for match in re.finditer(
            r'```(?:python)?\s*\n(.*?)\n```', reply, re.DOTALL | re.IGNORECASE
            )
        ]
        if code_blocks:
            for code in code_blocks:
                # Execute Python code
                output_str, final_df, fig = execute_python_code(
                    code, st.session_state.modified_df
                )

                # If a figure was generated, attach it to the assistant's message
                if fig:
                    st.pyplot(fig)
                    figure = fig  # Assign to outer variable

    # Append assistant message, including figure if present
    assistant_msg = {"role": "assistant", "content": response_without_code}
    if figure is not None:
        assistant_msg["figure"] = figure
    st.session_state.messages.append(assistant_msg)  # type: ignore