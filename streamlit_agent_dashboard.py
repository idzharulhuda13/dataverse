import io
import os
import random
import uuid
import time
import asyncio
from datetime import datetime

import streamlit as st
import pandas as pd
from google import genai
from google.genai import types

from models.utils import load_dataframe, get_excel_sheet_names, extract_non_code_text, SUPPORTED_EXTENSIONS
from dataverse_agent.agent import root_agent
from dataverse_agent.agents.enricher import enrich_query
from dataverse_agent.tools import set_session_context, get_session_figures, get_cleaned_df
from dataverse_agent.usage import SessionUsage
from dataverse_agent.messages import (
    SESSION_RESUMED_MESSAGES,
    UPLOAD_LANDING_MESSAGES,
    ANALYZING_DATA_MESSAGES,
)
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

st.set_page_config(page_title="DataVerse - Dashboard Generation", layout="wide")


# HELPER FUNCTIONS INLINED


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
        "messages": [],
        "modified_df": None,
        "dashboard_items": [],
        "usage": SessionUsage(sid),
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
            "usage": st.session_state.usage,
        })


def _load_session(sid):
    """Load a session's state into the working session_state keys."""
    session = st.session_state.sessions[sid]
    st.session_state.current_session_id = sid
    st.session_state.messages = session["messages"]
    st.session_state.modified_df = session["modified_df"]
    st.session_state.dashboard_items = session["dashboard_items"]
    st.session_state.usage = session.get("usage", SessionUsage(sid))


def _switch_session(sid):
    """Save current session, load the target one, and rerun."""
    _save_current_session()
    _load_session(sid)
    st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. SESSION STATE INITIALISATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Gemini configuration via os environ for ADK
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("Missing GEMINI_API_KEY in Streamlit secrets.")
    st.stop()
os.environ["GEMINI_API_KEY"] = api_key

if "runner" not in st.session_state:
    st.session_state.session_service = InMemorySessionService()
    st.session_state.runner = Runner(
        app_name="dataverse",
        agent=root_agent,
        session_service=st.session_state.session_service,
        auto_create_session=True
    )

# Sessions registry
if "sessions" not in st.session_state:
    st.session_state.sessions = {}

# Bootstrap: create the first session on very first load
if "current_session_id" not in st.session_state:
    first_sid = _create_session()
    st.session_state.current_session_id = first_sid
    _load_session(first_sid)

for key, default in [("messages", []), ("modified_df", None), ("dashboard_items", [])]:
    if key not in st.session_state:
        st.session_state[key] = default


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
                        # Direct renaming toggle
                        if "renaming_session_id" not in st.session_state:
                            st.session_state.renaming_session_id = None
                        
                        # Minimalist CSS to make the edit icon look like a 'ghost' button
                        st.markdown("""
                            <style>
                                div[data-testid="column"] button {
                                    border: none !important;
                                    background-color: transparent !important;
                                    padding: 0 !important;
                                    color: #64748B !important;
                                }
                                div[data-testid="column"] button:hover {
                                    color: #2D3A4A !important;
                                    background-color: #F1F5F9 !important;
                                }
                            </style>
                        """, unsafe_allow_html=True)

                        is_renaming = st.session_state.renaming_session_id == sid
                        
                        # Use a tighter column layout (0.85/0.15)
                        name_col, edit_col = st.columns([12, 2])
                        with name_col:
                            if is_renaming:
                                new_name = st.text_input(
                                    f"Rename {sid}",
                                    value=label,
                                    key=f"rename_{sid}",
                                    label_visibility="collapsed",
                                )
                                if new_name != label and new_name.strip():
                                    st.session_state.sessions[sid]["name"] = new_name.strip()
                                    st.session_state.renaming_session_id = None
                                    st.rerun()
                            else:
                                st.markdown(f"**{icon} {label}**")
                        
                        with edit_col:
                            # Use a cleaner icon and ghost-button style
                            if st.button("✎" if not is_renaming else "✔", key=f"edit_btn_{sid}", help="Rename Session"):
                                if is_renaming:
                                    st.session_state.renaming_session_id = None
                                else:
                                    st.session_state.renaming_session_id = sid
                                st.rerun()

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

    # ── Token Usage & Budget ──────────────────────────────────────────────
    st.markdown("## 💰 Usage & Budget")
    
    usage = st.session_state.get('usage', SessionUsage(current_sid))
    
    # Configuration: Max Budget
    if "max_budget_tokens" not in st.session_state:
        st.session_state.max_budget_tokens = 500_000
        
    new_budget = st.number_input(
        "Max Budget (Tokens)", 
        value=st.session_state.max_budget_tokens,
        step=50_000,
        help="Warning will appear when tokens exceed this limit."
    )
    st.session_state.max_budget_tokens = new_budget

    # Metrics
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric("📡 API Calls", f"{usage.api_calls}")
        st.metric("📊 Turns", f"{usage.turns}")
    with m_col2:
        st.metric("🪙 Tokens", f"{usage.total_tokens / 1000:.1f}K")
        st.metric("💵 Est. Cost", f"${usage.estimated_cost_usd:.4f}")

    # Progress/Visual Warning
    progress = min(1.0, usage.total_tokens / st.session_state.max_budget_tokens)
    st.progress(progress, text=f"{progress*100:.1f}% of budget")
    
    if usage.total_tokens >= st.session_state.max_budget_tokens:
        st.error("⚠️ Budget limit reached! Freezing further requests.")
    elif usage.total_tokens >= st.session_state.max_budget_tokens * 0.8:
        st.warning("🪫 Approaching budget limit soon.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. HELPER — Run agent and handle response (reused by upload + chat)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _run_agent_and_save(llm_prompt: str, user_display_text: str | None = None):
    """Send a prompt to the agent, capture response + figures, and save to session.

    Args:
        llm_prompt: The full prompt to send to the LLM (may include system context).
        user_display_text: If provided, added as a visible 'user' message in chat history.
    """
    if user_display_text is not None:
        st.session_state.messages.append({"role": "user", "content": user_display_text})

    runner = st.session_state.runner
    current_session = st.session_state.current_session_id

    # Budget Check
    if st.session_state.usage.total_tokens >= st.session_state.max_budget_tokens:
        st.error("❌ Request blocked: Session budget exceeded. Please increase budget in the sidebar to continue.")
        return

    # Setup context for tools
    set_session_context(st.session_state.modified_df)

    async def generate_response():
        final_text = ""
        async for event in runner.run_async(
            user_id="default",
            session_id=current_session,
            new_message=types.Content(parts=[types.Part.from_text(text=llm_prompt)])
        ):
            # Capture usage metadata from ADK Runner events
            if hasattr(event, 'usage_metadata') and event.usage_metadata:
                st.session_state.usage.record_api_call({
                    'prompt_token_count': event.usage_metadata.prompt_token_count,
                    'candidates_token_count': event.usage_metadata.candidates_token_count,
                    'total_token_count': event.usage_metadata.total_token_count,
                })
            
            if event.content and event.content.parts:
                for p in event.content.parts:
                    if p.text:
                        final_text += p.text
        return final_text

    response_text = asyncio.run(generate_response())
    response_without_code = extract_non_code_text(response_text)

    # Retrieve generated figures and original data summary from the session context
    figures = get_session_figures()
    figure = figures[-1] if figures else None
    
    # Grounding context (actual data metrics) for the Vision agent
    from dataverse_agent.tools import get_session_data_summary
    data_grounding_summary = get_session_data_summary()

    # Check if the cleaning agent produced a transformed DataFrame
    cleaned_df = get_cleaned_df()
    if cleaned_df is not None:
        # Sanity guard: only persist if it looks like a full-dataset transformation.
        # A filtered subset (e.g. top-5 rows × 2 cols from Visual Analyst) will have
        # fewer columns than the original — we should NEVER overwrite with that.
        original_df = st.session_state.get("original_df")
        is_safe = (
            original_df is None  # no baseline yet (e.g. first clean on fresh upload)
            or set(original_df.columns).issubset(set(cleaned_df.columns))  # superset of original cols
            or len(cleaned_df.columns) >= len(st.session_state.modified_df.columns)  # at least as wide
        )
        if is_safe:
            st.session_state.modified_df = cleaned_df
            set_session_context(cleaned_df)
        else:
            # Visual Analyst produced a temporary filtered subset — silently discard it.
            pass

    insight_text = None

    # SECOND PASS: If figure generated, ask agent to read it and provide insights
    if figure:
        img_buf = io.BytesIO()
        figure.savefig(img_buf, format="png")
        img_bytes = img_buf.getvalue()

        with st.spinner("Analyzing chart insights..."):
            insight_prompt = (
                "You are looking at a chart generated from the following dataset summary:\n\n"
                f"### [Reference Data Grounding]\n{data_grounding_summary}\n\n"
                "---\n\n"
                "Provide a focused data insight using this strict two-part framework:\n\n"
                "**📊 Observation (What do I see?):** What specific, factual patterns, trends, outliers, or distributions exist in the chart? Be precise — use the **Reference Data Grounding** above to cite exact numbers, percentages, or rankings where possible.\n\n"
                "**💡 Interpretation (Why does it matter?):** What is the core business or practical implication of this pattern? "
                "Consider: Is there a concentration risk? A growth opportunity? An anomaly that needs investigation?\n\n"
                "Keep it concise (2-4 sentences total). Be highly specific and avoid generic statements.\n\n"
                "CRITICAL: Do NOT suggest any recommendations, follow-up analyses, or next steps here. Focus purely on interpreting the visual evidence in front of you."
            )
            async def generate_insight():
                text = ""
                async for event in runner.run_async(
                    user_id="default",
                    session_id=current_session,
                    new_message=types.Content(parts=[
                        types.Part.from_text(text=insight_prompt),
                        types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                    ])
                ):
                    # Capture usage metadata for vision second-pass
                    if hasattr(event, 'usage_metadata') and event.usage_metadata:
                        st.session_state.usage.record_api_call({
                            'prompt_token_count': event.usage_metadata.prompt_token_count,
                            'candidates_token_count': event.usage_metadata.candidates_token_count,
                            'total_token_count': event.usage_metadata.total_token_count,
                        })
                    
                    if event.content and event.content.parts:
                        for p in event.content.parts:
                            if p.text:
                                text += p.text
                return text

            insight_text = extract_non_code_text(asyncio.run(generate_insight()))

    # Build assistant message
    assistant_msg = {
        "role": "assistant",
        "content": response_without_code,
    }
    if figure is not None:
        assistant_msg["figure"] = figure
    if insight_text is not None:
        assistant_msg["insight"] = insight_text

    st.session_state.messages.append(assistant_msg)  # type: ignore
    st.session_state.usage.record_turn()
    _save_current_session()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. MAIN LAYOUT — UPLOAD-FIRST or CHAT + DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.title("DataVerse - Agent Dashboard Generation")

# ── BRANCH: No data loaded yet → Upload-First Landing ─────────────────────
if st.session_state.modified_df is None:

    st.markdown("")
    # Centered hero layout
    _left_spacer, center_col, _right_spacer = st.columns([1, 2, 1])

    with center_col:
        st.markdown(
            "<div style='text-align:center; padding: 1.5rem 0 0.5rem;'>"
            "<span style='font-size:3.5rem;'>📂</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<h2 style='text-align:center; margin-bottom:0.25rem;'>Upload Your Dataset</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align:center; color:#64748B; font-size:1.05rem; margin-bottom:1.5rem;'>"
            f"{random.choice(UPLOAD_LANDING_MESSAGES)}</p>",
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Choose a data file",
            type=["csv", "xls", "xlsx", "parquet", "json", "tsv"],
            label_visibility="collapsed",
            key="hero_uploader",
        )

        if uploaded_file is not None:
            # ── Excel multi-sheet handling ────────────────────────────────
            selected_sheet = 0  # default: first sheet
            file_name_lower = uploaded_file.name.lower()

            if file_name_lower.endswith((".xls", ".xlsx")):
                sheet_names = get_excel_sheet_names(uploaded_file)
                uploaded_file.seek(0)  # reset after reading sheet names

                if len(sheet_names) > 1:
                    st.markdown("##### 📑 This file has multiple sheets")
                    selected_sheet = st.selectbox(
                        "Select a sheet to load",
                        options=sheet_names,
                        key="hero_sheet_picker",
                    )
                    if not st.button("✅ Load selected sheet", key="hero_load_sheet", type="primary"):
                        st.stop()  # wait for user to confirm sheet selection

            df, error = load_dataframe(uploaded_file, sheet_name=selected_sheet)
            if error:
                st.error(f"⚠️ Error loading file: {error}")
            else:
                st.session_state.modified_df = df.copy()
                # Immutable backup — never overwritten, used as a restore point
                st.session_state.original_df = df.copy()

                # Build the system context string
                buf = io.StringIO()
                st.session_state.modified_df.info(buf=buf)
                df_info = buf.getvalue()
                df_head = st.session_state.modified_df.head(10).to_string()  # type: ignore

                # PHASE 1: Data Quality Check (Cleaning Agent)
                # We fire a silent prompt directly to the Orchestrator/Cleaning Agent
                # to perform automated data quality repairs before analysis starts.
                cleaning_prompt = (
                    "[INITIAL-CLEANING]\n\n"
                    "[System Context]: The user just uploaded a new dataset. "
                    "Analyze the dataset for missing values, duplicate rows, and incorrect data types. "
                    "Apply necessary corrections (e.g., filling nulls with median, dropping duplicates) "
                    "and SAVE the cleaned result to `final_df` so it persists for the user. "
                    "Report a concise summary of what was cleaned."
                )

                with st.spinner("Ensuring data quality... (Cleaning Phase)"):
                    _run_agent_and_save(cleaning_prompt)

                # PHASE 2: Exploratory Insights (Visual Analyst)
                # Now that the data is clean (st.session_state.modified_df is updated via _run_agent_and_save),
                # we fire the original [AUTO-ANALYSIS] prompt for recommendations.
                auto_prompt = (
                    "[AUTO-ANALYSIS]\n\n"
                    "[System Context]: The dataset has been cleaned. "
                    "Recommend 5 specific insights or analyses the user could explore. "
                    "Do NOT create any charts yet."
                )

                with st.spinner(random.choice(ANALYZING_DATA_MESSAGES)):
                    _run_agent_and_save(auto_prompt)

                st.rerun()

        # Helpful tips below the uploader
        st.markdown("")
        st.markdown("---")
        tips_col1, tips_col2, tips_col3 = st.columns(3)
        with tips_col1:
            st.markdown("##### 📊 Visualize")
            st.caption("Generate bar, line, scatter, and more charts from your data.")
        with tips_col2:
            st.markdown("##### 🔮 Forecast")
            st.caption("Predict future trends with time-series analysis.")
        with tips_col3:
            st.markdown("##### 🧹 Clean")
            st.caption("Fix missing values, duplicates, and data quality issues.")


# ── BRANCH: Data loaded → Normal Chat + Dashboard ─────────────────────────
else:
    chat_col, dash_col = st.columns([4, 6], gap="large")

    with chat_col:
        st.subheader("💬 Chat & Explore")

        # Render previous chat history
        for idx, msg in enumerate(st.session_state.messages):  # type: ignore
            with st.chat_message(msg["role"]):  # type: ignore
                st.markdown(msg["content"])  # type: ignore

                # Show enriched query subtitle for user messages
                if msg.get("enriched_query"):
                    st.caption(f"✨ Enriched: {msg['enriched_query']}")

                # Show output string from code execution
                if "output" in msg:
                    st.markdown(f"```python\n{msg['output']}\n```")  # type: ignore

                # Show previously generated figure
                if "figure" in msg:
                    try:
                        st.pyplot(msg["figure"])  # type: ignore
                    except Exception as e:
                        st.error(f"⚠️ Could not render visual: {e}")

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

        # ── Chat Input Box ────────────────────────────────────────────────
        if prompt := st.chat_input("Ask for a visualization (attach a data file)...", accept_file="multiple"):
            user_text = (
                getattr(prompt, "text", "")
                if hasattr(prompt, "text")
                else (prompt if isinstance(prompt, str) else "")
            )  # type: ignore
            uploaded_files = getattr(prompt, "files", []) if hasattr(prompt, "files") else []

            # Handle new file uploads (re-upload mid-session)
            if uploaded_files:
                uploaded_file = uploaded_files[0]
                df, error = load_dataframe(uploaded_file)
                if error:
                    st.error(f"⚠️ Error loading file: {error}")
                else:
                    st.session_state.modified_df = df.copy()
                    buf = io.StringIO()
                    st.session_state.modified_df.info(buf=buf)
                    df_info = buf.getvalue()
                    df_head = st.session_state.modified_df.head(10).to_string()  # type: ignore

            # Enrich the query via direct Gemini API call
            enriched_question = user_text  # fallback
            if st.session_state.modified_df is not None:
                # Check budget before enrichment
                if st.session_state.usage.total_tokens >= st.session_state.max_budget_tokens:
                    st.error("❌ Request blocked: Session budget exceeded.")
                    st.stop()

                with st.spinner("Enriching question..."):
                    try:
                        enriched_question, usage = enrich_query(user_text, st.session_state.modified_df)
                        st.session_state.usage.record_api_call(usage)
                    except Exception:
                        enriched_question = user_text  # graceful fallback to raw query

            # The actual prompt we send to the LLM
            llm_prompt = enriched_question

            with st.chat_message("user"):
                st.markdown(user_text)
                if enriched_question != user_text:
                    st.caption(f"✨ Enriched: {enriched_question}")

            with st.spinner("Agent is thinking..."):
                user_msg = {"role": "user", "content": user_text}
                if enriched_question != user_text:
                    user_msg["enriched_query"] = enriched_question
                st.session_state.messages.append(user_msg)
                _run_agent_and_save(llm_prompt)

            st.rerun()


    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. DASHBOARD RENDER
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
                            try:
                                st.pyplot(item["figure"], use_container_width=True)
                            except Exception as e:
                                st.error(f"⚠️ Could not render pinned visual: {e}")
                            if item.get("insight"):
                                st.info(f"💡 {item['insight']}")

                            if st.button("❌ Remove", key=f"remove_btn_{i}"):
                                st.session_state.dashboard_items.pop(i)
                                _save_current_session()
                                st.rerun()
