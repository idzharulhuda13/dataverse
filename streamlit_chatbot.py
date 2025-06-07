# app.py
import streamlit as st
import pandas as pd
from gpt4all import GPT4All #type: ignore
from models.prompt_template import prompt_analyst_template
import io

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

if prompt := st.chat_input("Type your question..."):
    st.session_state.messages.append({"role": "user", "content": prompt}) # type: ignore
    with st.chat_message("user"):
        st.markdown(prompt)

    reply = st.session_state.session.generate(prompt)
    st.session_state.messages.append({"role": "assistant", "content": reply}) # type: ignore
    with st.chat_message("assistant"):
        st.markdown(reply)