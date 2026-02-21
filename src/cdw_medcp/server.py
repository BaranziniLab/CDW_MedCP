"""CDW_MedCP server — creates FastMCP and registers all tool modules"""

import logging
from typing import Literal, Optional

from fastmcp.server import FastMCP

from cdw_medcp.config import CDWConfig, ClinicalDBConfig
from cdw_medcp.tools.schema import register_schema_tools
from cdw_medcp.tools.queries import register_query_tools
from cdw_medcp.tools.notes import register_notes_tools
from cdw_medcp.tools.export import register_export_tools
from cdw_medcp.tools.concepts import register_concept_tools
from cdw_medcp.tools.stats import register_stats_tools

logger = logging.getLogger("CDW_MedCP")


def _format_namespace(namespace: str) -> str:
    """Format namespace with trailing dash if needed"""
    if namespace:
        return namespace if namespace.endswith("-") else namespace + "-"
    return ""


def create_cdw_server(config: CDWConfig) -> FastMCP:
    """Create CDW_MedCP server with all tool modules registered"""
    logging.basicConfig(level=getattr(logging, config.log_level.upper()))

    mcp = FastMCP("CDW_MedCP")
    ns = _format_namespace(config.namespace)

    # Schema tools (bundled reference, no DB connection needed)
    register_schema_tools(mcp, ns)

    # All other tools require DB connection
    db_config = config.clinical_db
    register_query_tools(mcp, ns, db_config)
    register_notes_tools(mcp, ns, db_config)
    register_export_tools(mcp, ns, db_config)
    register_concept_tools(mcp, ns, db_config)
    register_stats_tools(mcp, ns, db_config)

    # MCP Prompts
    @mcp.prompt("clinical_data_exploration")
    def clinical_data_exploration() -> str:
        """Guided workflow for exploring the CDW schema and running queries"""
        return (
            "I want to explore clinical data in the CDW. Please help me:\n"
            "1. First, show me the database overview to understand available tables\n"
            "2. Search the schema for tables related to my topic of interest\n"
            "3. Describe the relevant tables to understand their columns\n"
            "4. Write and execute queries to retrieve the data I need\n\n"
            "Start by showing me the database overview."
        )

    @mcp.prompt("cohort_building")
    def cohort_building() -> str:
        """Step-by-step cohort identification workflow"""
        return (
            "I need to build a patient cohort for research. Please help me:\n"
            "1. Identify the relevant diagnosis, procedure, or medication tables\n"
            "2. Define inclusion/exclusion criteria using available columns\n"
            "3. Query to identify the cohort and get a summary\n"
            "4. Extract demographics and clinical characteristics\n"
            "5. Export the cohort data to CSV for further analysis\n\n"
            "What condition or criteria should we use to define the cohort?"
        )

    @mcp.prompt("notes_analysis")
    def notes_analysis() -> str:
        """Guided clinical notes investigation"""
        return (
            "I want to investigate clinical notes in the CDW. Please help me:\n"
            "1. Search for notes containing specific keywords or concepts\n"
            "2. Review note metadata (type, date, provider)\n"
            "3. Read full note text for relevant findings\n"
            "4. Summarize patterns across multiple notes\n\n"
            "What patient or keyword should we start searching for?"
        )

    return mcp


def main(
    transport: Literal["stdio", "sse", "http"] = "stdio",
    clinical_records_server: Optional[str] = None,
    clinical_records_database: Optional[str] = None,
    clinical_records_username: Optional[str] = None,
    clinical_records_password: Optional[str] = None,
    namespace: str = "CDW",
    log_level: str = "INFO",
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp/",
) -> None:
    """Main entry point for the CDW_MedCP server"""
    if not all([clinical_records_server, clinical_records_database,
                clinical_records_username, clinical_records_password]):
        raise ValueError("All clinical database credentials must be provided")

    config = CDWConfig(
        clinical_db=ClinicalDBConfig(
            server=clinical_records_server,
            database=clinical_records_database,
            username=clinical_records_username,
            password=clinical_records_password,
        ),
        namespace=namespace,
        log_level=log_level,
    )

    logger.info("Starting CDW_MedCP - Clinical Data Warehouse MCP Server")
    logger.info(f"Database: {clinical_records_server}/{clinical_records_database}")

    mcp = create_cdw_server(config)
    mcp.run()


if __name__ == "__main__":
    import os
    main(
        clinical_records_server=os.getenv("CLINICAL_RECORDS_SERVER"),
        clinical_records_database=os.getenv("CLINICAL_RECORDS_DATABASE"),
        clinical_records_username=os.getenv("CLINICAL_RECORDS_USERNAME"),
        clinical_records_password=os.getenv("CLINICAL_RECORDS_PASSWORD"),
        namespace=os.getenv("CDW_NAMESPACE", "CDW"),
        log_level=os.getenv("CDW_LOG_LEVEL", "INFO"),
    )
