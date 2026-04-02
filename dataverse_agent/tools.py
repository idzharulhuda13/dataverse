import sys
import threading
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from typing import Dict, Any
from google.adk.tools import FunctionTool

# Use threading.local to safely pass the DataFrame and Figures
# between Streamlit's main execution thread and the ADK tools execution context
_local = threading.local()

def set_session_context(df: pd.DataFrame):
    """Register the dataframe and a fresh figure store for the current thread."""
    _local.df = df
    _local.figures = []

def get_session_figures() -> list:
    """Retrieve and clear generated figures for this thread."""
    figs = getattr(_local, "figures", [])
    _local.figures = []
    return figs

def get_cleaned_df() -> pd.DataFrame | None:
    """Retrieve the cleaned DataFrame from the cleaning agent, if any.
    
    When the cleaning agent executes code that assigns to `final_df`,
    the sandbox captures it and we store it here. The Streamlit dashboard
    checks this after each agent run to update the session DataFrame.
    
    Returns:
        The cleaned DataFrame, or None if no cleaning was performed.
    """
    cleaned = getattr(_local, "cleaned_df", None)
    _local.cleaned_df = None  # clear after retrieval
    return cleaned

def _get_df() -> pd.DataFrame:
    return getattr(_local, "df", None)

def _format_label(raw: str) -> str:
    """Transform raw column names into clean, human-readable axis labels.
    e.g. 'revenue_sum' → 'Revenue (Total)', 'avg_score' → 'Average Score'
    """
    if not raw:
        return ""
    
    # Common aggregation suffixes → parenthetical notation
    SUFFIX_MAP = {
        "_sum": " (Total)", "_total": " (Total)",
        "_avg": " (Avg)", "_mean": " (Avg)",
        "_count": " (Count)", "_cnt": " (Count)",
        "_min": " (Min)", "_max": " (Max)",
        "_std": " (Std Dev)", "_median": " (Median)",
        "_pct": " (%)", "_percent": " (%)", "_rate": " (Rate)",
    }
    
    # Common prefixes → expanded form
    PREFIX_MAP = {
        "avg_": "Average ", "mean_": "Average ",
        "sum_": "Total ", "total_": "Total ",
        "num_": "Number of ", "cnt_": "Count of ",
        "pct_": "% of ", "max_": "Max ", "min_": "Min ",    
    }
    
    label = raw.strip()
    
    # Check for suffix matches first
    suffix_added = ""
    for suffix, replacement in SUFFIX_MAP.items():
        if label.lower().endswith(suffix):
            label = label[:len(label) - len(suffix)]
            suffix_added = replacement
            break
    
    # Check for prefix matches
    for prefix, replacement in PREFIX_MAP.items():
        if label.lower().startswith(prefix):
            label = replacement + label[len(prefix):]
            break
    
    # Replace underscores/hyphens with spaces, then title-case each word, preserving uppercase acronyms
    words = label.replace("_", " ").replace("-", " ").strip().split()
    label = " ".join(w if w.isupper() else w.title() for w in words)
    
    # Append the parenthetical suffix
    label += suffix_added
    
    return label

def _human_format(val, pos=None):
    """Format large numbers into human-readable strings.
    e.g. 1500 → '1.5K', 2300000 → '2.3M', 1200000000 → '1.2B'
    """
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.1f}B"
    elif abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.1f}M"
    elif abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.1f}K"
    elif abs_val == 0:
        return "0"
    elif abs_val < 1:
        return f"{val:.3g}"
    else:
        return f"{sign}{abs_val:.0f}"

def _percent_format(val, pos=None):
    """Format decimal values (0.0 to 1.0) as percentages (0% to 100%)."""
    return f"{val * 100:.1f}%".rstrip('0').rstrip('.') + '%'

def create_visualization(chart_type: str, x_column: str, y_column: str = None, hue: str = None, title: str = None, subtitle: str = None) -> str:
    """Create a Seaborn or Matplotlib visualization from the dataset.
    
    Args:
        chart_type: The type of chart ('bar', 'line', 'scatter', 'hist', 'box', 'violin', 'heatmap', 'pie').
        x_column: The name of the column for the X-axis.
        y_column: The name of the column for the Y-axis (optional for some charts).
        hue: The name of the column to group by color (optional).
        title: The title of the chart (e.g. "Revenue by Region").
        subtitle: A short, insight-driven description shown below the title (e.g. "North America leads with 42% of total revenue, followed by EMEA at 28%").
        
    Returns:
        A success message indicating the chart was created.
    """
    df = _get_df()
    if df is None:
        return "Error: No dataset loaded."

    # ── Elegant Color Palette ────────────────────────────────────────────
    PALETTE = ["#2D3A4A", "#4A7C8F", "#7BA7A9", "#B8D4D2", "#D4A574", "#C4786C", "#8B6F8E", "#A3B5C7"]
    HIGHLIGHT = "#2D3A4A"   # deep navy
    ACCENT = "#D4A574"      # warm gold
    BG_COLOR = "#FAFBFC"
    TEXT_COLOR = "#1E293B"  # slate-800
    CAPTION_COLOR = "#64748B"  # slate-500
    GRID_COLOR = "#E2E8F0"  # slate-200
    
    import matplotlib
    matplotlib.rcParams.update({
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": BG_COLOR,
        "axes.edgecolor": GRID_COLOR,
        "axes.labelcolor": TEXT_COLOR,
        "xtick.color": CAPTION_COLOR,
        "ytick.color": CAPTION_COLOR,
        "text.color": TEXT_COLOR,
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
    })
    
    sns.set_theme(style="white", font_scale=1.05)
    
    fig, ax = plt.subplots(figsize=(11, 6.5))
    fig.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    
    try:
        palette = PALETTE if hue else [HIGHLIGHT]
        
        if chart_type == 'bar':
            sns.barplot(data=df, x=x_column, y=y_column, hue=hue, palette=palette, ax=ax, edgecolor="none", saturation=0.95)
            # Add human-readable value labels on bars
            for container in ax.containers:
                labels = [_human_format(v.get_height()) for v in container]
                ax.bar_label(container, labels=labels, fontsize=9, color=CAPTION_COLOR, padding=3)
        elif chart_type == 'line':
            sns.lineplot(data=df, x=x_column, y=y_column, hue=hue, palette=palette, ax=ax, linewidth=2.5, marker="o", markersize=6)
        elif chart_type == 'scatter':
            sns.scatterplot(data=df, x=x_column, y=y_column, hue=hue, palette=palette, ax=ax, s=70, alpha=0.8, edgecolor="white", linewidth=0.5)
        elif chart_type == 'hist':
            sns.histplot(data=df, x=x_column, hue=hue, palette=palette, ax=ax, kde=True, edgecolor="white", linewidth=0.5, alpha=0.75)
        elif chart_type == 'box':
            sns.boxplot(data=df, x=x_column, y=y_column, hue=hue, palette=palette, ax=ax, linewidth=1.2, flierprops=dict(marker="o", markersize=4, alpha=0.5))
        elif chart_type == 'violin':
            sns.violinplot(data=df, x=x_column, y=y_column, hue=hue, palette=palette, ax=ax, linewidth=1, inner="box", alpha=0.85)
        elif chart_type == 'heatmap':
            numeric_df = df.select_dtypes(include='number')
            sns.heatmap(numeric_df.corr(), annot=True, fmt=".2f", cmap="RdYlBu_r", ax=ax, linewidths=0.5, square=True, cbar_kws={"shrink": 0.8})
        elif chart_type == 'pie':
            if y_column:
                pie_data = df.groupby(x_column)[y_column].sum()
            else:
                pie_data = df[x_column].value_counts()
            colors = PALETTE[:len(pie_data)]
            wedges, texts, autotexts = ax.pie(pie_data, labels=pie_data.index, autopct='%1.1f%%', colors=colors, startangle=140, pctdistance=0.82, wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2))
            for t in autotexts:
                t.set_fontsize(9)
                t.set_color(TEXT_COLOR)
            ax.set_aspect('equal')
        else:
            plt.close(fig)
            return f"Error: Unsupported chart_type '{chart_type}'."
        
        # ── Axis Cleanup ─────────────────────────────────────────────────
        if chart_type != 'heatmap' and chart_type != 'pie':
            sns.despine(ax=ax, left=True, bottom=False)
            ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.6, alpha=0.7)
            ax.set_axisbelow(True)
            # Clean up label formatting
            ax.set_xlabel(_format_label(x_column), fontweight="medium", labelpad=10)
            ax.set_ylabel(_format_label(y_column) if y_column else "", fontweight="medium", labelpad=10)
            
            # Helper: detect year-like columns (e.g., 2018, 2019...) 
            def _is_year_column(col_name: str) -> bool:
                """Check if a numeric column likely contains year values."""
                if col_name not in df.columns:
                    return False
                col = df[col_name].dropna()
                if len(col) == 0:
                    return False
                return (
                    pd.api.types.is_numeric_dtype(col)
                    and col.between(1900, 2100).all()
                    and (col == col.astype(int)).all()
                )

            # Helper: detect percentage/ratio columns (e.g., share, pct...)
            def _is_percent_column(col_name: str) -> bool:
                """Check if a numeric column likely contains percentage/ratio values (0 to 1)."""
                if col_name not in df.columns:
                    return False
                col = df[col_name].dropna()
                if len(col) == 0:
                    return False
                # If name suggests percentage AND values are mostly between 0 and 1
                name_suggests = any(word in col_name.lower() for word in ["pct", "percent", "share", "ratio", "rate"])
                if name_suggests and col.between(0, 1.1).mean() > 0.9:
                    return True
                return False
            
            # Disable scientific notation on numeric axes ONLY
            # But use plain integer formatting for year-like columns
            if pd.api.types.is_numeric_dtype(df[x_column]):
                if _is_year_column(x_column):
                    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}"))
                elif _is_percent_column(x_column):
                    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_percent_format))
                else:
                    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_human_format))
            
            if y_column:
                if pd.api.types.is_numeric_dtype(df[y_column]):
                    if _is_year_column(y_column):
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}"))
                    elif _is_percent_column(y_column):
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_percent_format))
                    else:
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_human_format))
            else:
                # E.g. histograms where y-axis is the count/density
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(_human_format))
            # Auto-rotate x labels if many ticks
            if len(ax.get_xticklabels()) > 6:
                plt.setp(ax.get_xticklabels(), rotation=40, ha="right", fontsize=9)
        
        # ── Legend Styling ───────────────────────────────────────────────
        if hue and chart_type not in ('heatmap', 'pie'):
            legend = ax.get_legend()
            if legend:
                legend.set_title(_format_label(hue))
                legend.get_frame().set_facecolor(BG_COLOR)
                legend.get_frame().set_edgecolor(GRID_COLOR)
                legend.get_frame().set_alpha(0.9)
        
        # tight_layout FIRST, then position title/subtitle so they don't get overridden
        fig.tight_layout()
        
        # ── Title + Subtitle Formatting (AFTER tight_layout) ─────────
        has_header = title or subtitle
        if has_header:
            fig.subplots_adjust(top=0.86 if (title and subtitle) else 0.90)
            if title:
                fig.suptitle(title, fontsize=16, fontweight="bold", color=TEXT_COLOR, y=0.98, ha="center")
            if subtitle:
                sub_y = 0.935 if title else 0.97
                fig.text(0.5, sub_y, subtitle, fontsize=11, color=CAPTION_COLOR, ha="center", style="italic")
        
        # Save figure to registry
        if not hasattr(_local, "figures"):
            _local.figures = []
        _local.figures.append(fig)
            
        return "Visualization created successfully."
    except Exception as e:
        plt.close('all')
        return f"Error creating visualization: {str(e)}"

def get_data_summary() -> str:
    """Returns a summary of the dataset, including columns, data types, and missing values."""
    df = _get_df()
    if df is None:
        return "Error: No dataset loaded."
        
    import io
    buf = io.StringIO()
    df.info(buf=buf)
    info_str = buf.getvalue()
    
    head_str = df.head().to_string()
    
    return f"Data Summary:\n{info_str}\n\nFirst 5 rows:\n{head_str}"

def execute_python_code_fallback(code: str) -> str:
    """Fallback tool to execute arbitrary Python code when standard tools are insufficient.
    This should be used for complex data transformations or custom charts.
    Assume pandas is 'pd', matplotlib.pyplot is 'plt', seaborn is 'sns'. The dataset is named 'df'.
    
    Args:
        code: The Python code to execute. Do not include ```python blocks.
    """
    from models.sandbox import safe_execute
    
    df = _get_df()
    if df is None:
        return "Error: No dataset loaded."
        
    result = safe_execute(code, df)
    
    if result.blocked:
        return f"Code blocked: {result.blocked_reason}"
    if result.error:
        return f"Error: {result.error}"
        
    # If the code produced a figure, capture it
    if result.figure:
        if not hasattr(_local, "figures"):
            _local.figures = []
        _local.figures.append(result.figure)
    
    # If the code produced a cleaned DataFrame (final_df), capture it
    # This is used by the cleaning agent to persist transformations
    if result.dataframe is not None:
        _local.cleaned_df = result.dataframe
        
    output = result.output if result.output else "Code executed successfully."
    return output

viz_tool = FunctionTool(func=create_visualization)
summary_tool = FunctionTool(func=get_data_summary)
fallback_tool = FunctionTool(func=execute_python_code_fallback)

TOOLS = [viz_tool, summary_tool, fallback_tool]
