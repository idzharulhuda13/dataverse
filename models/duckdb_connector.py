"""
DuckDB Warehouse Connector for DataVerse Enterprise Mode.

Provides access to the pre-built dbt data marts stored in
dbt/dataverse/dataverse_warehouse.duckdb.
"""
from pathlib import Path

import duckdb
import pandas as pd

# ── Warehouse location ─────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
WAREHOUSE_PATH = _PROJECT_ROOT / "dbt" / "dataverse" / "dataverse_warehouse.duckdb"

# ── Table Registry ─────────────────────────────────────────────────────────────
# Manually maintained for now. Future: auto-scan from dbt manifest.json
TABLE_REGISTRY: dict[str, dict] = {
    "mrt_sales": {
        "display_name": "Chocolate Sales — Latest 6 Months",
        "description": "Transactional data filtered at the source model (dbt) to only include the last 6 months of data (~250k rows).",
        "schema": "main_chocolate_sales_mrt",
        "icon": "🛒",
        "grain": "One row per order",
        "approx_rows": "250,000",
        "columns": 44,
        "tags": ["sales", "transactions", "OBT", "filtered"],
    },
    "mrt_customer_summary": {
        "display_name": "Customer Summary",
        "description": "Lifetime value and purchase behaviour aggregated per customer. Segmented by age, gender, and loyalty.",
        "schema": "main_chocolate_sales_mrt",
        "icon": "👤",
        "grain": "One row per customer",
        "approx_rows": "50,000",
        "columns": 21,
        "tags": ["customers", "LTV", "segmentation"],
    },
    "mrt_product_performance": {
        "display_name": "Product Performance",
        "description": "Sales KPIs per product SKU — revenue, margin, discount rate, and unique customer reach.",
        "schema": "main_chocolate_sales_mrt",
        "icon": "🍫",
        "grain": "One row per product",
        "approx_rows": "202",
        "columns": 20,
        "tags": ["products", "SKU", "margin"],
    },
    "mrt_store_performance": {
        "display_name": "Store Performance",
        "description": "Regional and store-level KPIs — revenue, profit margin, loyalty penetration, and customer counts.",
        "schema": "main_chocolate_sales_mrt",
        "icon": "🏪",
        "grain": "One row per store",
        "approx_rows": "100",
        "columns": 20,
        "tags": ["stores", "regional", "retail"],
    },
    "mrt_daily_sales": {
        "display_name": "Daily Sales Trend",
        "description": "Time-series at daily grain covering 2023–2024. Ideal for trend analysis and forecasting.",
        "schema": "main_chocolate_sales_mrt",
        "icon": "📈",
        "grain": "One row per calendar day",
        "approx_rows": "731",
        "columns": 20,
        "tags": ["time-series", "trends", "forecasting"],
    },
}


def list_tables() -> list[dict]:
    """Return all registered tables as a list, with table_id included."""
    return [{"table_id": k, **v} for k, v in TABLE_REGISTRY.items()]


def load_table(table_id: str) -> pd.DataFrame:
    """Load a registered table from the DuckDB warehouse into a DataFrame.

    Args:
        table_id: Key from TABLE_REGISTRY (e.g. 'mrt_sales').

    Returns:
        Full table as a pandas DataFrame.

    Raises:
        ValueError: If table_id is not registered.
        FileNotFoundError: If the warehouse file is missing.
    """
    if table_id not in TABLE_REGISTRY:
        raise ValueError(
            f"Unknown table_id '{table_id}'. Available: {list(TABLE_REGISTRY.keys())}"
        )
    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {WAREHOUSE_PATH}. "
            "Run `dbt run --profiles-dir .` inside dbt/dataverse/ to build it."
        )

    meta = TABLE_REGISTRY[table_id]
    schema = meta["schema"]

    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        df = con.execute(f"SELECT * FROM {schema}.{table_id}").df()
    finally:
        con.close()

    return df
