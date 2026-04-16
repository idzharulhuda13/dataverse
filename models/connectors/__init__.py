import streamlit as st
from models.connectors.base import BaseConnector

def get_active_connector() -> BaseConnector:
    """
    Factory function to retrieve the configured database connector
    based on st.session_state.
    """
    from models.connectors.duckdb import DuckDBConnector
    from models.connectors.bigquery import BigQueryConnector
    
    ctype = st.session_state.get("connector_type", "duckdb")
    if ctype == "bigquery":
        return BigQueryConnector()
    return DuckDBConnector()
