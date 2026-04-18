"""
Base Connector Interface for DataVerse.
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
    def load_table(self, table_id: str, limit: Optional[int] = None) -> pd.DataFrame:
        """Load a specific table into a Pandas DataFrame, with optional limit."""
        pass

    @abstractmethod
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results as a DataFrame."""
        pass
