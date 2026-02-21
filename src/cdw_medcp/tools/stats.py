"""Data summarization and cohort statistics tools"""

import json
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


def register_stats_tools(mcp: FastMCP, namespace_prefix: str, clinical_config: ClinicalDBConfig):
    """Register data summarization tools"""

    @mcp.tool(
        name=f"{namespace_prefix}summarize_table",
        annotations=ToolAnnotations(
            title="Summarize Table",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def summarize_table(
        table_name: str = Field(..., description="Table name to summarize")
    ) -> ToolResult:
        """Get summary statistics for a table: row count, column null rates, and
        sample value distributions for key columns."""
        if not table_name.replace("_", "").replace(".", "").isalnum():
            raise ToolError("Invalid table name")

        conn = get_connection(clinical_config)
        try:
            cursor = conn.cursor()

            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            row_count = cursor.fetchone()[0]

            cursor.execute(
                f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                f"WHERE TABLE_NAME = '{table_name}' ORDER BY ORDINAL_POSITION"
            )
            columns = cursor.fetchall()

            summary = {"table_name": table_name, "row_count": row_count, "columns": []}
            for col_name, data_type in columns[:50]:
                cursor.execute(
                    f"SELECT COUNT(*) FROM [{table_name}] WHERE [{col_name}] IS NULL"
                )
                null_count = cursor.fetchone()[0]
                col_summary = {
                    "name": col_name,
                    "data_type": data_type,
                    "null_count": null_count,
                    "null_pct": round(null_count / row_count * 100, 1) if row_count > 0 else 0,
                }
                summary["columns"].append(col_summary)

            cursor.close()
        finally:
            conn.close()

        return ToolResult(content=[TextContent(type="text", text=json.dumps(summary, indent=2))])

    @mcp.tool(
        name=f"{namespace_prefix}cohort_summary",
        annotations=ToolAnnotations(
            title="Cohort Summary",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False
        )
    )
    def cohort_summary(
        sql_filter: str = Field(..., description="SQL WHERE clause to define the cohort (e.g., \"DiagnosisKey = 12345\")")
    ) -> ToolResult:
        """Get aggregate demographics and statistics for a filtered patient cohort.
        Provide a SQL WHERE clause to define the cohort. Returns patient count."""
        if not ClinicalQueryValidator.is_read_only_clinical_query(f"SELECT 1 WHERE {sql_filter}"):
            raise ToolError("Invalid filter — only read-only expressions allowed.")

        sql = (
            f"SELECT COUNT(DISTINCT p.PatientKey) AS PatientCount "
            f"FROM PatientDim p WHERE {sql_filter}"
        )

        conn = get_connection(clinical_config)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            count = cursor.fetchone()[0]
            cursor.close()
        finally:
            conn.close()

        result = {"cohort_filter": sql_filter, "patient_count": count}
        return ToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])
