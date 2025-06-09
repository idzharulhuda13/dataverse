# app.py
import streamlit as st
import pandas as pd
from gpt4all import GPT4All #type: ignore
from models.prompt_template import prompt_analyst_template
from models.utils import execute_python_code, load_csv, make_stop_on_token_callback_exit_code_block, extract_non_code_text, extract_python_code_blocks
import io

# ── 1. PAGE CONFIG & TITLE ─────────────────────────────────────────────────────
st.set_page_config(page_title="Nano-Dataverse", layout="centered")
st.title("Dataverse - Data Explorer")

# ── 2. CACHE DATAFRAME LOAD & INTROSPECTION ───────────────────────────────────
# File uploader
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
    for key in list(st.session_state.keys()):
        del st.session_state[key]
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

    if "session" not in st.session_state:
        cm = st.session_state.model.chat_session(system_prompt=st.session_state.system_prompt)
        st.session_state.session = cm.__enter__()
        st.session_state.session_cm = cm

    # ── 6. RENDER & HANDLE CHAT ────────────────────────────────────────────────────
    with st.spinner("Loading data and model..."):
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
                st.pyplot(msg["figure"]) # type: ignore
            elif "output" in msg:
                st.markdown(f"```\n{output_str}\n```") # type: ignore

    if prompt := st.chat_input("Type your question..."):
        st.session_state.messages.append({"role": "user", "content": prompt}) # type: ignore
        with st.chat_message("user"):
            st.markdown(prompt)

        MAX_RETRIES = 2
        retry_count = 0
        output_str = None  # Initialize output_str to ensure it's defined
        response_without_code = ""
        figure = None  # Initialize figure to ensure it's defined

        while retry_count < MAX_RETRIES:
            generation_input = prompt if output_str is None else (
                f"The previous code resulted in an error: {output_str}\n"
                f"Please try again and fix the issue."
            )

            reply = st.session_state.session.generate(
                generation_input,
                callback=make_stop_on_token_callback_exit_code_block()
            )  # type: ignore

            # Use utility function to extract non-code text
            response_without_code = extract_non_code_text(reply)

            # Extract and execute Python code if present
            code_blocks = extract_python_code_blocks(reply)
            code_block = code_blocks[0] if code_blocks else None

            output_str = None  # Ensure output_str is always defined

            if code_block:
                print(f"\n\nGenerated codeblock: {code_block}")  # Debugging output
                if st.session_state.modified_df is not None:
                    output_str, final_df, figure = execute_python_code(
                        code_block, st.session_state.modified_df
                    )
                    print(f"Output: {output_str}")
                else:
                    output_str, final_df, figure = "No DataFrame loaded.", None, None

            if output_str and "error executing code" in output_str.lower():
                retry_count += 1
                print(f"Retry {retry_count} due to error...")
            else:
                break  # Exit loop if there's no error


        with st.chat_message("assistant"):
            st.markdown(response_without_code)

            if figure:
                st.pyplot(figure)
            elif output_str:
                st.markdown(f"```\n{output_str}\n```")

        # Append assistant message, including figure if present
        assistant_msg = {"role": "assistant", "content": response_without_code}
        if figure is not None:
            assistant_msg["figure"] = figure  # type: ignore
        elif output_str and output_str.lower() != "no dataframe loaded." and "error" not in output_str.lower():
            assistant_msg["output"] = output_str  # Save output if not error
        st.session_state.messages.append(assistant_msg)  # type: ignore