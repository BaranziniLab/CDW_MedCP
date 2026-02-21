"""SQL execution and canned clinical query tools"""

import logging

from pydantic import Field
from fastmcp.exceptions import ToolError
from fastmcp.server import FastMCP
from fastmcp.tools.tool import ToolResult, TextContent
from mcp.types import ToolAnnotations

from cdw_medcp.config import ClinicalDBConfig
from cdw_medcp.db import get_connection
from cdw_medcp.validation import ClinicalQueryValidator

logger = logging.getLogger("CDW_MedCP")

DEFAULT_ROW_LIMIT = 1000


def _execute_readonly_query(config: ClinicalDBConfig, sql: str, row_limit: int = DEFAULT_ROW_LIMIT) -> str:
    """Execute a validated read-only query and return CSV-formatted results"""
    if not ClinicalQueryValidator.is_read_only_clinical_query(sql):
        raise ToolError("Only SELECT queries are allowed. Write operations are blocked for security.")

    conn = get_connection(config)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(row_limit)
        cursor.close()
    finally:
        conn.close()

    if not columns:
        return "Query executed successfully (no results returned)"

    csv_lines = [",".join(columns)]
    csv_lines.extend([",".join(str(v) if v is not None else "" for v in row) for row in rows])
    return "\n".join(csv_lines)


def register_query_tools(mcp: FastMCP, namespace_prefix: str, clinical_config: ClinicalDBConfig):
    """Register SQL execution and canned query tools"""

    @mcp.tool(
        name=f"{namespace_prefix}query",
        annotations=ToolAnnotations(
            title="Query Clinical Data",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def query(
        sql_query: str = Field(..., description="Read-only SQL SELECT query"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return (default 1000)")
    ) -> ToolResult:
        """Execute a READ-ONLY SQL query on the Clinical Data Warehouse.
        Only SELECT, WITH, and DECLARE statements are allowed.
        Results are returned as CSV. Use get_database_overview and describe_table first
        to understand the schema before writing queries."""
        result = _execute_readonly_query(clinical_config, sql_query, row_limit)
        return ToolResult(content=[TextContent(type="text", text=result)])

    @mcp.tool(
        name=f"{namespace_prefix}get_patient_demographics",
        annotations=ToolAnnotations(
            title="Get Patient Demographics",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_patient_demographics(
        patient_key: str = Field(..., description="The PatientKey (surrogate ID) to look up")
    ) -> ToolResult:
        """Retrieve demographic information for a patient from PatientDim."""
        sql = f"SELECT * FROM PatientDim WHERE PatientKey = '{patient_key}'"
        result = _execute_readonly_query(clinical_config, sql)
        return ToolResult(content=[TextContent(type="text", text=result)])

    @mcp.tool(
        name=f"{namespace_prefix}get_encounters",
        annotations=ToolAnnotations(
            title="Get Patient Encounters",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_encounters(
        patient_key: str = Field(..., description="The PatientKey to look up"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return")
    ) -> ToolResult:
        """Retrieve encounter history for a patient from EncounterFact."""
        sql = f"SELECT TOP {row_limit} * FROM EncounterFact WHERE PatientKey = '{patient_key}' ORDER BY DateKey DESC"
        result = _execute_readonly_query(clinical_config, sql, row_limit)
        return ToolResult(content=[TextContent(type="text", text=result)])

    @mcp.tool(
        name=f"{namespace_prefix}get_medications",
        annotations=ToolAnnotations(
            title="Get Patient Medications",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_medications(
        patient_key: str = Field(..., description="The PatientKey to look up"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return")
    ) -> ToolResult:
        """Retrieve medication order records for a patient from MedicationOrderFact."""
        sql = f"SELECT TOP {row_limit} * FROM MedicationOrderFact WHERE PatientKey = '{patient_key}' ORDER BY OrderedDateKey DESC"
        result = _execute_readonly_query(clinical_config, sql, row_limit)
        return ToolResult(content=[TextContent(type="text", text=result)])

    @mcp.tool(
        name=f"{namespace_prefix}get_diagnoses",
        annotations=ToolAnnotations(
            title="Get Patient Diagnoses",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_diagnoses(
        patient_key: str = Field(..., description="The PatientKey to look up"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return")
    ) -> ToolResult:
        """Retrieve diagnosis history for a patient from DiagnosisEventFact."""
        sql = f"SELECT TOP {row_limit} * FROM DiagnosisEventFact WHERE PatientKey = '{patient_key}' ORDER BY StartDateKey DESC"
        result = _execute_readonly_query(clinical_config, sql, row_limit)
        return ToolResult(content=[TextContent(type="text", text=result)])

    @mcp.tool(
        name=f"{namespace_prefix}get_labs",
        annotations=ToolAnnotations(
            title="Get Patient Labs",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_labs(
        patient_key: str = Field(..., description="The PatientKey to look up"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return")
    ) -> ToolResult:
        """Retrieve lab component results for a patient from LabComponentResultFact."""
        sql = f"SELECT TOP {row_limit} * FROM LabComponentResultFact WHERE PatientKey = '{patient_key}' ORDER BY ResultDateKey DESC"
        result = _execute_readonly_query(clinical_config, sql, row_limit)
        return ToolResult(content=[TextContent(type="text", text=result)])
