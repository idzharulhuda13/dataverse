import io
import os
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from models.prompt_template import prompt_seaborn_analyst
from models.utils import load_csv, extract_non_code_text, extract_python_code_blocks, execute_python_code
import dotenv

dotenv.load_dotenv()

st.set_page_config(page_title="Nano-Dataverse", layout="centered")
st.title("Dataverse - Data Explorer")

uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

@st.cache_data
def get_df_info(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.info(buf=buf)
    return buf.getvalue()

@st.cache_data
def get_df_head(df: pd.DataFrame, n: int = 10) -> str:
    return df.head(n).to_string() #type: ignore

df = None
if uploaded_file:
    st.cache_data.clear()
    st.cache_resource.clear()
    df, error = load_csv(uploaded_file)
    if df is not None:
        df_info   = get_df_info(df)
        df_head   = get_df_head(df)
    else:
        df_info = ""
        df_head = ""

    # Keep track of the original/modified DataFrame
    if "modified_df" not in st.session_state:
        if df is not None:
            st.session_state.modified_df = df.copy()
        else:
            st.session_state.modified_df = None
    
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY environment variable.")
    if not model:
        raise ValueError("Missing GEMINI_MODEL environment variable.")

    if "client" not in st.session_state:
        st.session_state.client = genai.Client(api_key=api_key)
    if "chat" not in st.session_state:
        st.session_state.chat = st.session_state.client.chats.create(
            model=model,
            config=types.GenerateContentConfig(system_instruction=prompt_seaborn_analyst.format(
                df_info=df_info,
                df_head=df_head
            ))
        )
    if "messages" not in st.session_state: # type: ignore
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": st.session_state.chat.send_message("with the data provided, what is your suggestion?").text
            }
        ]

    for msg in st.session_state.messages: # type: ignore
        with st.chat_message(msg["role"]): # type: ignore
            st.markdown(msg["content"]) # type: ignore
            if "figure" in msg:
                st.pyplot(msg["figure"]) # type: ignore
            elif "output" in msg:
                st.markdown(msg['output']) # type: ignore

    if prompt := st.chat_input("Type your question..."):
        st.session_state.messages.append({"role": "user", "content": prompt}) # type: ignore

        with st.chat_message("user"):
            st.markdown(prompt)

        response = st.session_state.chat.send_message(prompt)
        print(response.usage_metadata)

        response_without_code = extract_non_code_text(response.text or "")
        code_blocks = extract_python_code_blocks(response.text or "")
        code_block = code_blocks[0] if code_blocks else None

        output_str = None
        figure = None

        if code_block:
            if st.session_state.modified_df is not None:
                output_str, final_df, figure = execute_python_code(
                    code_block, st.session_state.modified_df
                )
                print(f"Output: {output_str}")
            else:
                output_str, final_df, figure = "No DataFrame loaded.", None, None

        with st.chat_message("assistant"):
            st.markdown(response_without_code)
            if figure:
                st.pyplot(figure)
            
        assistant_msg = {"role": "assistant", "content": response_without_code}
        if figure is not None:
            assistant_msg["figure"] = figure  # type: ignore

        st.session_state.messages.append(assistant_msg) # type: ignore