import io
import random
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types

from models.utils import load_csv, extract_non_code_text, extract_python_code_blocks, execute_python_code
from dataverse_agent.agent import root_agent
from dataverse_agent.messages import INTRO_MESSAGES, NO_CSV_MESSAGES

st.set_page_config(page_title="DataVerse - Dashboard Generation", layout="wide")

st.title("DataVerse - Agent Dashboard Generation")

import time
from google.genai.errors import ServerError

def safe_chat_send(chat, payload, max_retries=3):
    """Small wrapper to handle 503 demand spikes gracefully."""
    for attempt in range(max_retries):
        try:
            return chat.send_message(payload)
        except ServerError as e:
            if "503" in str(e) and attempt < max_retries - 1:
                st.warning(f"⚠️ Model is busy (503). Retrying in {2**attempt}s...")
                time.sleep(2**attempt)
            else:
                st.error(f"❌ Gemini API Error: {str(e)}")
                return None
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            return None
    return None

# ── 1. SESSION STATE INIT ────────────────────────────────────────────────────────
if "dashboard_items" not in st.session_state:
    st.session_state.dashboard_items = []

if "modified_df" not in st.session_state:
    st.session_state.modified_df = None

# Initialize Chat
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("Missing GEMINI_API_KEY in Streamlit secrets.")
    st.stop()

if "client" not in st.session_state:
    st.session_state.client = genai.Client(api_key=api_key)

# ── 2. LAYOUT & FILE UPLOAD ─────────────────────────────────────────────────────
chat_col, dash_col = st.columns([4, 6], gap="large")

with chat_col:
    st.subheader("💬 Chat & Explore")
    
    df_info = ""
    df_head = ""
    if st.session_state.modified_df is not None:
        buf = io.StringIO()
        st.session_state.modified_df.info(buf=buf)
        df_info = buf.getvalue()
        df_head = st.session_state.modified_df.head(10).to_string() # type: ignore

    # System prompt setup utilizing our root_agent properties
    instruction_payload = root_agent.instruction
    if df_info:
        instruction_payload += f"\n\nHere is the DataFrame Info:\n{df_info}\n\nHere is a sample (head):\n{df_head}"

    if "chat" not in st.session_state:
        st.session_state.chat = st.session_state.client.chats.create(
            model=st.secrets.get("GEMINI_MODEL"),
            config=types.GenerateContentConfig(system_instruction=instruction_payload)
        )

    if "messages" not in st.session_state: # type: ignore
        initial_msg = random.choice(INTRO_MESSAGES)
        st.session_state.messages = [{"role": "assistant", "content": initial_msg}]

    # Render previous chat history
    for idx, msg in enumerate(st.session_state.messages): # type: ignore
        with st.chat_message(msg["role"]): # type: ignore
            st.markdown(msg["content"]) # type: ignore
            
            # Show output string from code execution
            if "output" in msg:
                st.markdown(f"```python\n{msg['output']}\n```") # type: ignore
                
            # Show previously generated figure
            if "figure" in msg:
                st.pyplot(msg["figure"]) # type: ignore

            # Show generated insights
            if msg.get("insight"):
                st.info(f"💡 **Data Insight**: {msg['insight']}")
                
            if "figure" in msg:
                # Add Pin button for this figure if it hasn't been pinned yet
                pin_key = f"pin_btn_{idx}"
                if st.button("📌 Pin to Dashboard", key=pin_key):
                    # Save to dashboard_items
                    item = {
                        "type": "figure",
                        "figure": msg["figure"],
                        "code": msg.get("code", ""),
                        "insight": msg.get("insight", "")
                    }
                    st.session_state.dashboard_items.append(item)
                    st.rerun() # Refresh to show in dashboard column

    # Chat Input Box
    if prompt := st.chat_input("Ask for a visualization (attach a CSV)...", accept_file="multiple"):
        user_text = getattr(prompt, "text", "") if hasattr(prompt, "text") else (prompt if isinstance(prompt, str) else "") # type: ignore
        uploaded_files = getattr(prompt, "files", []) if hasattr(prompt, "files") else []
        
        # Handle new file uploads
        append_data_context = ""
        if uploaded_files:
            uploaded_file = uploaded_files[0]
            df, error = load_csv(uploaded_file)
            if error:
                st.error(f"Error loading CSV: {error}")
            else:
                st.session_state.modified_df = df.copy()
                buf = io.StringIO()
                st.session_state.modified_df.info(buf=buf)
                df_info = buf.getvalue()
                df_head = st.session_state.modified_df.head(10).to_string() # type: ignore
                append_data_context = f"\n\n[System Context]: The user just uploaded a new dataset. Here is the DataFrame Info:\n{df_info}\n\nAnd a sample (head):\n{df_head}\nAssume it is loaded as `df`."

        # The actual prompt we send to the LLM
        llm_prompt = user_text + append_data_context

        # Guard: if no dataset is loaded yet, ask the user to upload a CSV first
        if st.session_state.modified_df is None and not uploaded_files:
            st.session_state.messages.append({"role": "user", "content": user_text}) # type: ignore
            st.session_state.messages.append({"role": "assistant", "content": random.choice(NO_CSV_MESSAGES)}) # type: ignore
            st.rerun()

        # Add only the user's text to the visible UI history
        st.session_state.messages.append({"role": "user", "content": user_text}) # type: ignore
        with st.chat_message("user"):
            st.markdown(user_text)

        with st.spinner("Agent is thinking..."):
            response = safe_chat_send(st.session_state.chat, llm_prompt)
            if not response:
                st.session_state.messages.pop() # remove the user message if no response
                st.stop()
            
            print("Usage summary:", getattr(response, "usage_metadata", "N/A"))

            response_without_code = extract_non_code_text(response.text or "")
            code_blocks = extract_python_code_blocks(response.text or "")
            code_block = code_blocks[0] if code_blocks else None

            output_str = None
            figure = None
            insight_text = None

            if code_block:
                if st.session_state.modified_df is not None:
                    output_str, final_df, figure = execute_python_code(
                        code_block, st.session_state.modified_df
                    )
                else:
                    output_str, final_df, figure = "No DataFrame loaded.", None, None

            # SECOND PASS: If figure generated, ask agent to read it and provide insights
            if figure:
                from PIL import Image
                buf = io.BytesIO()
                figure.savefig(buf, format="png")
                buf.seek(0)
                img = Image.open(buf)
                
                with st.spinner("Analyzing chart insights..."):
                    insight_prompt = "Here is the chart you just generated. Please provide a concise, data-driven insight (1-2 paragraphs) explicitly stating what this chart reveals (e.g., trends, spikes, correlations, or key takeaways). Do not explain how you made the chart, just focus on the business or data insights."
                    insight_response = safe_chat_send(st.session_state.chat, [insight_prompt, img])
                    insight_text = extract_non_code_text(insight_response.text if insight_response else "")

            # Save into session state BEFORE rendering so that button reruns don't lose the msg
            assistant_msg = {
                "role": "assistant",
                "content": response_without_code,
            }
            if figure is not None:
                assistant_msg["figure"] = figure
                assistant_msg["code"] = code_block # type: ignore
            if output_str is not None:
                assistant_msg["output"] = output_str
            if insight_text is not None:
                assistant_msg["insight"] = insight_text # type: ignore

            st.session_state.messages.append(assistant_msg) # type: ignore
            st.rerun()


# ── 3. DASHBOARD RENDER ─────────────────────────────────────────────────────────
with dash_col:
    st.subheader("📊 Generated Dashboard")
    st.markdown("Your pinned visualizations will appear here in real-time.")
    st.divider()

    if not st.session_state.dashboard_items:
        st.info("No items pinned yet. Ask the agent to generate some visualizations and click '📌 Pin to Dashboard'.")
    else:
        # Layout in a grid (e.g., 2 items per row)
        db_cols = st.columns(2)
        for i, item in enumerate(st.session_state.dashboard_items):
            col = db_cols[i % 2]
            with col:
                with st.container(border=True): # visual boundary
                    if item["type"] == "figure":
                        st.pyplot(item["figure"], use_container_width=True)
                        if item.get("insight"):
                            st.info(f"💡 {item['insight']}")
                            
                        # Options to remove or see code
                        # with st.expander("View Code"):
                        #     st.code(item["code"], language="python")
                        if st.button("❌ Remove", key=f"remove_btn_{i}"):
                            st.session_state.dashboard_items.pop(i)
                            st.rerun()
