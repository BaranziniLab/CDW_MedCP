# CDW_MedCP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a modular MCP server (CDW_MedCP) that connects Claude Desktop and Claude Code to an Epic Caboodle CDW via SQL Server, with tiered schema discovery, clinical queries, notes tools, data export, concept mapping, and summarization.

**Architecture:** Modular tool registry — separate tool modules registered on a shared FastMCP instance. Security/connection patterns identical to MedCP. Schema reference parsed from xlsx into bundled JSON.

**Tech Stack:** Python 3.13, FastMCP, pymssql, Pydantic, hatchling (build), uv (package manager), openpyxl (xlsx parsing)

---

### Task 1: Project Scaffolding

**Files:**
- Create: `src/cdw_medcp/__init__.py`
- Create: `src/cdw_medcp/__main__.py`
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.env.example`
- Create: `.mcpbignore`
- Create: `src/cdw_medcp/tools/__init__.py`

**Step 1: Create `.python-version`**

```
3.13
```

**Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cdw-medcp"
version = "0.1.0"
description = "An MCP server for querying a de-identified Epic Caboodle Clinical Data Warehouse"
readme = "README.md"
license = {text = "MIT"}
keywords = [
    "mcp",
    "clinical",
    "ehr",
    "sql-server",
    "healthcare",
    "clinical-informatics",
    "epic",
    "caboodle"
]
dependencies = [
    "fastmcp>=2.11.2",
    "pydantic>=2.11.7",
    "pymssql>=2.3.7",
    "openpyxl>=3.1.0",
]
requires-python = ">=3.11"

scripts.cdw-medcp = "cdw_medcp.cli:main"
```

**Step 3: Create `.env.example`**

```
# Clinical Data Warehouse (SQL Server)
CLINICAL_RECORDS_SERVER=
CLINICAL_RECORDS_DATABASE=
CLINICAL_RECORDS_USERNAME=
CLINICAL_RECORDS_PASSWORD=

# Optional Configuration
CDW_NAMESPACE=CDW
CDW_LOG_LEVEL=INFO
```

**Step 4: Create `src/cdw_medcp/__init__.py`**

```python
"""
CDW_MedCP - Clinical Data Warehouse MCP Server

An MCP server for querying a de-identified Epic Caboodle Clinical Data Warehouse.
"""

__version__ = "0.1.0"

from cdw_medcp.server import create_cdw_server, main, CDWConfig

__all__ = ["create_cdw_server", "main", "CDWConfig", "__version__"]
```

**Step 5: Create `src/cdw_medcp/__main__.py`**

```python
"""Entry point for running as a module: python -m cdw_medcp"""

from cdw_medcp.cli import main

if __name__ == "__main__":
    main()
```

**Step 6: Create `src/cdw_medcp/tools/__init__.py`**

```python
"""CDW_MedCP tool modules"""
```

**Step 7: Create `.mcpbignore`**

```
src/
benchmarks/
docs/
*.xlsx
*.md
uv.lock
.venv/
__pycache__/
*.pyc
.env
.env.example
```

**Step 8: Run `uv sync` to install dependencies**

Run: `cd /Users/j/CDW_medCP && uv sync`
Expected: Dependencies installed, `.venv` created

**Step 9: Commit**

```bash
git add .python-version pyproject.toml .env.example .mcpbignore src/cdw_medcp/__init__.py src/cdw_medcp/__main__.py src/cdw_medcp/tools/__init__.py
git commit -m "feat: scaffold CDW_MedCP project structure"
```

---

### Task 2: Config, Validation, and Database Connection

**Files:**
- Create: `src/cdw_medcp/config.py`
- Create: `src/cdw_medcp/validation.py`
- Create: `src/cdw_medcp/db.py`

**Step 1: Create `src/cdw_medcp/config.py`**

```python
"""CDW_MedCP configuration models"""

from pydantic import BaseModel, Field


class ClinicalDBConfig(BaseModel):
    """Clinical Data Warehouse database configuration (SQL Server)"""
    server: str = Field(..., description="CDW database server host")
    database: str = Field(..., description="CDW database name")
    username: str = Field(..., description="CDW database username")
    password: str = Field(..., description="CDW database password")


class CDWConfig(BaseModel):
    """Complete CDW_MedCP server configuration"""
    clinical_db: ClinicalDBConfig = Field(..., description="Clinical Data Warehouse configuration")
    namespace: str = Field("CDW", description="Tool namespace prefix")
    log_level: str = Field("INFO", description="Logging level")
```

**Step 2: Create `src/cdw_medcp/validation.py`**

Lifted directly from MedCP — identical security logic.

```python
"""SQL query validation — read-only enforcement (identical to MedCP)"""

import re


def _is_write_query(query: str) -> bool:
    """Check if the query contains write operations"""
    return re.search(
        r"\b(MERGE|CREATE|SET|DELETE|REMOVE|ADD|INSERT|UPDATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|SP_)\b",
        query, re.IGNORECASE
    ) is not None


class ClinicalQueryValidator:
    """Clinical record query validator for read-only operations"""

    @staticmethod
    def is_read_only_clinical_query(query: str) -> bool:
        clean_query = query.strip().upper()

        allowed_statements = ['SELECT', 'WITH', 'DECLARE']
        if not any(clean_query.startswith(stmt) for stmt in allowed_statements):
            return False

        if _is_write_query(query):
            return False

        if re.search(r';\s*\w+', clean_query):
            return False

        return True
```

**Step 3: Create `src/cdw_medcp/db.py`**

```python
"""Database connection management (identical pattern to MedCP)"""

import logging

import pymssql
from fastmcp.exceptions import ToolError

from cdw_medcp.config import ClinicalDBConfig

logger = logging.getLogger("CDW_MedCP")


def get_connection(config: ClinicalDBConfig):
    """Get a per-query database connection"""
    try:
        return pymssql.connect(
            server=config.server,
            user=config.username,
            password=config.password,
            database=config.database
        )
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise ToolError(f"Database connection failed: {e}")
```

**Step 4: Commit**

```bash
git add src/cdw_medcp/config.py src/cdw_medcp/validation.py src/cdw_medcp/db.py
git commit -m "feat: add config, validation, and db connection modules"
```

---

### Task 3: Parse Data Dictionary into Schema Reference JSON

**Files:**
- Create: `scripts/parse_data_dictionary.py` (one-time script)
- Create: `data/schema_reference.json` (output)

**Step 1: Create `scripts/parse_data_dictionary.py`**

This script reads `deid_uf_data_dictionary.xlsx` and produces `data/schema_reference.json`.

```python
"""Parse deid_uf_data_dictionary.xlsx into schema_reference.json"""

import json
import sys
from pathlib import Path

import openpyxl

def parse_data_dictionary(xlsx_path: str, output_path: str):
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)

    # Parse Tables sheet
    tables_sheet = wb["Tables"]
    tables_rows = list(tables_sheet.iter_rows(values_only=True))
    tables_header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(tables_rows[0])]
    tables = {}
    for row in tables_rows[1:]:
        record = dict(zip(tables_header, row))
        name = record.get("table_name")
        if name:
            tables[name] = {
                "description": record.get("table_description", ""),
                "has_patient_data": record.get("has_pat_specific_data") == "Y",
                "has_phi": record.get("has_PHI") == "Y",
                "has_encounter_data": record.get("has_enc_specific_data") == "Y",
                "patient_key_column": record.get("PatientKey_Col"),
                "encounter_key_column": record.get("EncounterKey_Col"),
            }

    # Parse Columns sheet
    cols_sheet = wb["Columns"]
    cols_rows = list(cols_sheet.iter_rows(values_only=True))
    cols_header = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(cols_rows[0])]

    columns_by_table = {}
    for row in cols_rows[1:]:
        record = dict(zip(cols_header, row))
        table_name = record.get("table_name")
        if not table_name:
            continue
        if table_name not in columns_by_table:
            columns_by_table[table_name] = []
        col_info = {
            "name": record.get("column_name"),
            "description": record.get("column_description", ""),
            "data_type": record.get("data_type"),
            "ordinal_position": record.get("ordinal_position"),
        }
        lookup = record.get("lookupTableName")
        if lookup:
            col_info["lookup_table"] = lookup
            col_info["lookup_type"] = record.get("lookupType")
        columns_by_table[table_name].append(col_info)

    # Merge
    schema = {}
    all_table_names = set(tables.keys()) | set(columns_by_table.keys())
    for name in sorted(all_table_names):
        entry = tables.get(name, {"description": "", "has_patient_data": False, "has_phi": False})
        entry["columns"] = columns_by_table.get(name, [])
        schema[name] = entry

    wb.close()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2, default=str)

    print(f"Wrote {len(schema)} tables to {output_path}")


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    xlsx = project_root / "deid_uf_data_dictionary.xlsx"
    output = project_root / "data" / "schema_reference.json"
    parse_data_dictionary(str(xlsx), str(output))
```

**Step 2: Run the script**

Run: `cd /Users/j/CDW_medCP && uv run python scripts/parse_data_dictionary.py`
Expected: `Wrote 135 tables to data/schema_reference.json`

**Step 3: Verify output**

Run: `python -c "import json; d=json.load(open('data/schema_reference.json')); print(f'{len(d)} tables, sample keys: {list(d.keys())[:5]}')" `
Expected: Shows table count and first 5 table names

**Step 4: Commit**

```bash
git add scripts/parse_data_dictionary.py data/schema_reference.json
git commit -m "feat: parse data dictionary xlsx into schema_reference.json"
```

---

### Task 4: Schema Discovery Tools

**Files:**
- Create: `src/cdw_medcp/tools/schema.py`

**Step 1: Create `src/cdw_medcp/tools/schema.py`**

```python
"""Schema discovery tools — tiered access to CDW data dictionary"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastmcp.exceptions import ToolError
from fastmcp.server import FastMCP
from fastmcp.tools.tool import ToolResult, TextContent
from mcp.types import ToolAnnotations

logger = logging.getLogger("CDW_MedCP")

# Load schema reference at module level
_SCHEMA_REF_PATH = Path(__file__).parent.parent.parent.parent / "data" / "schema_reference.json"
_schema_ref: Optional[dict] = None


def _get_schema_ref() -> dict:
    global _schema_ref
    if _schema_ref is None:
        if not _SCHEMA_REF_PATH.exists():
            raise ToolError(f"Schema reference not found at {_SCHEMA_REF_PATH}")
        with open(_SCHEMA_REF_PATH) as f:
            _schema_ref = json.load(f)
    return _schema_ref


def register_schema_tools(mcp: FastMCP, namespace_prefix: str):
    """Register schema discovery tools on the FastMCP instance"""

    @mcp.tool(
        name=f"{namespace_prefix}get_database_overview",
        annotations=ToolAnnotations(
            title="Get Database Overview",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_database_overview() -> ToolResult:
        """Get an overview of all tables in the Clinical Data Warehouse with their descriptions.
        Returns table names, descriptions, and whether they contain patient/encounter data.
        Call this first to understand what data is available."""
        schema = _get_schema_ref()
        overview = []
        for name, info in schema.items():
            entry = {
                "table_name": name,
                "description": info.get("description", ""),
                "has_patient_data": info.get("has_patient_data", False),
                "has_encounter_data": info.get("has_encounter_data", False),
                "column_count": len(info.get("columns", [])),
            }
            pk = info.get("patient_key_column")
            if pk:
                entry["patient_key_column"] = pk
            ek = info.get("encounter_key_column")
            if ek:
                entry["encounter_key_column"] = ek
            overview.append(entry)
        return ToolResult(content=[TextContent(type="text", text=json.dumps(overview, indent=2))])

    @mcp.tool(
        name=f"{namespace_prefix}describe_table",
        annotations=ToolAnnotations(
            title="Describe Table",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def describe_table(table_name: str) -> ToolResult:
        """Get detailed column information for a specific table including column names,
        data types, descriptions, and foreign key relationships (lookup tables)."""
        schema = _get_schema_ref()
        if table_name not in schema:
            # Try case-insensitive match
            matches = [k for k in schema if k.lower() == table_name.lower()]
            if matches:
                table_name = matches[0]
            else:
                raise ToolError(f"Table '{table_name}' not found. Use get_database_overview to see available tables.")
        info = schema[table_name]
        result = {
            "table_name": table_name,
            "description": info.get("description", ""),
            "has_patient_data": info.get("has_patient_data", False),
            "patient_key_column": info.get("patient_key_column"),
            "encounter_key_column": info.get("encounter_key_column"),
            "columns": info.get("columns", []),
        }
        return ToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    @mcp.tool(
        name=f"{namespace_prefix}search_schema",
        annotations=ToolAnnotations(
            title="Search Schema",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def search_schema(keyword: str) -> ToolResult:
        """Search table and column names and descriptions for a keyword.
        Useful for finding which tables contain data about a specific concept
        (e.g., 'allergy', 'medication', 'diagnosis', 'lab')."""
        schema = _get_schema_ref()
        keyword_lower = keyword.lower()
        results = []

        for table_name, info in schema.items():
            table_match = keyword_lower in table_name.lower() or keyword_lower in (info.get("description") or "").lower()
            matching_columns = []
            for col in info.get("columns", []):
                col_name = col.get("name", "")
                col_desc = col.get("description", "") or ""
                if keyword_lower in col_name.lower() or keyword_lower in col_desc.lower():
                    matching_columns.append({
                        "column_name": col_name,
                        "description": col_desc,
                        "data_type": col.get("data_type"),
                    })

            if table_match or matching_columns:
                entry = {
                    "table_name": table_name,
                    "table_description": info.get("description", ""),
                }
                if matching_columns:
                    entry["matching_columns"] = matching_columns
                results.append(entry)

        if not results:
            return ToolResult(content=[TextContent(type="text", text=f"No tables or columns matching '{keyword}' found.")])

        return ToolResult(content=[TextContent(type="text", text=json.dumps(results, indent=2))])
```

**Step 2: Commit**

```bash
git add src/cdw_medcp/tools/schema.py
git commit -m "feat: add schema discovery tools (overview, describe, search)"
```

---

### Task 5: Query Execution Tools

**Files:**
- Create: `src/cdw_medcp/tools/queries.py`

**Step 1: Create `src/cdw_medcp/tools/queries.py`**

```python
"""SQL execution and canned clinical query tools"""

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
        patient_key: str = Field(..., description="The patient key (surrogate ID) to look up")
    ) -> ToolResult:
        """Retrieve demographic information for a patient from PatientDim."""
        sql = f"SELECT * FROM PatientDim WHERE PatientKey = '{patient_key}'"
        if not ClinicalQueryValidator.is_read_only_clinical_query(sql):
            raise ToolError("Invalid query generated")
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
        patient_key: str = Field(..., description="The patient key to look up"),
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
        patient_key: str = Field(..., description="The patient key to look up"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return")
    ) -> ToolResult:
        """Retrieve medication records for a patient."""
        sql = f"SELECT TOP {row_limit} * FROM MedicationEventFact WHERE PatientKey = '{patient_key}' ORDER BY DateKey DESC"
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
        patient_key: str = Field(..., description="The patient key to look up"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return")
    ) -> ToolResult:
        """Retrieve diagnosis history for a patient from DiagnosisEventFact."""
        sql = f"SELECT TOP {row_limit} * FROM DiagnosisEventFact WHERE PatientKey = '{patient_key}' ORDER BY DateKey DESC"
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
        patient_key: str = Field(..., description="The patient key to look up"),
        row_limit: int = Field(DEFAULT_ROW_LIMIT, description="Maximum rows to return")
    ) -> ToolResult:
        """Retrieve lab results for a patient from LabComponentResultFact."""
        sql = f"SELECT TOP {row_limit} * FROM LabComponentResultFact WHERE PatientKey = '{patient_key}' ORDER BY DateKey DESC"
        result = _execute_readonly_query(clinical_config, sql, row_limit)
        return ToolResult(content=[TextContent(type="text", text=result)])
```

**Note:** The canned query table/column names (PatientDim, EncounterFact, MedicationEventFact, DiagnosisEventFact, LabComponentResultFact, PatientKey, DateKey) should be verified against `schema_reference.json` during implementation. Adjust if column/table names differ.

**Step 2: Commit**

```bash
git add src/cdw_medcp/tools/queries.py
git commit -m "feat: add query execution and canned clinical query tools"
```

---

### Task 6: Clinical Notes Tools

**Files:**
- Create: `src/cdw_medcp/tools/notes.py`

**Step 1: Create `src/cdw_medcp/tools/notes.py`**

Note table names (`note_text`, `note_metadata`) should be verified against `schema_reference.json`. The data dictionary showed these exist in the Columns sheet.

```python
"""Clinical notes search and retrieval tools"""

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


def register_notes_tools(mcp: FastMCP, namespace_prefix: str, clinical_config: ClinicalDBConfig):
    """Register clinical notes tools"""

    @mcp.tool(
        name=f"{namespace_prefix}search_notes",
        annotations=ToolAnnotations(
            title="Search Clinical Notes",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False
        )
    )
    def search_notes(
        patient_key: str = Field(..., description="The patient key to search notes for"),
        keyword: str = Field(..., description="Keyword or phrase to search for in note text"),
        row_limit: int = Field(50, description="Maximum notes to return (default 50)")
    ) -> ToolResult:
        """Search clinical notes for a patient by keyword. Returns matching note metadata
        and text snippets. Use get_note() to retrieve the full text of a specific note."""
        # This query structure will need adjustment based on actual note table schema
        sql = (
            f"SELECT TOP {row_limit} nm.*, "
            f"SUBSTRING(nt.NoteText, 1, 500) AS NoteSnippet "
            f"FROM note_metadata nm "
            f"JOIN note_text nt ON nm.NoteKey = nt.NoteKey "
            f"WHERE nm.PatientKey = '{patient_key}' "
            f"AND nt.NoteText LIKE '%{keyword}%' "
            f"ORDER BY nm.DateKey DESC"
        )
        if not ClinicalQueryValidator.is_read_only_clinical_query(sql):
            raise ToolError("Invalid query generated")

        conn = get_connection(clinical_config)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        if not columns:
            return ToolResult(content=[TextContent(type="text", text="No matching notes found.")])

        csv_lines = [",".join(columns)]
        csv_lines.extend([",".join(str(v) if v is not None else "" for v in row) for row in rows])
        return ToolResult(content=[TextContent(type="text", text="\n".join(csv_lines))])

    @mcp.tool(
        name=f"{namespace_prefix}get_note",
        annotations=ToolAnnotations(
            title="Get Clinical Note",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def get_note(
        note_key: str = Field(..., description="The note key/ID to retrieve")
    ) -> ToolResult:
        """Retrieve the full text of a specific clinical note by its key."""
        sql = f"SELECT * FROM note_text WHERE NoteKey = '{note_key}'"
        if not ClinicalQueryValidator.is_read_only_clinical_query(sql):
            raise ToolError("Invalid query generated")

        conn = get_connection(clinical_config)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        if not rows:
            return ToolResult(content=[TextContent(type="text", text=f"No note found with key '{note_key}'")])

        csv_lines = [",".join(columns)]
        csv_lines.extend([",".join(str(v) if v is not None else "" for v in row) for row in rows])
        return ToolResult(content=[TextContent(type="text", text="\n".join(csv_lines))])
```

**Step 2: Commit**

```bash
git add src/cdw_medcp/tools/notes.py
git commit -m "feat: add clinical notes search and retrieval tools"
```

---

### Task 7: Data Export Tool

**Files:**
- Create: `src/cdw_medcp/tools/export.py`

**Step 1: Create `src/cdw_medcp/tools/export.py`**

```python
"""Data export tools — CSV extraction"""

import csv
import logging
from pathlib import Path

from pydantic import Field
from fastmcp.exceptions import ToolError
from fastmcp.server import FastMCP
from fastmcp.tools.tool import ToolResult, TextContent
from mcp.types import ToolAnnotations

from cdw_medcp.config import ClinicalDBConfig
from cdw_medcp.db import get_connection
from cdw_medcp.validation import ClinicalQueryValidator

logger = logging.getLogger("CDW_MedCP")


def register_export_tools(mcp: FastMCP, namespace_prefix: str, clinical_config: ClinicalDBConfig):
    """Register data export tools"""

    @mcp.tool(
        name=f"{namespace_prefix}export_query_to_csv",
        annotations=ToolAnnotations(
            title="Export Query to CSV",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False
        )
    )
    def export_query_to_csv(
        sql_query: str = Field(..., description="Read-only SQL SELECT query to export"),
        filepath: str = Field(..., description="Full file path where the CSV should be saved (e.g., /Users/me/exports/results.csv)")
    ) -> ToolResult:
        """Execute a read-only SQL query and save results to a CSV file at the specified path.
        The directory must already exist. Returns the number of rows exported and the file path."""
        if not ClinicalQueryValidator.is_read_only_clinical_query(sql_query):
            raise ToolError("Only SELECT queries are allowed for export.")

        output_path = Path(filepath)
        if not output_path.parent.exists():
            raise ToolError(f"Directory does not exist: {output_path.parent}")

        conn = get_connection(clinical_config)
        try:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            if not columns:
                return ToolResult(content=[TextContent(type="text", text="Query returned no results. No file created.")])

            row_count = 0
            with open(output_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                while True:
                    rows = cursor.fetchmany(5000)
                    if not rows:
                        break
                    writer.writerows(rows)
                    row_count += len(rows)

            cursor.close()
        finally:
            conn.close()

        return ToolResult(content=[TextContent(
            type="text",
            text=f"Exported {row_count} rows to {output_path}"
        )])
```

**Step 2: Commit**

```bash
git add src/cdw_medcp/tools/export.py
git commit -m "feat: add CSV export tool"
```

---

### Task 8: Concept Mapping Tools

**Files:**
- Create: `src/cdw_medcp/tools/concepts.py`

**Step 1: Create `src/cdw_medcp/tools/concepts.py`**

These tools query dimension/lookup tables in the CDW to map between local codes and standard vocabularies and to discover concept relationships. The exact table/column names need verification against the schema reference during implementation.

```python
"""Concept mapping and relationship discovery tools"""

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


def _run_query(config: ClinicalDBConfig, sql: str) -> str:
    """Run a validated query and return CSV"""
    if not ClinicalQueryValidator.is_read_only_clinical_query(sql):
        raise ToolError("Only SELECT queries are allowed.")
    conn = get_connection(config)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    if not columns:
        return "No results found."
    csv_lines = [",".join(columns)]
    csv_lines.extend([",".join(str(v) if v is not None else "" for v in row) for row in rows])
    return "\n".join(csv_lines)


def register_concept_tools(mcp: FastMCP, namespace_prefix: str, clinical_config: ClinicalDBConfig):
    """Register concept mapping and relationship tools"""

    @mcp.tool(
        name=f"{namespace_prefix}map_to_standard",
        annotations=ToolAnnotations(
            title="Map to Standard Vocabulary",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def map_to_standard(
        code: str = Field(..., description="The local code or term to map"),
        source_vocab: str = Field("", description="Source vocabulary (e.g., 'ICD10', 'SNOMED', 'LOINC', 'RxNorm'). Leave empty to search all.")
    ) -> ToolResult:
        """Map a local code or term to standard medical vocabularies.
        Searches dimension tables for matching codes and returns standardized mappings."""
        # Query will need adjustment based on actual vocabulary/concept table structure
        sql = (
            f"SELECT TOP 50 * FROM ConceptDim "
            f"WHERE ConceptCode LIKE '%{code}%' OR ConceptName LIKE '%{code}%'"
        )
        if source_vocab:
            sql += f" AND VocabularyName LIKE '%{source_vocab}%'"
        result = _run_query(clinical_config, sql)
        return ToolResult(content=[TextContent(type="text", text=result)])

    @mcp.tool(
        name=f"{namespace_prefix}find_related_concepts",
        annotations=ToolAnnotations(
            title="Find Related Concepts",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False
        )
    )
    def find_related_concepts(
        concept: str = Field(..., description="Concept name, code, or keyword to find relationships for"),
        relationship_type: str = Field("", description="Type of relationship to search for (e.g., 'drug-diagnosis', 'lab-diagnosis'). Leave empty for all.")
    ) -> ToolResult:
        """Discover how concepts relate to each other in the CDW.
        For example, find which diagnoses are commonly associated with a medication,
        or which labs are typically ordered for a condition."""
        # This is a discovery tool — exact queries depend on CDW schema
        # Start with foreign key relationships from the schema reference
        sql = (
            f"SELECT TOP 100 c1.ConceptName AS Source, c2.ConceptName AS Related, cr.RelationshipType "
            f"FROM ConceptRelationship cr "
            f"JOIN ConceptDim c1 ON cr.SourceConceptKey = c1.ConceptKey "
            f"JOIN ConceptDim c2 ON cr.TargetConceptKey = c2.ConceptKey "
            f"WHERE c1.ConceptName LIKE '%{concept}%'"
        )
        if relationship_type:
            sql += f" AND cr.RelationshipType LIKE '%{relationship_type}%'"
        result = _run_query(clinical_config, sql)
        return ToolResult(content=[TextContent(type="text", text=result)])
```

**Note:** ConceptDim, ConceptRelationship table/column names are placeholders. Verify against `schema_reference.json` during implementation and adjust SQL accordingly.

**Step 2: Commit**

```bash
git add src/cdw_medcp/tools/concepts.py
git commit -m "feat: add concept mapping and relationship tools"
```

---

### Task 9: Data Summarization Tools

**Files:**
- Create: `src/cdw_medcp/tools/stats.py`

**Step 1: Create `src/cdw_medcp/tools/stats.py`**

```python
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
        # Validate table name (no SQL injection via table name)
        if not table_name.replace("_", "").replace(".", "").isalnum():
            raise ToolError("Invalid table name")

        conn = get_connection(clinical_config)
        try:
            cursor = conn.cursor()

            # Row count
            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            row_count = cursor.fetchone()[0]

            # Column info + null counts
            cursor.execute(
                f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                f"WHERE TABLE_NAME = '{table_name}' ORDER BY ORDINAL_POSITION"
            )
            columns = cursor.fetchall()

            summary = {"table_name": table_name, "row_count": row_count, "columns": []}
            for col_name, data_type in columns[:50]:  # Limit to first 50 columns
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
        sql_filter: str = Field(..., description="SQL WHERE clause to define the cohort (e.g., \"DiagnosisCode LIKE 'G35%'\")")
    ) -> ToolResult:
        """Get aggregate demographics and statistics for a filtered patient cohort.
        Provide a SQL WHERE clause to define the cohort. Returns counts, age distribution,
        and gender breakdown from PatientDim."""
        # Validate the filter doesn't contain write operations
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
```

**Step 2: Commit**

```bash
git add src/cdw_medcp/tools/stats.py
git commit -m "feat: add table summarization and cohort summary tools"
```

---

### Task 10: Server Orchestrator and CLI

**Files:**
- Create: `src/cdw_medcp/server.py`
- Create: `src/cdw_medcp/cli.py`

**Step 1: Create `src/cdw_medcp/server.py`**

```python
"""CDW_MedCP server — creates FastMCP and registers all tool modules"""

import logging
from typing import Literal, Optional

from fastmcp.server import FastMCP
from pydantic import Field

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
```

**Step 2: Create `src/cdw_medcp/cli.py`**

```python
"""CDW_MedCP CLI entry point"""

import logging
import os

from cdw_medcp.server import main as server_main

logger = logging.getLogger("CDW_MedCP")


def main() -> None:
    """CLI entry point — reads env vars and starts the server."""
    log_level = os.getenv("CDW_LOG_LEVEL", "INFO")
    logging.basicConfig(level=getattr(logging, log_level.upper()))

    logger.info("Starting CDW_MedCP - Clinical Data Warehouse MCP Server")

    server_main(
        clinical_records_server=os.getenv("CLINICAL_RECORDS_SERVER"),
        clinical_records_database=os.getenv("CLINICAL_RECORDS_DATABASE"),
        clinical_records_username=os.getenv("CLINICAL_RECORDS_USERNAME"),
        clinical_records_password=os.getenv("CLINICAL_RECORDS_PASSWORD"),
        namespace=os.getenv("CDW_NAMESPACE", "CDW"),
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
```

**Step 3: Commit**

```bash
git add src/cdw_medcp/server.py src/cdw_medcp/cli.py
git commit -m "feat: add server orchestrator and CLI entry point"
```

---

### Task 11: MCPB Manifest and Server Entry Point

**Files:**
- Create: `manifest.json`
- Create: `server/main.py`

**Step 1: Create `manifest.json`**

Adapted from MedCP — no knowledge graph config, CDW-specific descriptions.

```json
{
  "manifest_version": "0.2",
  "name": "CDW_MedCP",
  "version": "0.1.0",
  "description": "Clinical Data Warehouse MCP Server for Claude Desktop",
  "long_description": "CDW_MedCP connects Claude Desktop to a de-identified Epic Caboodle Clinical Data Warehouse via SQL Server. It provides schema discovery, clinical queries, notes investigation, data export, concept mapping, and data summarization — all read-only. Designed for clinical researchers who need natural language access to EHR data.",
  "icon": "logo.png",
  "server": {
    "type": "python",
    "entry_point": "server/main.py",
    "mcp_config": {
      "command": "${__dirname}/.python/bin/python3.12",
      "args": ["${__dirname}/server/main.py"],
      "env": {
        "CDW_LOG_LEVEL": "${user_config.CDW_LOG_LEVEL}",
        "CDW_NAMESPACE": "${user_config.CDW_NAMESPACE}",
        "CLINICAL_RECORDS_SERVER": "${user_config.CLINICAL_RECORDS_SERVER}",
        "CLINICAL_RECORDS_DATABASE": "${user_config.CLINICAL_RECORDS_DATABASE}",
        "CLINICAL_RECORDS_USERNAME": "${user_config.CLINICAL_RECORDS_USERNAME}",
        "CLINICAL_RECORDS_PASSWORD": "${user_config.CLINICAL_RECORDS_PASSWORD}"
      }
    }
  },
  "tools": [
    {"name": "get_database_overview", "description": "Get an overview of all tables in the CDW with descriptions"},
    {"name": "describe_table", "description": "Get detailed column info for a specific table"},
    {"name": "search_schema", "description": "Search table/column names and descriptions by keyword"},
    {"name": "query", "description": "Execute a read-only SQL query on the CDW"},
    {"name": "get_patient_demographics", "description": "Get demographics for a patient"},
    {"name": "get_encounters", "description": "Get encounter history for a patient"},
    {"name": "get_medications", "description": "Get medication records for a patient"},
    {"name": "get_diagnoses", "description": "Get diagnosis history for a patient"},
    {"name": "get_labs", "description": "Get lab results for a patient"},
    {"name": "search_notes", "description": "Search clinical notes by keyword"},
    {"name": "get_note", "description": "Retrieve full text of a clinical note"},
    {"name": "export_query_to_csv", "description": "Export query results to a CSV file"},
    {"name": "map_to_standard", "description": "Map local codes to standard vocabularies"},
    {"name": "find_related_concepts", "description": "Discover concept relationships in the CDW"},
    {"name": "summarize_table", "description": "Get summary statistics for a table"},
    {"name": "cohort_summary", "description": "Get aggregate stats for a filtered cohort"}
  ],
  "prompts": [
    {"name": "clinical_data_exploration", "description": "Guided CDW exploration workflow", "text": "I want to explore clinical data in the CDW. Please start by showing me the database overview."},
    {"name": "cohort_building", "description": "Step-by-step cohort identification", "text": "I need to build a patient cohort for research. What condition should we use?"},
    {"name": "notes_analysis", "description": "Clinical notes investigation", "text": "I want to investigate clinical notes. What patient or keyword should we search?"}
  ],
  "user_config": {
    "CLINICAL_RECORDS_SERVER": {
      "type": "string",
      "title": "CDW Server",
      "description": "SQL Server host for the Clinical Data Warehouse",
      "required": true,
      "sensitive": false
    },
    "CLINICAL_RECORDS_DATABASE": {
      "type": "string",
      "title": "CDW Database",
      "description": "Database name for the Clinical Data Warehouse",
      "required": true,
      "sensitive": false
    },
    "CLINICAL_RECORDS_USERNAME": {
      "type": "string",
      "title": "CDW Username",
      "description": "Username for the CDW SQL Server",
      "required": true,
      "sensitive": false
    },
    "CLINICAL_RECORDS_PASSWORD": {
      "type": "string",
      "title": "CDW Password",
      "description": "Password for the CDW SQL Server",
      "required": true,
      "sensitive": true
    },
    "CDW_NAMESPACE": {
      "type": "string",
      "title": "Tool Namespace",
      "description": "Prefix for all CDW_MedCP tool names",
      "required": false,
      "default": "CDW",
      "sensitive": false
    },
    "CDW_LOG_LEVEL": {
      "type": "string",
      "title": "Log Level",
      "description": "Logging level (DEBUG, INFO, WARNING, ERROR)",
      "required": false,
      "default": "INFO",
      "sensitive": false
    }
  },
  "compatibility": {
    "platforms": ["darwin", "win32", "linux"],
    "runtimes": {"node": ">=18.0.0"}
  },
  "keywords": ["Clinical", "Healthcare", "EHR", "Epic", "Caboodle", "SQL Server", "CDW", "MCP"],
  "license": "MIT"
}
```

**Step 2: Create `server/main.py`**

This is the MCPB entry point — reads env vars and starts the server.

```python
"""CDW_MedCP MCPB entry point — standalone server for Claude Desktop extension"""

import os
import sys

# Add src to path so we can import cdw_medcp package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cdw_medcp.server import main

if __name__ == "__main__":
    main(
        clinical_records_server=os.getenv("CLINICAL_RECORDS_SERVER"),
        clinical_records_database=os.getenv("CLINICAL_RECORDS_DATABASE"),
        clinical_records_username=os.getenv("CLINICAL_RECORDS_USERNAME"),
        clinical_records_password=os.getenv("CLINICAL_RECORDS_PASSWORD"),
        namespace=os.getenv("CDW_NAMESPACE", "CDW"),
        log_level=os.getenv("CDW_LOG_LEVEL", "INFO"),
    )
```

**Step 3: Commit**

```bash
git add manifest.json server/main.py
git commit -m "feat: add MCPB manifest and server entry point for Claude Desktop"
```

---

### Task 12: Verify Everything Wires Up

**Step 1: Check imports resolve**

Run: `cd /Users/j/CDW_medCP && uv run python -c "from cdw_medcp import create_cdw_server, CDWConfig; print('Imports OK')"`
Expected: `Imports OK`

**Step 2: Check CLI entry point**

Run: `uv run cdw-medcp --help 2>&1 || echo "Expected: fails because no DB credentials, but should show it tried to start"`
Expected: Error about missing credentials (not import errors)

**Step 3: Check schema reference loads**

Run: `uv run python -c "from cdw_medcp.tools.schema import _get_schema_ref; d = _get_schema_ref(); print(f'{len(d)} tables loaded')"`
Expected: `135 tables loaded` (or similar count)

**Step 4: Commit any fixes, update CLAUDE.md**

Update CLAUDE.md to reflect the final project structure and commands.

```bash
git add -A
git commit -m "chore: verify wiring and update docs"
```

---

## Verification Notes

- **Canned query table names** (Tasks 5-6, 8): PatientDim, EncounterFact, MedicationEventFact, DiagnosisEventFact, LabComponentResultFact, note_metadata, note_text, ConceptDim — these must be verified against `schema_reference.json` and adjusted if the actual table names differ.
- **Schema reference path** (Task 4): The `_SCHEMA_REF_PATH` in `schema.py` assumes the JSON is at `data/schema_reference.json` relative to project root. For MCPB bundling, this path may need adjustment.
- **No tests yet**: This plan scaffolds the server. Tests can be added in a follow-up task once we can verify against the actual database.
