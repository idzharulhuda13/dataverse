import sys
import os
from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EARLY MOCKING — Must happen before importing the dashboard
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

mock_st = MagicMock()
mock_st.secrets = {"GEMINI_API_KEY": "test-key"}
mock_st.session_state = MagicMock()

def mock_columns(spec, **kwargs):
    if isinstance(spec, list):
        return [MagicMock() for _ in range(len(spec))]
    return [MagicMock() for _ in range(spec)]

mock_st.columns.side_effect = mock_columns
mock_st.chat_input.return_value = None 
mock_st.file_uploader.return_value = None

# Mocking the entire google package to prevent import crashes or real API calls
sys.modules["streamlit"] = mock_st
sys.modules["google"] = MagicMock()
sys.modules["google.adk"] = MagicMock()
sys.modules["google.adk.runners"] = MagicMock()
sys.modules["google.adk.sessions.in_memory_session_service"] = MagicMock()
sys.modules["google.genai"] = MagicMock()

# Now we can safely import the dashboard
# We use importlib to ensure we get a fresh import if needed, 
# but for simple unit tests a direct import is fine since we mocked st
import streamlit_agent_dashboard as dash

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_new_session_id():
    sid = dash._new_session_id()
    assert isinstance(sid, str)
    assert len(sid) == 8

def test_session_display_name():
    name = dash._session_display_name()
    assert name.startswith("Session – ")
    # Verify it has the date/time (roughly)
    now = datetime.now()
    assert now.strftime("%b") in name

def test_create_session():
    # Setup mock session_state
    mock_st.session_state.sessions = {}
    
    with patch("streamlit_agent_dashboard._new_session_id", return_value="test-sid"):
        sid = dash._create_session("Custom Name")
        
        assert sid == "test-sid"
        assert "test-sid" in mock_st.session_state.sessions
        assert mock_st.session_state.sessions[sid]["name"] == "Custom Name"
        assert isinstance(mock_st.session_state.sessions[sid]["created_at"], datetime)

def test_save_current_session():
    mock_st.session_state.current_session_id = "sid-123"
    mock_st.session_state.sessions = {"sid-123": {}}
    mock_st.session_state.messages = ["msg1"]
    mock_st.session_state.modified_df = "mock-df"
    mock_st.session_state.dashboard_items = ["item1"]
    
    dash._save_current_session()
    
    session = mock_st.session_state.sessions["sid-123"]
    assert session["messages"] == ["msg1"]
    assert session["modified_df"] == "mock-df"
    assert session["dashboard_items"] == ["item1"]

def test_load_session():
    sid = "sid-456"
    mock_st.session_state.sessions = {
        sid: {
            "messages": ["msg-old"],
            "modified_df": "df-old",
            "dashboard_items": ["item-old"]
        }
    }
    
    dash._load_session(sid)
    
    assert mock_st.session_state.current_session_id == sid
    assert mock_st.session_state.messages == ["msg-old"]
    assert mock_st.session_state.modified_df == "df-old"
    assert mock_st.session_state.dashboard_items == ["item-old"]

def test_switch_session():
    sid = "sid-next"
    with patch("streamlit_agent_dashboard._save_current_session") as mock_save, \
         patch("streamlit_agent_dashboard._load_session") as mock_load:
        
        # Reset because top-level code in dashboard might have called it
        mock_st.rerun.reset_mock()
        
        dash._switch_session(sid)
        
        mock_save.assert_called_once()
        mock_load.assert_called_once_with(sid)
        assert mock_st.rerun.call_count == 1
