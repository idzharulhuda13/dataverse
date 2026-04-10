from pathlib import Path
from typing import List

import duckdb
import pandas as pd

from dataverse_agent.schemas import TableRegistryEntry
from models.connectors import BaseConnector

# ── Warehouse location ─────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
WAREHOUSE_PATH = _PROJECT_ROOT / "dbt" / "dataverse" / "dataverse_warehouse.duckdb"

# ── Table Registry ─────────────────────────────────────────────────────────────
# Manually maintained for now. Future: auto-scan from dbt manifest.json
TABLE_REGISTRY: dict[str, TableRegistryEntry] = {
    "mrt_sales": TableRegistryEntry(
        table_id="mrt_sales",
        display_name="Chocolate Sales — Transactions",
        description="Full order-level transactions with customer, product, store, and time dimensions pre-joined.",
        db_schema="main_chocolate_sales_mrt",
        icon="🛒",
        grain="One row per order",
        approx_rows="250,000",
        columns=44,
        tags=["sales", "transactions", "OBT"],
    ),
    "mrt_customer_summary": TableRegistryEntry(
        table_id="mrt_customer_summary",
        display_name="Customer Summary",
        description="Lifetime value and purchase behaviour aggregated per customer. Segmented by age, gender, and loyalty.",
        db_schema="main_chocolate_sales_mrt",
        icon="👤",
        grain="One row per customer",
        approx_rows="50,000",
        columns=21,
        tags=["customers", "LTV", "segmentation"],
    ),
    "mrt_product_performance": TableRegistryEntry(
        table_id="mrt_product_performance",
        display_name="Product Performance",
        description="Sales KPIs per product SKU — revenue, margin, discount rate, and unique customer reach.",
        db_schema="main_chocolate_sales_mrt",
        icon="🍫",
        grain="One row per product",
        approx_rows="202",
        columns=20,
        tags=["products", "SKU", "margin"],
    ),
    "mrt_store_performance": TableRegistryEntry(
        table_id="mrt_store_performance",
        display_name="Store Performance",
        description="Regional and store-level KPIs — revenue, profit margin, loyalty penetration, and customer counts.",
        db_schema="main_chocolate_sales_mrt",
        icon="🏦",
        grain="One row per store",
        approx_rows="100",
        columns=20,
        tags=["stores", "regional", "retail"],
    ),
    "mrt_daily_sales": TableRegistryEntry(
        table_id="mrt_daily_sales",
        display_name="Daily Sales Trend",
        description="Time-series at daily grain. Ideal for high-density trend analysis and forecasting.",
        db_schema="main_chocolate_sales_mrt",
        icon="📈",
        grain="One row per calendar day",
        approx_rows="185",
        columns=20,
        tags=["time-series", "trends", "forecasting"],
    ),
}

class DuckDBConnector(BaseConnector):
    """
    DuckDB implementation of the Database Connector.
    """

    def list_tables(self) -> List[TableRegistryEntry]:
        """Return all registered tables as a list of TableRegistryEntry models."""
        return list(TABLE_REGISTRY.values())

    def load_table(self, table_id: str) -> pd.DataFrame:
        """Load a registered table from the DuckDB warehouse into a DataFrame."""
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
        con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
        try:
            df = con.execute(f"SELECT * FROM {meta.db_schema}.{table_id}").df()
        finally:
            con.close()
        return df

    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query against the DuckDB warehouse."""
        if not WAREHOUSE_PATH.exists():
            raise FileNotFoundError(f"Warehouse not found at {WAREHOUSE_PATH}.")
        
        con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
        try:
            df = con.execute(query).df()
        finally:
            con.close()
        return df

# Helper instances/functions for backward compatibility if needed, 
# though we should update callers.
def list_tables() -> List[TableRegistryEntry]:
    return DuckDBConnector().list_tables()

def load_table(table_id: str) -> pd.DataFrame:
    return DuckDBConnector().load_table(table_id)
