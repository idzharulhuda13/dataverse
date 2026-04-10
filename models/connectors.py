"""
Connector Interfaces for DataVerse Database Backends.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

import pandas as pd
from dataverse_agent.schemas import TableRegistryEntry

class BaseConnector(ABC):
    """
    Abstract Base Class for all Database Connectors.
    """

    @abstractmethod
    def list_tables(self) -> List[TableRegistryEntry]:
        """Return all registered tables for this connector."""
        pass

    @abstractmethod
    def load_table(self, table_id: str) -> pd.DataFrame:
        """Load a specific table into a Pandas DataFrame."""
        pass

    @abstractmethod
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results as a DataFrame."""
        pass

def get_active_connector() -> BaseConnector:
    """
    Factory function to retrieve the configured database connector
    based on st.session_state.
    """
    import streamlit as st
    from models.duckdb_connector import DuckDBConnector
    from models.bigquery_connector import BigQueryConnector
    
    ctype = st.session_state.get("connector_type", "duckdb")
    if ctype == "bigquery":
        return BigQueryConnector()
    return DuckDBConnector()
