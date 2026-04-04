import pytest
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

# Force non-interactive backend so plots aren't displayed during testing
matplotlib.use("Agg")

from dataverse_agent.tools import (
    create_visualization,
    set_session_context,
    get_session_figures,
    _local,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture(scope="module")
def bmw_df():
    """Load the BMW dataset for testing."""
    df = pd.read_csv("data/bmw_global_sales_2018_2025.csv")
    return df

@pytest.fixture(autouse=True)
def setup_teardown_session(bmw_df):
    """
    Automatically set the thread-local dataframe before each test
    and clean up the matplotlib figures after.
    """
    set_session_context(bmw_df.copy())
    yield
    # Cleanup figures
    get_session_figures()
    plt.close('all')
    if hasattr(_local, "df"):
        del _local.df

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ERROR HANDLING TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_no_dataset_loaded():
    """Test behavior when no dataframe is in the thread-local context."""
    # Temporarily remove df
    if hasattr(_local, "df"):
        del _local.df
        
    result = create_visualization(chart_type="bar", x_column="Region")
    assert "Error: No dataset loaded" in result

def test_unsupported_chart_type():
    """Test behavior with an unknown chart type."""
    result = create_visualization(chart_type="radar", x_column="Region")
    assert "Error: Unsupported chart_type" in result
    assert "radar" in result
    
    # Assert no figure was saved
    figs = get_session_figures()
    assert len(figs) == 0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CHART GENERATOR TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestChartGenerations:
    
    @pytest.mark.parametrize("chart_type, kwargs", [
        ("bar", {"x_column": "Region", "y_column": "Units_Sold"}),
        ("line", {"x_column": "Year", "y_column": "Revenue_EUR", "hue": "Region"}),
        ("scatter", {"x_column": "Units_Sold", "y_column": "Revenue_EUR", "hue": "Model"}),
        ("hist", {"x_column": "Avg_Price_EUR"}),
        ("box", {"x_column": "Region", "y_column": "Units_Sold"}),
        ("violin", {"x_column": "Region", "y_column": "Units_Sold", "hue": "Region"}),
        ("heatmap", {"x_column": "Doesn't Matter"}),  # Heatmap auto-selects numeric columns
        ("pie", {"x_column": "Region"}),
    ])
    def test_chart_creation_success(self, chart_type, kwargs):
        """Test that all supported chart types return success and save a Figure."""
        result = create_visualization(chart_type=chart_type, **kwargs)
        
        assert result == "Visualization created successfully."
        
        figs = get_session_figures()
        assert len(figs) == 1
        assert isinstance(figs[0], plt.Figure)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AESTHETIC DETAILS & FORMATTING TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_human_readable_labels():
    """Verify raw column names are converted to human-readable forms."""
    create_visualization(
        chart_type="bar", 
        x_column="Avg_Price_EUR", 
        y_column="Units_Sold", 
        title="My Custom Title"
    )
    
    fig = get_session_figures()[0]
    ax = fig.gca()
    
    # "Avg_Price_EUR" should become "Average Price EUR" (title-cased and underscored removed, acronyms preserved)
    assert ax.get_xlabel() == "Average Price EUR"
    assert ax.get_ylabel() == "Units Sold"

def test_title_and_subtitle_rendering():
    """Verify titles and subtitles are correctly set on the figure."""
    create_visualization(
        chart_type="scatter", 
        x_column="Units_Sold", 
        y_column="Revenue_EUR", 
        title="Revenue Analysis",
        subtitle="Higher units align with revenue"
    )
    
    fig = get_session_figures()[0]
    
    # Title is usually the overall figure suptitle
    assert fig._suptitle is not None
    assert fig._suptitle.get_text() == "Revenue Analysis"
    
    # Subtitle is added as a custom text element
    texts = [t.get_text() for t in fig.texts]
    assert "Higher units align with revenue" in texts

def test_year_axis_formatting():
    """Year columns should not have decimals or scientific notation (2018, not 2,018 or 2e3)."""
    create_visualization(chart_type="line", x_column="Year", y_column="Units_Sold")
    
    fig = get_session_figures()[0]
    ax = fig.gca()
    
    # Get the formatter for the X axis
    formatter = ax.xaxis.get_major_formatter()
    
    # Test formatting 2018.0 -> "2018"
    from matplotlib.ticker import FuncFormatter
    assert isinstance(formatter, FuncFormatter)
    
    # 2018 should not have K, M, decimals, or commas
    formatted_val = formatter(2018.0)
    assert formatted_val == "2018"

def test_percent_axis_formatting():
    """Columns representing percentages/shares (0 to 1) should be formatted as %."""
    create_visualization(chart_type="bar", x_column="Region", y_column="BEV_Share")
    
    fig = get_session_figures()[0]
    ax = fig.gca()
    
    formatter = ax.yaxis.get_major_formatter()
    
    # A value of 0.15 should be "15%"
    formatted_val = formatter(0.15)
    assert "%" in formatted_val

def test_hue_legend_formatting():
    """Ensure the legend title is correctly formatted when hue is used."""
    create_visualization(
        chart_type="scatter", 
        x_column="Units_Sold", 
        y_column="Revenue_EUR", 
        hue="Avg_Price_EUR"
    )
    
    fig = get_session_figures()[0]
    ax = fig.gca()
    
    legend = ax.get_legend()
    assert legend is not None
    assert legend.get_title().get_text() == "Average Price EUR"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ADDITIONAL TOOL TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_session_context_management(bmw_df):
    """Verify set_session_context and _get_df work as expected."""
    set_session_context(bmw_df)
    assert _local.df is bmw_df
    from dataverse_agent.tools import _get_df
    assert _get_df() is bmw_df

def test_get_session_figures_handling():
    """Verify figures are correctly collected and cleared."""
    fig1, ax1 = plt.subplots()
    fig2, ax2 = plt.subplots()
    _local.figures = [fig1, fig2]
    
    figs = get_session_figures()
    assert len(figs) == 2
    assert fig1 in figs
    assert fig2 in figs
    
    # Verify it cleared the store
    assert len(get_session_figures()) == 0
    plt.close(fig1)
    plt.close(fig2)

def test_get_final_df_handling(bmw_df):
    """Verify final_df is retrieved and cleared."""
    _local.final_df = bmw_df
    from dataverse_agent.tools import get_final_df
    assert get_final_df() is bmw_df
    assert get_final_df() is None

def test_get_data_summary(bmw_df):
    """Verify the summary string describes the current dataframe."""
    set_session_context(bmw_df)
    from dataverse_agent.tools import get_data_summary
    summary = get_data_summary()
    assert "Data Summary:" in summary
    assert "First 5 rows:" in summary
    assert "Model" in summary # Column name from bmw dataset

def test_get_data_summary_no_df():
    """Verify error message when no dataframe is loaded."""
    if hasattr(_local, "df"):
        del _local.df
    from dataverse_agent.tools import get_data_summary
    assert "Error: No dataset loaded" in get_data_summary()

def test_execute_python_code_fallback_success(bmw_df):
    """Verify arbitrary code execution and result capture."""
    set_session_context(bmw_df)
    from dataverse_agent.tools import execute_python_code_fallback
    code = "final_df = df.copy()\nfinal_df['new_col'] = 123\nprint('Hello Fallback')"
    output = execute_python_code_fallback(code)
    
    assert "Hello Fallback" in output
    # Verify final_df was updated in _local
    from dataverse_agent.tools import get_final_df
    cleaned = get_final_df()
    assert cleaned is not None
    assert 'new_col' in cleaned.columns

def test_execute_python_code_fallback_figure(bmw_df):
    """Verify figures from fallback execution are captured."""
    set_session_context(bmw_df)
    from dataverse_agent.tools import execute_python_code_fallback
    code = "import matplotlib.pyplot as plt\nplt.figure()\nplt.plot([1, 2], [1, 2])"
    execute_python_code_fallback(code)
    
    figs = get_session_figures()
    assert len(figs) == 1
    plt.close('all')

def test_execute_python_code_fallback_blocked(bmw_df):
    """Verify blocked code returns error message."""
    set_session_context(bmw_df)
    from dataverse_agent.tools import execute_python_code_fallback
    code = "import os\nos.getcwd()"
    output = execute_python_code_fallback(code)
    assert "Code blocked" in output
