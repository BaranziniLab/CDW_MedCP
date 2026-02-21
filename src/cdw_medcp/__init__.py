"""
CDW_MedCP - Clinical Data Warehouse MCP Server

An MCP server for querying a de-identified Epic Caboodle Clinical Data Warehouse.
"""

__version__ = "0.1.0"

from cdw_medcp.config import CDWConfig
from cdw_medcp.server import create_cdw_server, main

__all__ = ["create_cdw_server", "main", "CDWConfig", "__version__"]
