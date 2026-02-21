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

### Key Tables (from schema reference)

- **PatientDim** — patient demographics (key: `PatientKey`)
- **EncounterFact** — encounters (keys: `PatientKey`, `EncounterKey`, order by `DateKey`)
- **MedicationOrderFact** — medication orders (order by `OrderedDateKey`)
- **DiagnosisEventFact** — diagnoses (order by `StartDateKey`)
- **LabComponentResultFact** — lab results (order by `ResultDateKey`)
- **note_metadata** / **note_text** — clinical notes (join on `deid_note_key`, patient via `PatientDurableKey`)
- **DiagnosisTerminologyDim**, **MedicationCodeDim**, **ProcedureTerminologyDim** — vocabulary/code lookups
