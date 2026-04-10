import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from dataverse_agent.tools import (
    fetch_sql_data_to_sandbox,
    set_session_context,
    get_session_figures,
    _local,
    viz_tool
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture(autouse=True)
def cleanup_session():
    """Clean up thread-local state after each test."""
    yield
    get_session_figures()
    if hasattr(_local, "df"):
        del _local.df
    if hasattr(_local, "viz_temp_df"):
        _local.viz_temp_df = None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SQL AGGREGATION & HANDOFF TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_fetch_sql_data_success():
    """Test that fetch_sql_data_to_sandbox correctly populates viz_temp_df."""
    mock_df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    
    with patch("models.connectors.get_active_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.execute_query.return_value = mock_df
        mock_get_connector.return_value = mock_connector
        
        result = fetch_sql_data_to_sandbox("SELECT * FROM dummy")
        
        assert "Successfully fetched 2 rows" in result
        assert _local.viz_temp_df is not None
        assert _local.viz_temp_df.equals(mock_df)

def test_fetch_sql_data_empty():
    """Test behavior when SQL query returns no data."""
    mock_df = pd.DataFrame()
    
    with patch("models.connectors.get_active_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.execute_query.return_value = mock_df
        mock_get_connector.return_value = mock_connector
        
        result = fetch_sql_data_to_sandbox("SELECT * FROM empty_table")
        
        assert "returned zero rows" in result
        assert _local.viz_temp_df is None

def test_visual_analyst_prefers_viz_temp_df():
    """Verify that Visual Analyst tool (viz_tool) uses viz_temp_df if present."""
    main_df = pd.DataFrame({"X": ["Global"], "Y": [100]})
    sql_df = pd.DataFrame({"X": ["Local"], "Y": [10]}) # The "fetched" data
    
    set_session_context(main_df)
    _local.viz_temp_df = sql_df
    
    # We call the viz_tool (create_visualization)
    # If it uses sql_df, the X label should be "Local"
    from dataverse_agent.tools import create_visualization
    create_visualization(chart_type="bar", x_column="X", y_column="Y")
    
    figs = get_session_figures()
    assert len(figs) == 1
    ax = figs[0].gca()
    
    # Check X label (it applies _format_label, so "X" -> "X")
    assert ax.get_xlabel() == "X"
    
    # Check if the data plotted was from sql_df
    # In a bar chart, the categories are on the x-axis (or y if horizontal)
    tick_labels = [t.get_text() for t in ax.get_xticklabels()]
    assert "Local" in tick_labels
    assert "Global" not in tick_labels

def test_sql_agent_handover_flow():
    """
    Simulated multi-agent flow:
    1. SQL Agent fetches data.
    2. Visual Analyst plots the result.
    """
    mock_data = pd.DataFrame({"Metric": ["A", "B"], "Value": [50, 60]})
    
    with patch("models.connectors.get_active_connector") as mock_get_connector:
        mock_connector = MagicMock()
        mock_connector.execute_query.return_value = mock_data
        mock_get_connector.return_value = mock_connector
        
        # Step 1: SQL Agent tool call
        fetch_sql_data_to_sandbox("SELECT ...")
        
        # Step 2: Visual Analyst tool call
        from dataverse_agent.tools import create_visualization
        create_visualization(chart_type="pie", x_column="Metric", y_column="Value")
        
        figs = get_session_figures()
        assert len(figs) == 1
        # For pie charts, we check labels
        ax = figs[0].gca()
        # Labels are handled differently in pie charts (wedges/texts)
        # But we can check if the underlying data in _local was used.
        # Just verifying it didn't crash and viz_temp_df was cleared after figure collection.
        assert _local.viz_temp_df is None # Cleared by get_session_figures
