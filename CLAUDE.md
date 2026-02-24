# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CDW_MedCP** — An MCP server that connects Claude Desktop and Claude Code to a de-identified Epic Caboodle Clinical Data Warehouse via SQL Server. Based on the [MedCP template](https://github.com/BaranziniLab/MedCP) by UCSF Baranzini Lab, with modular architecture, expanded tools, and no knowledge graph. Read-only access only.

**Target users:** Clinical researchers who may not know SQL.

## Tech Stack

- **Python >=3.11** (`.python-version` pins 3.13 for local dev)
- **Package manager**: `uv`
- **Build backend**: `hatchling`
- **MCP framework**: `FastMCP` (decorator-based tool registration)
- **Config**: Pydantic models from environment variables
- **SQL Server driver**: `pymssql`
- **Transport**: stdio (Claude Desktop), also supports SSE/HTTP

## Commands

```bash
# Install dependencies
uv sync

# Run server locally (needs env vars set)
uvx --from . cdw-medcp

# Run as module
python -m cdw_medcp

# Install as package
uv pip install .
cdw-medcp

# Regenerate schema reference from xlsx
uv run python scripts/parse_data_dictionary.py
```

No test suite, linter, or CI currently configured.

## Architecture

### Modular Tool Registry

Tools are organized into separate modules by domain. `server.py` is a thin orchestrator that imports and registers them all on a shared FastMCP instance.

```
src/cdw_medcp/
├── __init__.py          # Package exports
├── __main__.py          # python -m cdw_medcp
├── cli.py               # CLI entry point, reads env vars
├── server.py            # Creates FastMCP, registers all tool modules, defines prompts
├── config.py            # Pydantic models: ClinicalDBConfig, CDWConfig
├── db.py                # Per-query pymssql connection management
├── validation.py        # SQL read-only validation (identical to MedCP)
└── tools/
    ├── schema.py        # get_database_overview, describe_table, search_schema
    ├── queries.py       # query, get_patient_demographics/encounters/medications/diagnoses/labs
    ├── notes.py         # search_notes, get_note (via note_metadata + note_text tables)
    ├── export.py        # export_query_to_csv (user specifies output path)
    ├── concepts.py      # search_diagnoses/medications/procedures_by_code
    └── stats.py         # summarize_table, cohort_summary
```

### Entry Points

1. **pip/uvx package** (`src/cdw_medcp/`): `cli.py` reads env vars → `server.main()` → `create_cdw_server(config)` → `mcp.run()`
2. **MCPB extension** (`server/main.py`): Adds `src/` to sys.path and imports from the package. No code duplication.

### Schema Reference

The data dictionary (`deid_uf_data_dictionary.xlsx`, 139 tables, ~5000 columns) is parsed into `data/schema_reference.json` by `scripts/parse_data_dictionary.py`. Schema tools read from this JSON at runtime — no DB connection needed for schema discovery.

### Security Model (Critical — identical to MedCP)

- **SQL validation**: `ClinicalQueryValidator.is_read_only_clinical_query()` enforces SELECT/WITH/DECLARE-only via regex. Blocks semicolons.
- **Write blocking**: `_is_write_query()` blocks MERGE, CREATE, INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, EXEC, etc.
- **Credentials**: Marked `sensitive: true` in `manifest.json` for OS keychain storage

### Configuration

All config via environment variables (see `.env.example`):
- `CLINICAL_RECORDS_SERVER`, `CLINICAL_RECORDS_DATABASE`, `CLINICAL_RECORDS_USERNAME`, `CLINICAL_RECORDS_PASSWORD`
- `CDW_NAMESPACE` (tool name prefix, default "CDW")
- `CDW_SCHEMA` (database schema for table qualification, default "deid_uf")
- `CDW_LOG_LEVEL`

### 17 MCP Tools (namespace-prefixed with `CDW-`)

| Module | Tools |
|---|---|
| schema.py | `get_database_overview`, `describe_table`, `search_schema` |
| queries.py | `query`, `get_patient_demographics`, `get_encounters`, `get_medications`, `get_diagnoses`, `get_labs` |
| notes.py | `search_notes`, `get_note` |
| export.py | `export_query_to_csv` |
| concepts.py | `search_diagnoses_by_code`, `search_medications_by_code`, `search_procedures_by_code` |
| stats.py | `summarize_table`, `cohort_summary` |

### Key Tables (schema-qualified with `deid_uf.`)

- **PatientDim** — patient demographics. SCD Type 2: use `IsCurrent=1`. **PatientDurableKey** is the STABLE identifier; PatientKey is a surrogate that changes when demographics update.
- **EncounterFact** — encounters (order by `DateKey`). Columns: `Type` (NOT EncounterType), DepartmentName, DepartmentSpecialty, PatientDurableKey
- **MedicationOrderFact** — medication orders. Has OrderedDateKey, StartDateKey, EndDateKey, PatientDurableKey. Use StartDateKey/EndDateKey for treatment duration.
- **DiagnosisEventFact** — diagnoses (order by `StartDateKey`). Has PatientDurableKey.
- **LabComponentResultFact** — lab results (order by `ResultDateKey`). Use `Value` (string) for results, NOT `NumericValue` (DEID'd). Has PatientDurableKey.
- **note_metadata** / **note_text** — clinical notes (join on `deid_note_key`, patient via `PatientDurableKey`). Filter by `enc_dept_specialty` for department.
- **DiagnosisTerminologyDim**, **MedicationCodeDim**, **ProcedureTerminologyDim** — vocabulary/code lookups

### Patient Identifier Pattern (CRITICAL)

- **PatientDurableKey** = stable patient ID across all SCD Type 2 versions. Use this for ALL cohort queries.
- **PatientKey** = SCD Type 2 surrogate key. Changes when demographics update. Fact tables stamp the key active at event time. Old PatientKeys have `IsCurrent=0` in PatientDim — using PatientKey to join to PatientDim with IsCurrent=1 matches only ~16% of patients.
- **Always**: `WHERE PatientDurableKey IN (SELECT PatientDurableKey FROM fact_table ...)`
- **Never**: `WHERE PatientKey IN (SELECT PatientKey FROM fact_table ...)`

### Date Handling

- Date columns (*DateKey) are YYYYMMDD integers (e.g., 20240115)
- Convert to DATE: `CONVERT(DATE, CAST(DateKey AS VARCHAR(8)), 112)`
- Filter invalid dates: `WHERE DateKey > 19000101`

### CDW Performance Patterns (Critical)

- **NEVER** join PatientDim directly to fact tables — causes timeouts (>120s)
- Use `WHERE PatientDurableKey IN (SELECT PatientDurableKey FROM ...)` subquery pattern instead (<1s)
- CTE + JOIN also times out — use nested subqueries
- SQL Server syntax: `SELECT DISTINCT TOP N` (not `SELECT TOP N DISTINCT`)
- All tables must be schema-qualified: `deid_uf.TableName`
- Database has dual schemas (`deid` and `deid_uf`); `deid_uf` has all columns and note tables
- Cross-schema joins timeout — stay within one schema
- Multi-fact queries (diagnosis + medication): use 2-step approach — first get key values via concept tools, then use hardcoded `IN (...)` lists instead of nesting subqueries across fact tables
