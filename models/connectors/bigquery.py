"""
BigQuery Warehouse Connector for DataVerse.
"""
import os
from typing import List, Optional
import pandas as pd
import numpy as np
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
from dataverse_agent.schemas import TableRegistryEntry
from models.connectors.base import BaseConnector

# ── BigQuery Table Registry ───────────────────────────────────────────────────
BQ_TABLE_REGISTRY: dict[str, TableRegistryEntry] = {
    "languages": TableRegistryEntry(
        table_id="languages",
        display_name="GitHub — Repository Languages",
        description="Programming language distribution across millions of GitHub repositories.",
        db_schema="bigquery-public-data.github_repos",
        icon="💻",
        grain="One row per repository/language",
        approx_rows="~10M",
        columns=3,
        tags=["github", "coding", "languages"],
    ),
    "sample_repos": TableRegistryEntry(
        table_id="sample_repos",
        display_name="GitHub — Sample Repositories",
        description="Metadata for a representative subset of GitHub repositories.",
        db_schema="bigquery-public-data.github_repos",
        icon="📁",
        grain="One row per repository",
        approx_rows="~400K",
        columns=5,
        tags=["github", "metadata", "repos"],
    ),
    "licenses": TableRegistryEntry(
        table_id="licenses",
        display_name="GitHub — Open Source Licenses",
        description="License identification for open source projects on GitHub.",
        db_schema="bigquery-public-data.github_repos",
        icon="⚖️",
        grain="One row per repository",
        approx_rows="~3.5M",
        columns=2,
        tags=["github", "legal", "opensource"],
    ),
}

class BigQueryConnector(BaseConnector):
    """
    Google BigQuery implementation of the Database Connector.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self) -> bigquery.Client:
        """Lazily initialize the BigQuery client."""
        if self._client is None:
            # Try to load credentials from Streamlit secrets
            bq_creds = st.secrets.get("BIGQUERY_CREDENTIALS")
            if bq_creds:
                if isinstance(bq_creds, str):
                    # Check if it's a file path
                    if bq_creds.endswith(".json") and os.path.exists(bq_creds):
                        self._client = bigquery.Client.from_service_account_json(bq_creds)
                    else:
                        # Otherwise assume it's a JSON string
                        import json
                        info = json.loads(bq_creds)
                        creds = service_account.Credentials.from_service_account_info(info)
                        self._client = bigquery.Client(credentials=creds, project=info.get("project_id"))
                else:
                    # Assume it's already a dict from secrets.toml
                    creds = service_account.Credentials.from_service_account_info(dict(bq_creds))
                    self._client = bigquery.Client(credentials=creds, project=bq_creds.get("project_id"))
            else:
                # Fallback to default credentials (gcloud auth)
                self._client = bigquery.Client()
        return self._client

    def list_tables(self) -> List[TableRegistryEntry]:
        """Return registered BigQuery tables."""
        return list(BQ_TABLE_REGISTRY.values())

    def load_table(self, table_id: str, limit: Optional[int] = None) -> pd.DataFrame:
        """
        In BigQuery mode, we return a sample for grounding.
        """
        if table_id not in BQ_TABLE_REGISTRY:
            raise ValueError(f"Unknown BQ table_id '{table_id}'")
        
        meta = BQ_TABLE_REGISTRY[table_id]
        # Using a preview for grounding
        limit_val = limit if limit is not None else 100
        query = f"SELECT * FROM `{meta.db_schema}.{table_id}` LIMIT {limit_val}"
        return self.execute_query(query)

    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query against BigQuery and dynamically flatten results."""
        try:
            query_job = self.client.query(query)
            df = query_job.to_dataframe()
            df = flatten_dataframe(df)
            return ensure_dataframe_is_arrow_compatible(df)
        except Exception as e:
            raise e

def ensure_dataframe_is_arrow_compatible(df: pd.DataFrame) -> pd.DataFrame:
    """ Ensure DataFrame is Arrow-compatible for Streamlit serialization. """
    for col in df.columns:
        # Convert objects that look like timestamps but cause Arrow conversion errors
        if df[col].dtype == "object":
            try:
                # Try to cast to datetime if it looks like one
                if df[col].astype(str).str.contains("-").any():
                    df[col] = pd.to_datetime(df[col], format='mixed', errors='coerce')
            except:
                pass
    return df

def flatten_dataframe(df: pd.DataFrame, max_depth: int = 3) -> pd.DataFrame:
    """
    Recursively flattens columns containing dictionaries or lists (BigQuery Records/Arrays).
    """
    for _ in range(max_depth):
        list_cols = []
        dict_cols = []
        
        for col in df.columns:
            # We check the first non-null value to determine the type
            first_valid_idx = df[col].first_valid_index()
            if first_valid_idx is not None:
                val = df[col].loc[first_valid_idx]
                if isinstance(val, (list, np.ndarray)):
                    list_cols.append(col)
                elif isinstance(val, dict):
                    dict_cols.append(col)
        
        if not list_cols and not dict_cols:
            break
            
        for l_col in list_cols:
            df = df.explode(l_col).reset_index(drop=True)
            
        for d_col in dict_cols:
            filled_series = df[d_col].apply(lambda x: x if isinstance(x, dict) else {})
            dict_df = pd.json_normalize(filled_series.tolist()).add_prefix(f"{d_col}_")
            df = pd.concat([df.drop(columns=[d_col]).reset_index(drop=True), dict_df], axis=1)
            
    return df
