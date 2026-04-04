import threading
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from google.adk.tools import FunctionTool

# Use threading.local to safely pass the DataFrame and Figures
# between Streamlit's main execution thread and the ADK tools execution context
_local = threading.local()

def set_session_context(df: pd.DataFrame):
    """Register the dataframe and a fresh figure store for the current thread."""
    _local.df = df
    _local.figures = []

def get_session_figures() -> list:
    """Retrieve and clear generated figures for this thread.
    Also clears viz_temp_df so Visual Analyst's filtered subsets never
    leak into the next question.
    """
    figs = getattr(_local, "figures", [])
    _local.figures = []
    _local.viz_temp_df = None  # Clear temp data *after* figures are collected
    return figs

def get_session_data_summary() -> str:
    """Generate a text summary of the actual data used in the latest chart.
    Used to ground the Vision Agent and prevent numeric hallucinations.
    """
    df = _get_df()
    if df is None:
        return ""
    
    # Capture a concise statistical summary
    summary = []
    summary.append(f"Rows: {len(df)}")
    if not df.empty:
        # For numeric columns, provide sum, mean, max for grounding
        num_df = df.select_dtypes(include='number')
        if not num_df.empty:
            summary.append("Numeric Summary:")
            summary.append(num_df.agg(['sum', 'mean', 'max', 'min']).to_string())
        
        # For categorical columns, provide top 5 values
        cat_df = df.select_dtypes(exclude='number')
        if not cat_df.empty:
            summary.append("Category Samples:")
            for col in cat_df.columns[:3]: # limit to first 3 cats
                top_v = df[col].value_counts().head(5).to_string()
                summary.append(f"- {col}:\n{top_v}")
    
    # No side-effects here to allow multiple calls if needed
    return "\n".join(summary)

def get_final_df() -> pd.DataFrame | None:
    """Retrieve the persisted DataFrame (final_df) from the cleaning agent, if any.

    ONLY intended for the Cleaning Agent's persistent full-dataset
    transformations. Visual Analyst's temporary filtered subsets are stored
    in _local.viz_temp_df and are never returned here.

    The name mirrors the sandbox variable `final_df` that the cleaning agent
    prompt instructs the LLM to assign to.

    Returns:
        The persisted DataFrame, or None if no cleaning was performed.
    """
    result = getattr(_local, "final_df", None)
    _local.final_df = None  # clear after retrieval
    return result

def _get_df() -> pd.DataFrame:
    # 1. Check for a viz-scoped temp df (from multi-step execution within
    #    the current Visual Analyst turn — e.g. top-5 filtered subset).
    #    This is intentionally NOT persisted to the session.
    viz_temp = getattr(_local, "viz_temp_df", None)
    if viz_temp is not None:
        return viz_temp
    # 2. Check for final_df (from the Cleaning Agent — persisted to session).
    final = getattr(_local, "final_df", None)
    if final is not None:
        return final
    # 3. Fall back to the original session df.
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
    Strips unnecessary trailing .0 (e.g. 500.0K → 500K).
    """
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000:
        formatted = f"{abs_val / 1_000_000_000:.1f}"
        return f"{sign}{formatted.rstrip('0').rstrip('.')}B"
    elif abs_val >= 1_000_000:
        formatted = f"{abs_val / 1_000_000:.1f}"
        return f"{sign}{formatted.rstrip('0').rstrip('.')}M"
    elif abs_val >= 1_000:
        formatted = f"{abs_val / 1_000:.1f}"
        return f"{sign}{formatted.rstrip('0').rstrip('.')}K"
    elif abs_val == 0:
        return "0"
    elif abs_val < 1:
        return f"{val:.3g}"
    else:
        return f"{sign}{abs_val:.0f}"

def _percent_format(val, pos=None):
    """Format decimal values (0.0 to 1.0) as percentages (0% to 100%)."""
    return f"{val * 100:.1f}%".replace(".0%", "%")

def create_visualization(chart_type: str, x_column: str, y_column: str = None, hue: str = None, estimator: str = "mean", title: str = None, subtitle: str = None, sort_order: str = "ascending") -> str:
    """Create a Seaborn or Matplotlib visualization from the dataset.
    
    Args:
        chart_type: The type of chart ('bar', 'line', 'scatter', 'hist', 'box', 'violin', 'heatmap', 'pie', 'stacked_area', 'slope').
        x_column: The name of the column for the X-axis.
        y_column: The name of the column for the Y-axis (optional for some charts).
        hue: The name of the column to group by color (optional).
        estimator: Statistical function to use for aggregation ('mean', 'sum', 'count', 'min', 'max'). Defaults to 'mean'.
        title: The title of the chart (e.g. "Revenue by Region").
        subtitle: A descriptive label shown below the title (e.g. "Comparison of total units sold by model type").
        sort_order: How to sort categorical bars — 'ascending' (default), 'descending', or 'none' (dataset order).
        
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
        # Prevent Seaborn warning: "Passing palette without assigning hue is deprecated"
        use_legend = True if hue else False
        plot_hue = hue
        
        if chart_type in ('bar', 'box', 'violin'):
            is_horizontal = (
                y_column is not None
                and pd.api.types.is_numeric_dtype(df[x_column])
                and not pd.api.types.is_numeric_dtype(df[y_column])
            )
            cat_col = y_column if is_horizontal else x_column
        else:
            cat_col = x_column
            
        # For bar and hist, mapping hue to the categorical column resolves warnings safely
        if not hue and chart_type in ('bar', 'hist'):
            plot_hue = cat_col

        # Ensure palette safely covers all categories
        if not hue:
            num_categories = df[plot_hue].nunique() if plot_hue and plot_hue in df.columns else 1
            palette = [HIGHLIGHT] * max(1, num_categories)
        else:
            num_categories = df[hue].nunique() if hue in df.columns else len(PALETTE)
            if num_categories > len(PALETTE):
                palette = (PALETTE * ((num_categories // len(PALETTE)) + 1))[:num_categories]
            else:
                palette = PALETTE[:max(1, num_categories)]
        
        if chart_type == 'bar':
            # Determine bar orientation: horizontal if x is numeric and y is categorical
            is_horizontal = (
                y_column is not None
                and pd.api.types.is_numeric_dtype(df[x_column])
                and not pd.api.types.is_numeric_dtype(df[y_column])
            )

            # Auto-sort categorical axis by aggregated value
            bar_order = None
            if not hue:
                cat_col = y_column if is_horizontal else x_column
                num_col = x_column if is_horizontal else y_column
                if cat_col and num_col and cat_col in df.columns and num_col in df.columns:
                    agg_func = estimator if estimator in ("sum", "min", "max") else "mean"
                    ascending = sort_order != "descending"
                    bar_order = (
                        df.groupby(cat_col)[num_col]
                        .agg(agg_func)
                        .sort_values(ascending=ascending)
                        .index.tolist()
                    )

            # Error bars are only meaningful for mean aggregations
            error_bar_config = ("ci", 95) if estimator == "mean" else None

            if is_horizontal:
                sns.barplot(data=df, x=x_column, y=y_column, hue=plot_hue, palette=palette, ax=ax,
                            edgecolor="none", saturation=0.95, estimator=estimator,
                            errorbar=error_bar_config, order=bar_order, legend=use_legend)
                for container in ax.containers:
                    labels = [_human_format(v.get_width()) for v in container]
                    ax.bar_label(container, labels=labels, fontsize=9, color=CAPTION_COLOR, padding=3)
            else:
                sns.barplot(data=df, x=x_column, y=y_column, hue=plot_hue, palette=palette, ax=ax,
                            edgecolor="none", saturation=0.95, estimator=estimator,
                            errorbar=error_bar_config, order=bar_order, legend=use_legend)
                for container in ax.containers:
                    labels = [_human_format(v.get_height()) for v in container]
                    ax.bar_label(container, labels=labels, fontsize=9, color=CAPTION_COLOR, padding=3)
        elif chart_type == 'line':
            # Error bars are only meaningful for mean aggregations
            error_config = None
            if estimator == "mean":
                error_config = None if (hue and df[hue].nunique() > 3) else "sd"

            if plot_hue:
                sns.lineplot(data=df, x=x_column, y=y_column, hue=plot_hue, palette=palette, ax=ax, linewidth=2.5, marker="o", markersize=6, estimator=estimator, errorbar=error_config, legend=use_legend)
            else:
                # Use scalar color to avoid palette without hue warnings
                sns.lineplot(data=df, x=x_column, y=y_column, color=HIGHLIGHT, ax=ax, linewidth=2.5, marker="o", markersize=6, estimator=estimator, errorbar=error_config)
        elif chart_type == 'scatter':
            sns.scatterplot(data=df, x=x_column, y=y_column, hue=plot_hue, palette=palette, ax=ax, s=70, alpha=0.8, edgecolor="white", linewidth=0.5, legend=use_legend)
        elif chart_type == 'hist':
            sns.histplot(data=df, x=x_column, hue=plot_hue, palette=palette, ax=ax, kde=True, edgecolor="white", linewidth=0.5, alpha=0.75, legend=use_legend)
        elif chart_type == 'box':
            sns.boxplot(data=df, x=x_column, y=y_column, hue=hue, palette=palette, ax=ax, linewidth=1.2, flierprops=dict(marker="o", markersize=4, alpha=0.5))
        elif chart_type == 'violin':
            sns.violinplot(data=df, x=x_column, y=y_column, hue=hue, palette=palette, ax=ax, linewidth=1, inner="box", alpha=0.85)
        elif chart_type == 'stacked_area':
            if hue:
                # Pivot data for stacking: rows=X, columns=Hue, values=Y
                pivot_df = df.pivot_table(index=x_column, columns=hue, values=y_column, aggfunc=estimator).fillna(0)
                ax.stackplot(pivot_df.index, pivot_df.values.T, labels=pivot_df.columns, colors=palette, alpha=0.8)
                use_legend = True
            else:
                # Single area chart
                ax.fill_between(df[x_column], df[y_column] if y_column else 0, color=HIGHLIGHT, alpha=0.4)
                ax.plot(df[x_column], df[y_column] if y_column else 0, color=HIGHLIGHT, linewidth=2)
        elif chart_type == 'slope':
            if not hue:
                plt.close(fig)
                return "Error: Slope chart requires 'hue' parameter for comparison."
            # Filter to min and max X to enforce the two-point slope 
            unique_x = sorted(df[x_column].unique())
            if len(unique_x) > 2:
                min_x, max_x = unique_x[0], unique_x[-1]
                slope_df = df[df[x_column].isin([min_x, max_x])]
            else:
                slope_df = df
                
            pivot_df = slope_df.pivot_table(index=hue, columns=x_column, values=y_column, aggfunc=estimator).dropna()
            if pivot_df.empty or pivot_df.shape[1] != 2:
                plt.close(fig)
                return "Error: Slope chart could not find two distinct X values to connect."
            
            x_vals = pivot_df.columns
            for i, category in enumerate(pivot_df.index):
                y_vals = pivot_df.loc[category].values
                color = palette[i % len(palette)]
                ax.plot(x_vals, y_vals, marker='o', markersize=6, label=category, color=color, linewidth=2.5)
            
            ax.set_xticks(x_vals)
            ax.set_xlim(min(x_vals) - (max(x_vals)-min(x_vals))*0.1, max(x_vals) + (max(x_vals)-min(x_vals))*0.1)
            use_legend = True
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
            
            def _is_year_column(col_name: str) -> bool:
                """Check if a numeric column likely contains year values."""
                if col_name not in df.columns:
                    return False
                col = df[col_name].dropna()
                if len(col) == 0:
                    return False
                
                # Check for 4-digit integers in year range (1900-2100)
                is_numeric = pd.api.types.is_numeric_dtype(col)
                if not is_numeric:
                    return False
                
                # Check if values are mostly integers in the year range
                # Use a small tolerance for floating point noise
                is_in_range = col.between(1900, 2100).all()
                is_mostly_int = (col % 1 == 0).all()
                
                return is_in_range and is_mostly_int

            # Helper: detect month-like columns (e.g., 1-12)
            def _is_month_column(col_name: str) -> bool:
                """Check if a column likely contains month values (1-12)."""
                if col_name not in df.columns:
                    return False
                col = df[col_name].dropna()
                if len(col) == 0:
                    return False
                
                # Name contains "month" and values are integers 1-12
                name_suggests = "month" in col_name.lower()
                is_int_1_12 = pd.api.types.is_numeric_dtype(col) and col.between(1, 12).all() and (col == col.astype(int)).all()
                
                return name_suggests and is_int_1_12

            def _month_name(val, pos=None):
                months = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 
                          7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
                return months.get(int(val), str(int(val)))

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
                elif _is_month_column(x_column):
                    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_month_name))
                elif _is_percent_column(x_column):
                    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_percent_format))
                else:
                    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_human_format))
            
            if y_column:
                if pd.api.types.is_numeric_dtype(df[y_column]):
                    if _is_year_column(y_column):
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}"))
                    elif _is_month_column(y_column):
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_month_name))
                    elif _is_percent_column(y_column):
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_percent_format))
                    else:
                        ax.yaxis.set_major_formatter(mticker.FuncFormatter(_human_format))
            else:
                # E.g. histograms where y-axis is the count/density
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(_human_format))
            # Auto-rotate x labels if they are long or numerous
            ticks = ax.get_xticklabels()
            max_label_len = max([len(t.get_text()) for t in ticks]) if ticks else 0
            if len(ticks) > 5 or max_label_len > 8:
                plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=9)
        
        # ── Legend Styling ───────────────────────────────────────────────
        if hue and chart_type not in ('heatmap', 'pie'):
            legend = ax.get_legend()
            if not legend and use_legend:
                legend = ax.legend()
                
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
            # Increase top margin to prevent title/subtitle overlap with plot
            fig.subplots_adjust(top=0.85 if (title and subtitle) else 0.88)
            if title:
                fig.suptitle(title, fontsize=17, fontweight="bold", color=TEXT_COLOR, y=0.98, ha="center")
            if subtitle:
                sub_y = 0.93 if title else 0.96
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
    
    # If the code produced a DataFrame (viz_df or final_df), capture it.
    # viz_df → Visual Analyst's temp scoped variable (never persisted to session).
    # final_df → Cleaning Agent's persistent variable (persisted to session).
    if result.dataframe is not None:
        # Infer which agent produced this: if the code contains 'viz_df', treat as temp.
        # Otherwise store as final_df (Cleaning Agent behaviour).
        if "viz_df" in code:
            _local.viz_temp_df = result.dataframe
        else:
            _local.final_df = result.dataframe
        
    output = result.output if result.output else "Code executed successfully."
    return output

viz_tool = FunctionTool(func=create_visualization)
summary_tool = FunctionTool(func=get_data_summary)
fallback_tool = FunctionTool(func=execute_python_code_fallback)

TOOLS = [viz_tool, summary_tool, fallback_tool]
