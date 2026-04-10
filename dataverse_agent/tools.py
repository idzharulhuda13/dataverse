import threading
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Ensure thread-safe, non-interactive plotting
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from google.adk.tools import FunctionTool
from dataverse_agent.errors import error_guardrail

# ── DataVerse Design System ──────────────────────────────────────────
PALETTE = ["#2D3A4A", "#D4A574", "#4A7C8F", "#7BA7A9", "#B8D4D2", "#C4786C", "#8B6F8E", "#A3B5C7"]
HIGHLIGHT = "#2D3A4A"   # DataVerse Navy
ACCENT = "#D4A574"      # DataVerse Gold
BG_COLOR = "#FAFBFC"
TEXT_COLOR = "#1E293B"  # slate-800
CAPTION_COLOR = "#64748B"  # slate-500
GRID_COLOR = "#E2E8F0"  # slate-200

def _apply_branding(fig=None, ax=None):
    """Apply unified DataVerse aesthetics to a figure and axis."""
    import matplotlib
    matplotlib.rcParams.update({
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": BG_COLOR,
        "axes.edgecolor": GRID_COLOR,
        "axes.labelcolor": TEXT_COLOR,
        "xtick.color": CAPTION_COLOR,
        "ytick.color": CAPTION_COLOR,
        "text.color": TEXT_COLOR,
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Public Sans", "Segoe UI", "Roboto", "Arial"],
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
    })
    if fig:
        fig.set_facecolor(BG_COLOR)
    if ax:
        ax.set_facecolor(BG_COLOR)
        sns.despine(ax=ax, left=True, bottom=False)
        ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.6, alpha=0.7)
        ax.set_axisbelow(True)

def _draw_empty_placeholder(ax, message="No Matching Data Found"):
    """Draw a styled placeholder when no data is available for a chart."""
    ax.text(0.5, 0.5, message, transform=ax.transAxes, 
            ha='center', va='center', fontsize=14, fontweight='bold',
            color=CAPTION_COLOR, bbox=dict(facecolor='white', alpha=0.8, edgecolor=GRID_COLOR, boxstyle='round,pad=1'))
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

_local = threading.local()

def set_session_context(df: pd.DataFrame):
    """Register the dataframe and a fresh figure store for the current thread."""
    _local.df = df
    _local.figures = []
    _local.display_df = None

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
        
        # For categorical columns, provide top 5 values (or full list if low cardinality)
        cat_df = df.select_dtypes(exclude='number')
        if not cat_df.empty:
            summary.append("Category Samples:")
            for col in cat_df.columns[:3]: # limit to first 3 cats
                uniques = df[col].dropna().unique()
                if len(uniques) <= 20:
                    summary.append(f"- {col} (All {len(uniques)} unique values):\n{uniques.tolist()}")
                else:
                    top_v = df[col].value_counts().head(5).to_string()
                    summary.append(f"- {col} (Top 5 of {len(uniques)} unique values):\n{top_v}")
    
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

def get_display_df() -> pd.DataFrame | None:
    """Retrieve the standalone table (display_df) for chat rendering, if any.
    
    Used for one-off tables like pivot tables that should be shown in the chat
    but not replace the main dataset.
    """
    result = getattr(_local, "display_df", None)
    _local.display_df = None  # clear after retrieval
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

def _human_format(val: float, fixed_max: float = None) -> str:
    """Core logic to format numbers into a human-readable string (K, M, B).
    
    - If fixed_max is provided: uses a consistent unit based on that maximum (good for axes).
    - If fixed_max is None: scales each value independently to its best fit (good for labels).
    """
    if val is None:
        return ""
    if val == 0:
        return "0"
        
    abs_val = abs(val)
    # Determine unit scale based on the provided max or the individual value
    target_max = abs(fixed_max) if fixed_max is not None else abs_val
    
    if target_max >= 1_000_000_000:
        unit, div = "B", 1_000_000_000
    elif target_max >= 1_000_000:
        unit, div = "M", 1_000_000
    elif target_max >= 1_000:
        unit, div = "K", 1_000
    else:
        unit, div = "", 1

    sign = "-" if val < 0 else ""
    scaled = abs_val / div
    
    if div == 1:
        return f"{val:.3g}" if abs_val < 100 else f"{sign}{abs_val:.0f}"
    
    # Use more precision for small ranges (e.g. 1.25M vs 125M) to avoid duplicates
    fmt = ".2f" if scaled < 10 else ".1f"
    clean_val = f"{scaled:{fmt}}".rstrip('0').rstrip('.')
    return f"{sign}{clean_val}{unit}"

def _get_human_formatter(max_val: float = None):
    """Factory for a Matplotlib formatter using the unified human_format logic."""
    return mticker.FuncFormatter(lambda v, p: _human_format(v, fixed_max=max_val))

def _percent_format(val, pos=None):
    """Format decimal values (0.0 to 1.0) as percentages (0% to 100%)."""
    return f"{val * 100:.1f}%".replace(".0%", "%")

@error_guardrail(context="Visualization")
def create_visualization(chart_type: str, x_column: str, y_column: str = None, y2_column: str = None, hue: str = None, size: str = None, estimator: str = "mean", title: str = None, subtitle: str = None, sort_order: str = "ascending", show_trend: bool = False, v_line: float = None, h_line: float = None) -> str:
    """Create a Seaborn or Matplotlib visualization from the dataset.
    
    Args:
        chart_type: The type of chart ('bar', 'line', 'scatter', 'hist', 'box', 'violin', 'heatmap', 'pie', 'stacked_area', 'slope').
        x_column: The name of the column for the X-axis.
        y_column: The name of the column for the Y-axis (optional for some charts).
        y2_column: The name of the column for the secondary Y-axis (optional, used for dual-axis line charts).
        hue: The name of the column to group by color (optional).
        size: The name of the column to control marker size (used for Bubble Charts).
        estimator: Statistical function to use for aggregation ('mean', 'sum', 'count', 'min', 'max', 'std'). Defaults to 'mean'.
        title: The title of the chart (e.g. "Revenue by Region").
        subtitle: A descriptive label shown below the title (e.g. "Comparison of total units sold by model type").
        sort_order: How to sort categorical bars — 'ascending' (default), 'descending', or 'none' (dataset order).
        show_trend: If True, adds a regression/trend line to scatter or line plots.
        v_line: Optional X-value to draw a vertical reference line (useful for Quadrant Analysis).
        h_line: Optional Y-value to draw a horizontal reference line (useful for Quadrant Analysis).
        
    Returns:
        A success message indicating the chart was created.
    """
    df = _get_df()
    if df is None:
        return "Error: No dataset loaded."

    # ── High-Cardinality Guardrail (Readability) ─────────────────────────
    # For Bar/Box plots, if more than 20 categories exist, truncate to Top 15
    # to prevent "Spaghetti Charts" and overlapping X-labels.
    if chart_type in ('bar', 'box', 'violin'):
        is_horizontal = (y_column is not None and pd.api.types.is_numeric_dtype(df[x_column]) and not pd.api.types.is_numeric_dtype(df[y_column]))
        cat_col = y_column if is_horizontal else x_column
        num_col = x_column if is_horizontal else y_column
        
        if cat_col in df.columns:
            unique_cats = df[cat_col].nunique()
            if unique_cats > 20:
                print(f"⚠️ READABILITY GUARD: {unique_cats} categories detected. Truncating to Top 15 for clarity.")
                top_15 = df.groupby(cat_col)[num_col].agg(estimator).sort_values(ascending=False).head(15).index
                df = df[df[cat_col].isin(top_15)]
                if not subtitle:
                    subtitle = f"Showing Top 15 {cat_col} by {estimator} {num_col}"

    # ── Aggregation Guard (Performance) ───────────────────────────────
    if len(df) > 10_000:
        if chart_type == 'scatter':
            df = df.sample(n=5_000, random_state=42)
            print(f"⚠️ AGGREGATION GUARD: Dataset too large ({len(_get_df())} rows). Scatter plot sampled to 5,000 points for readability.")
        elif chart_type == 'line' and not hue:
            if df[x_column].nunique() > 1000:
                df = df.sample(n=5_000, random_state=42).sort_values(x_column)
                print(f"⚠️ AGGREGATION GUARD: Line chart input too large and high-cardinality. Sampled to 5,000 points.")

    _apply_branding()
    sns.set_theme(style="white", font_scale=1.05)
    
    fig, ax = plt.subplots(figsize=(11, 6.5))
    _apply_branding(fig, ax)
    
    # ── Zero-Data Guardrail (UX) ─────────────────────────────────────────
    try:
        if df.empty:
            _draw_empty_placeholder(ax, f"No data found for the selected {x_column}")
            if not title: title = "No Results Match Your Search"
        else:
            # Prevent Seaborn warning: "Passing palette without assigning hue is deprecated"
            # Show legend if hue is provided, or for bubble charts (size provided in scatter)
            use_legend = bool(hue) or (chart_type == 'scatter' and bool(size))
            plot_hue = hue
            ax2 = None
            
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
                        agg_func = estimator if estimator in ("sum", "min", "max", "std", "count") else "mean"
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
                
                if show_trend:
                    if pd.api.types.is_numeric_dtype(df[x_column]):
                        sns.regplot(data=df, x=x_column, y=y_column, scatter=False, ax=ax, color=ACCENT, line_kws={"linestyle": "--", "alpha": 0.6})
                    elif pd.api.types.is_datetime64_any_dtype(df[x_column]):
                        # For datetime X, convert to matplotlib numeric dates to align with axis units
                        import matplotlib.dates as mdates
                        df_temp = df.copy()
                        df_temp['x_num_tmp'] = mdates.date2num(df_temp[x_column])
                        sns.regplot(data=df_temp, x='x_num_tmp', y=y_column, scatter=False, ax=ax, color=ACCENT, line_kws={"linestyle": "--", "alpha": 0.6})
                    else:
                        # For categorical X (like brand), map to ordinal numeric indices for regression
                        x_idx = sorted(df[x_column].unique())
                        x_map = {val: i for i, val in enumerate(x_idx)}
                        df_temp = df.copy()
                        df_temp['x_idx_tmp'] = df_temp[x_column].map(x_map)
                        sns.regplot(data=df_temp, x='x_idx_tmp', y=y_column, scatter=False, ax=ax, color=ACCENT, line_kws={"linestyle": "--", "alpha": 0.6})
        
                if y2_column:
                    ax.set_ylabel(_format_label(y_column), fontweight="bold", labelpad=10, color=HIGHLIGHT)
                    ax.tick_params(axis='y', colors=HIGHLIGHT)
                    ax2 = ax.twinx()
                    sns.lineplot(data=df, x=x_column, y=y2_column, color=ACCENT, ax=ax2, linewidth=2.5, marker="^", markersize=6, estimator=estimator, errorbar=None)
                    ax2.set_ylabel(_format_label(y2_column), fontweight="bold", labelpad=10, color=ACCENT)
                    ax2.tick_params(axis='y', colors=ACCENT)
                    ax2.yaxis.grid(False)
            elif chart_type == 'scatter':
                scatter_size = size if size in df.columns else None
        
                # When hue is a numeric column, Seaborn renders a colorbar instead of a
                # discrete legend — ax.get_legend_handles_labels() comes back empty and
                # the figure-level legend is never built. Fix: bin the values into 4
                # quantile labels so Seaborn treats it as categorical and produces a
                # proper legend with a formatted title.
                scatter_df = df.copy()
                if plot_hue and plot_hue in scatter_df.columns and pd.api.types.is_numeric_dtype(scatter_df[plot_hue]):
                    try:
                        scatter_df[plot_hue] = pd.qcut(
                            scatter_df[plot_hue],
                            q=4,
                            labels=["Low", "Mid-Low", "Mid-High", "High"],
                            duplicates="drop",
                        ).astype(str)
                        # Re-compute palette for 4 bins
                        palette = PALETTE[:4]
                    except Exception:
                        pass  # Fall back to original numeric hue if binning fails
        
                sns.scatterplot(
                    data=scatter_df,
                    x=x_column, y=y_column,
                    hue=plot_hue, size=scatter_size,
                    sizes=(40, 400), palette=palette,
                    ax=ax, alpha=0.8,
                    edgecolor="white", linewidth=0.5,
                    legend='auto' if use_legend else False,
                )
                if show_trend:
                    sns.regplot(data=df, x=x_column, y=y_column, scatter=False, ax=ax, color=ACCENT, line_kws={"alpha": 0.6})
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
                # Pivot heatmap requires 3 dimensions: Index (x), Columns (hue), and Metric (y)
                if x_column and (hue or y_column):
                    # Map arguments to pivot dimensions:
                    # If hue is missing, but y_column is categorical, it might be the hue!
                    # We need a numeric column for values.
                    idx = x_column
                    cols = hue if hue and hue in df.columns else (y_column if y_column in df.columns and not pd.api.types.is_numeric_dtype(df[y_column]) else None)
                    vals = y_column if y_column in df.columns and pd.api.types.is_numeric_dtype(df[y_column]) else (hue if hue and pd.api.types.is_numeric_dtype(df[hue]) else None)
                    
                    # If we still lack a metric or columns, try to find one numeric column automatically
                    if not vals:
                        numeric_cols = df.select_dtypes(include='number').columns
                        if len(numeric_cols) > 0:
                            vals = numeric_cols[0]
                    
                    if idx and cols and vals:
                        pivot_df = df.pivot_table(index=idx, columns=cols, values=vals, aggfunc=estimator)
                        # Auto-sort by the across-columns average to highlight the "Sweet Spot"
                        pivot_df = pivot_df.reindex(pivot_df.mean(axis=1).sort_values(ascending=sort_order != "descending").index)
                        sns.heatmap(pivot_df, annot=True, fmt=".0f" if estimator == "sum" else ".1f", cmap="YlGnBu", ax=ax, linewidths=0.5, cbar_kws={"shrink": 0.8, "label": _format_label(str(vals))})
                    else:
                        return f"Error: Heatmap requires an index (x_column), columns (hue/y_column), and a numeric metric (y_column). Found: x={idx}, cols={cols}, values={vals}."
                else:
                    # Default correlation heatmap
                    numeric_df = df.select_dtypes(include='number')
                    sns.heatmap(numeric_df.corr(), annot=True, fmt=".2f", cmap="RdYlBu_r", ax=ax, linewidths=0.5, square=True, cbar_kws={"shrink": 0.8, "label": "Pearson Correlation Coefficient"})
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
                _apply_branding(ax=ax)
                # Clean up label formatting
                ax.set_xlabel(_format_label(x_column), fontweight="medium", labelpad=10)
                ax.set_ylabel(_format_label(y_column) if y_column else "", fontweight="medium", labelpad=10)
                
                # Draw reference lines (Quadrant Analysis)
                if v_line is not None:
                    ax.axvline(v_line, color=ACCENT, linestyle="--", linewidth=1.5, alpha=0.8)
                if h_line is not None:
                    ax.axhline(h_line, color=ACCENT, linestyle="--", linewidth=1.5, alpha=0.8)
        
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
                        max_x = df[x_column].max()
                        ax.xaxis.set_major_formatter(_get_human_formatter(max_x))
                
                if y_column:
                    if pd.api.types.is_numeric_dtype(df[y_column]):
                        if _is_year_column(y_column):
                            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}"))
                        elif _is_month_column(y_column):
                            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_month_name))
                        elif _is_percent_column(y_column):
                            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_percent_format))
                        else:
                            max_y = df[y_column].max()
                            ax.yaxis.set_major_formatter(_get_human_formatter(max_y))
                else:
                    # E.g. histograms where y-axis is the count/density
                    ax.yaxis.set_major_formatter(_get_human_formatter())
                    
                if ax2 is not None and y2_column:
                    if pd.api.types.is_numeric_dtype(df[y2_column]):
                        if _is_year_column(y2_column):
                            ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}"))
                        elif _is_month_column(y2_column):
                            ax2.yaxis.set_major_formatter(mticker.FuncFormatter(_month_name))
                        elif _is_percent_column(y2_column):
                            ax2.yaxis.set_major_formatter(mticker.FuncFormatter(_percent_format))
                        else:
                            ax2.yaxis.set_major_formatter(_get_human_formatter())
                            
                # Auto-rotate x labels if they are long or numerous
                ticks = ax.get_xticklabels()
                max_label_len = max([len(t.get_text()) for t in ticks]) if ticks else 0
                if len(ticks) > 5 or max_label_len > 8:
                    plt.setp(ax.get_xticklabels(), rotation=35, ha="right", fontsize=9)
        
            # ── Legend Styling (AFTER axes are finalized) ────────────────────
            # Check if any legend handles were actually created by the plot calls
            handles, labels = ax.get_legend_handles_labels()
            has_legend_data = len(handles) > 0
            if has_legend_data and use_legend:
                fig.set_figwidth(14)  # Wider figure for side legend
                try:
                    legend_title = ""
                    if hue and size and hue != size:
                        legend_title = f"{_format_label(hue)}\n{_format_label(size)} (Size)"
                    elif hue:
                        legend_title = _format_label(hue)
                    elif size:
                        legend_title = f"Size: {_format_label(size)}"
        
                    # Create a figure-level legend to guarantee it's outside and never clipped
                    # Extract handles from the main axes
                    handles, labels = ax.get_legend_handles_labels()
                    if handles:
                        fig.legend(handles, labels, loc='center left', bbox_to_anchor=(0.82, 0.5), title=legend_title, frameon=True, fontsize=9)
                        # Remove the axis-level legend to avoid double-legend
                        if ax.get_legend(): ax.get_legend().remove()
                except:
                    pass
            
            # tight_layout first, then subplots_adjust to override it for the legend
            fig.tight_layout(rect=[0, 0, 0.8, 0.95] if (has_legend_data and use_legend) else [0, 0, 1, 0.95])
            
            if has_legend_data and use_legend:
                # Further guarantee the right margin is open
                fig.subplots_adjust(right=0.8)
            
            # Disable scientific notation multiplier (e.g. 1e6) on axes
            if hasattr(ax.xaxis.get_major_formatter(), 'set_useOffset'):
                ax.xaxis.get_major_formatter().set_useOffset(False)
            if hasattr(ax.yaxis.get_major_formatter(), 'set_useOffset'):
                ax.yaxis.get_major_formatter().set_useOffset(False)
            
            # ── Title + Subtitle Formatting (AFTER tight_layout) ─────────
            has_header = title or subtitle
            if has_header:
                # Adjust top margin if legend isn't already pushing a massive margin
                top_margin = 0.85 if (title and subtitle) else 0.88
                fig.subplots_adjust(top=top_margin)
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

@error_guardrail(context="Logic")
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
    
    # If the code produced a DataFrame (viz_df, final_df, or display_df), capture it.
    # viz_df → Visual Analyst's temp scoped variable (never persisted to session).
    # final_df → Cleaning Agent's persistent variable (persisted to session).
    # display_df → Standalone table for chat rendering (not persisted to session df).
    if result.dataframe is not None:
        # Infer which agent produced this: if the code contains 'viz_df', treat as temp.
        # Otherwise store as final_df (Cleaning Agent behaviour).
        if "viz_df" in code:
            _local.viz_temp_df = result.dataframe
        else:
            _local.final_df = result.dataframe
    
    if result.display_df is not None:
        _local.display_df = result.display_df
        
    output = result.output if result.output else "Code executed successfully."
    return output

@error_guardrail(context="Table")
def create_table(table_code: str, title: str = None, subtitle: str = None) -> str:
    """Generate an interactive, copyable table using Python code.
    The code should result in a pandas DataFrame assigned to a variable named `display_df`.
    
    Args:
        table_code: Python code to generate the table. Must assign the result to `display_df`.
        title: The title of the table (e.g. "Monthly Sales Performance").
        subtitle: A descriptive label shown below the title.
    """
    from models.sandbox import safe_execute
    
    df = _get_df()
    if df is None:
        return "Error: No dataset loaded."
        
    # Ensure the code assigns to display_df for the sandbox to capture it correctly
    if "display_df =" not in table_code:
        table_code = f"display_df = {table_code}"
        
    result = safe_execute(table_code, df)
    
    if result.blocked:
        return f"Table creation blocked: {result.blocked_reason}"
    if result.error:
        return f"Error creating table: {result.error}"
        
    if result.display_df is not None:
        _local.display_df = result.display_df
        return f"Table '{title or 'Data Summary'}' created successfully."
        
    return "Error: The code did not produce a valid table."

def calculate_weighted_metric(metric_col: str, weight_col: str, label: str = None) -> str:
    """Helper to calculate weighted metrics (e.g. revenue split by share).
    Usage: `viz_df = calculate_weighted_metric('Revenue_EUR', 'BEV_Share', 'Electric Revenue')`
    
    This creates a new dataframe with the weighted metric applied as the primary Y-axis value.
    """
    df = _get_df()
    if df is None:
        return "Error: No dataset loaded."
    
    col_name = label if label else f"{metric_col} (Weighted)"
    
    # Calculate the weighted value and store it in a temp scoped df
    viz_df = df.copy()
    viz_df[col_name] = viz_df[metric_col] * viz_df[weight_col]
    
    _local.viz_temp_df = viz_df
    return f"Weighted metric '{col_name}' calculated. You can now use this column for visualization."

@error_guardrail(context="Statistics")
def calculate_statistical_metric(column: str, group_by: str = None, metric_type: str = "z-score") -> str:
    """Perform advanced statistical derivations on a numeric column.
    
    Args:
        column: The numeric column to analyze.
        group_by: Optional column to group by before calculating (e.g. 'brand').
        metric_type: The type of statistic to calculate ('z-score', 'percentile_rank', 'pct_change').
    
    Returns:
        A success message indicating the new column was added to a temporary dataframe.
    """
    df = _get_df()
    if df is None:
        return "Error: No dataset loaded."
    
    if column not in df.columns:
        return f"Error: Column '{column}' not found."
    
    viz_df = df.copy()
    new_col_name = f"{column}_{metric_type}"
    
    try:
        if metric_type == "z-score":
            if group_by:
                means = viz_df.groupby(group_by)[column].transform('mean')
                stds = viz_df.groupby(group_by)[column].transform('std')
                viz_df[new_col_name] = (viz_df[column] - means) / stds
            else:
                mean = viz_df[column].mean()
                std = viz_df[column].std()
                viz_df[new_col_name] = (viz_df[column] - mean) / std
        elif metric_type == "percentile_rank":
            if group_by:
                viz_df[new_col_name] = viz_df.groupby(group_by)[column].rank(pct=True)
            else:
                viz_df[new_col_name] = viz_df[column].rank(pct=True)
        elif metric_type == "pct_change":
            if group_by:
                viz_df[new_col_name] = viz_df.groupby(group_by)[column].pct_change()
            else:
                viz_df[new_col_name] = viz_df[column].pct_change()
        else:
            return f"Error: Unsupported metric_type '{metric_type}'."
            
        _local.viz_temp_df = viz_df
        return f"Metric '{new_col_name}' calculated and added to the temporary view. You can now use this column for visualization."
    except Exception as e:
        return f"Error calculating statistic: {str(e)}"

viz_tool = FunctionTool(func=create_visualization)
summary_tool = FunctionTool(func=get_data_summary)
table_tool = FunctionTool(func=create_table)
fallback_tool = FunctionTool(func=execute_python_code_fallback)
weighted_tool = FunctionTool(func=calculate_weighted_metric)
stats_tool = FunctionTool(func=calculate_statistical_metric)

TOOLS = [viz_tool, summary_tool, table_tool, fallback_tool, weighted_tool, stats_tool]
