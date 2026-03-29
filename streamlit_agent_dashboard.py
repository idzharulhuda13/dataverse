import io
import random
import uuid
import time
from datetime import datetime

import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from google.genai.errors import ServerError

from models.utils import load_csv, extract_non_code_text, extract_python_code_blocks, execute_python_code
from dataverse_agent.agent import root_agent
from dataverse_agent.messages import INTRO_MESSAGES, NO_CSV_MESSAGES, SESSION_RESUMED_MESSAGES

st.set_page_config(page_title="DataVerse - Dashboard Generation", layout="wide")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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


def _build_instruction(modified_df):
    """Build the system instruction, optionally appending DataFrame context."""
    instruction = root_agent.instruction
    if modified_df is not None:
        buf = io.StringIO()
        modified_df.info(buf=buf)
        df_info = buf.getvalue()
        df_head = modified_df.head(10).to_string()
        instruction += f"\n\nHere is the DataFrame Info:\n{df_info}\n\nHere is a sample (head):\n{df_head}"
    return instruction


def _create_chat(modified_df=None):
    """Create a fresh Gemini chat with the current system instruction."""
    return st.session_state.client.chats.create(
        model=st.secrets.get("GEMINI_MODEL"),
        config=types.GenerateContentConfig(
            system_instruction=_build_instruction(modified_df)
        ),
    )


# ── SESSION MANAGEMENT HELPERS ───────────────────────────────────────────────

def _new_session_id():
    return str(uuid.uuid4())[:8]


def _session_display_name():
    return f"Session – {datetime.now().strftime('%b %d, %I:%M %p')}"


def _create_session(name=None):
    """Create a brand-new session and return its id."""
    sid = _new_session_id()
    st.session_state.sessions[sid] = {
        "name": name or _session_display_name(),
        "created_at": datetime.now(),
        "messages": [{"role": "assistant", "content": random.choice(INTRO_MESSAGES)}],
        "modified_df": None,
        "dashboard_items": [],
        "chat": _create_chat(),
    }
    return sid


def _save_current_session():
    """Persist the current working state back into the sessions dict."""
    sid = st.session_state.current_session_id
    if sid and sid in st.session_state.sessions:
        st.session_state.sessions[sid].update({
            "messages": st.session_state.messages,
            "modified_df": st.session_state.modified_df,
            "dashboard_items": st.session_state.dashboard_items,
            "chat": st.session_state.chat,
        })


def _load_session(sid):
    """Load a session's state into the working session_state keys."""
    session = st.session_state.sessions[sid]
    st.session_state.current_session_id = sid
    st.session_state.messages = session["messages"]
    st.session_state.modified_df = session["modified_df"]
    st.session_state.dashboard_items = session["dashboard_items"]
    st.session_state.chat = session["chat"]


def _switch_session(sid):
    """Save current session, load the target one, and rerun."""
    _save_current_session()
    _load_session(sid)
    st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. SESSION STATE INITIALISATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Gemini client (shared across all sessions)
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("Missing GEMINI_API_KEY in Streamlit secrets.")
    st.stop()

if "client" not in st.session_state:
    st.session_state.client = genai.Client(api_key=api_key)

# Sessions registry
if "sessions" not in st.session_state:
    st.session_state.sessions = {}

# Bootstrap: create the first session on very first load
if "current_session_id" not in st.session_state:
    first_sid = _create_session()
    st.session_state.current_session_id = first_sid
    _load_session(first_sid)

# Defensive: ensure working keys always exist
for key, default in [("messages", []), ("modified_df", None), ("dashboard_items", [])]:
    if key not in st.session_state:
        st.session_state[key] = default

if "chat" not in st.session_state:
    st.session_state.chat = _create_chat()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. SIDEBAR – SESSION MANAGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with st.sidebar:
    st.markdown("## 🗂️ Sessions")

    # ── New Session Button ────────────────────────────────────────────────
    if st.button("➕  New Session", use_container_width=True, type="primary"):
        _save_current_session()
        new_sid = _create_session()
        _load_session(new_sid)
        st.rerun()

    st.divider()

    # ── Session List ──────────────────────────────────────────────────────
    current_sid = st.session_state.current_session_id
    sorted_sessions = sorted(
        st.session_state.sessions.items(),
        key=lambda x: x[1]["created_at"],
        reverse=True,
    )

    if not sorted_sessions:
        st.caption("No sessions yet.")
    else:
        for sid, session_data in sorted_sessions:
            is_active = sid == current_sid
            label = session_data["name"]
            created = session_data["created_at"].strftime("%b %d, %I:%M %p")
            msg_count = len([m for m in session_data.get("messages", []) if m["role"] == "user"])
            has_data = session_data.get("modified_df") is not None

            # Visual indicator for active session
            if is_active:
                icon = "🟢"
            elif has_data:
                icon = "📊"
            else:
                icon = "💬"

            with st.container(border=True):
                col_info, col_actions = st.columns([5, 1])

                with col_info:
                    # Session switch button
                    if is_active:
                        st.markdown(f"**{icon} {label}**")
                        st.caption(f"🕐 {created}  ·  {msg_count} message{'s' if msg_count != 1 else ''}")
                    else:
                        if st.button(
                            f"{icon} {label}",
                            key=f"switch_{sid}",
                            use_container_width=True,
                        ):
                            _save_current_session()
                            _load_session(sid)
                            # Add a "welcome back" message if switching to a session with history
                            if msg_count > 0:
                                resumed_msg = random.choice(SESSION_RESUMED_MESSAGES)
                                st.session_state.messages.append(
                                    {"role": "assistant", "content": resumed_msg}
                                )
                                _save_current_session()
                            st.rerun()
                        st.caption(f"🕐 {created}  ·  {msg_count} msg{'s' if msg_count != 1 else ''}")

                with col_actions:
                    # Only allow deleting non-active sessions (and only if > 1 session)
                    if not is_active and len(st.session_state.sessions) > 1:
                        if st.button("🗑️", key=f"del_{sid}", help="Delete this session"):
                            del st.session_state.sessions[sid]
                            st.rerun()

    # ── Rename Current Session ────────────────────────────────────────────
    st.divider()
    st.markdown("##### ✏️ Rename Current Session")
    current_name = st.session_state.sessions.get(current_sid, {}).get("name", "")
    new_name = st.text_input(
        "Session name",
        value=current_name,
        key="rename_input",
        label_visibility="collapsed",
    )
    if new_name != current_name and new_name.strip():
        st.session_state.sessions[current_sid]["name"] = new_name.strip()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. MAIN LAYOUT – CHAT + DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.title("DataVerse - Agent Dashboard Generation")

chat_col, dash_col = st.columns([4, 6], gap="large")

with chat_col:
    st.subheader("💬 Chat & Explore")

    # Render previous chat history
    for idx, msg in enumerate(st.session_state.messages):  # type: ignore
        with st.chat_message(msg["role"]):  # type: ignore
            st.markdown(msg["content"])  # type: ignore

            # Show output string from code execution
            if "output" in msg:
                st.markdown(f"```python\n{msg['output']}\n```")  # type: ignore

            # Show previously generated figure
            if "figure" in msg:
                st.pyplot(msg["figure"])  # type: ignore

            # Show generated insights
            if msg.get("insight"):
                st.info(f"💡 **Data Insight**: {msg['insight']}")

            if "figure" in msg:
                # Add Pin button for this figure if it hasn't been pinned yet
                pin_key = f"pin_btn_{idx}"
                if st.button("📌 Pin to Dashboard", key=pin_key):
                    item = {
                        "type": "figure",
                        "figure": msg["figure"],
                        "code": msg.get("code", ""),
                        "insight": msg.get("insight", ""),
                    }
                    st.session_state.dashboard_items.append(item)
                    _save_current_session()
                    st.rerun()

    # ── Chat Input Box ────────────────────────────────────────────────────
    if prompt := st.chat_input("Ask for a visualization (attach a CSV)...", accept_file="multiple"):
        user_text = (
            getattr(prompt, "text", "")
            if hasattr(prompt, "text")
            else (prompt if isinstance(prompt, str) else "")
        )  # type: ignore
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
                df_head = st.session_state.modified_df.head(10).to_string()  # type: ignore
                append_data_context = (
                    f"\n\n[System Context]: The user just uploaded a new dataset. "
                    f"Here is the DataFrame Info:\n{df_info}\n\n"
                    f"And a sample (head):\n{df_head}\nAssume it is loaded as `df`."
                )

        # The actual prompt we send to the LLM
        llm_prompt = user_text + append_data_context

        # Guard: if no dataset is loaded yet, ask the user to upload a CSV first
        if st.session_state.modified_df is None and not uploaded_files:
            st.session_state.messages.append({"role": "user", "content": user_text})  # type: ignore
            st.session_state.messages.append(
                {"role": "assistant", "content": random.choice(NO_CSV_MESSAGES)}
            )  # type: ignore
            _save_current_session()
            st.rerun()

        # Add only the user's text to the visible UI history
        st.session_state.messages.append({"role": "user", "content": user_text})  # type: ignore
        with st.chat_message("user"):
            st.markdown(user_text)

        with st.spinner("Agent is thinking..."):
            response = safe_chat_send(st.session_state.chat, llm_prompt)
            if not response:
                st.session_state.messages.pop()
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
                    insight_prompt = (
                        "Here is the chart you just generated. Please provide a concise, "
                        "data-driven insight (1-2 paragraphs) explicitly stating what this chart "
                        "reveals (e.g., trends, spikes, correlations, or key takeaways). "
                        "Do not explain how you made the chart, just focus on the business or data insights."
                    )
                    insight_response = safe_chat_send(st.session_state.chat, [insight_prompt, img])
                    insight_text = extract_non_code_text(
                        insight_response.text if insight_response else ""
                    )

            # Save into session state BEFORE rendering so that button reruns don't lose the msg
            assistant_msg = {
                "role": "assistant",
                "content": response_without_code,
            }
            if figure is not None:
                assistant_msg["figure"] = figure
                assistant_msg["code"] = code_block  # type: ignore
            if output_str is not None:
                assistant_msg["output"] = output_str
            if insight_text is not None:
                assistant_msg["insight"] = insight_text  # type: ignore

            st.session_state.messages.append(assistant_msg)  # type: ignore
            _save_current_session()  # ← auto-save after every message
            st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. DASHBOARD RENDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with dash_col:
    st.subheader("📊 Generated Dashboard")
    st.markdown("Your pinned visualizations will appear here in real-time.")
    st.divider()

    if not st.session_state.dashboard_items:
        st.info(
            "No items pinned yet. Ask the agent to generate some visualizations "
            "and click '📌 Pin to Dashboard'."
        )
    else:
        db_cols = st.columns(2)
        for i, item in enumerate(st.session_state.dashboard_items):
            col = db_cols[i % 2]
            with col:
                with st.container(border=True):
                    if item["type"] == "figure":
                        st.pyplot(item["figure"], use_container_width=True)
                        if item.get("insight"):
                            st.info(f"💡 {item['insight']}")

                        if st.button("❌ Remove", key=f"remove_btn_{i}"):
                            st.session_state.dashboard_items.pop(i)
                            _save_current_session()
                            st.rerun()
