# CDW_MedCP Design Document

**Date:** 2026-02-20
**Status:** Approved

## Overview

CDW_MedCP is an MCP server that connects Claude Desktop and Claude Code to a de-identified Epic Caboodle Clinical Data Warehouse (CDW) via SQL Server. It provides read-only tools for schema discovery, clinical queries, notes investigation, data export, concept mapping, and data summarization. No knowledge graph component.

**Target users:** Clinical researchers who may not know SQL.

## Architecture: Modular Tool Registry

Tools are organized into separate modules by domain. A thin `server.py` imports and registers them all on a shared FastMCP instance.

```
CDW_medCP/
├── CLAUDE.md
├── .env.example
├── .python-version                  # 3.13
├── pyproject.toml                   # package: cdw-medcp
├── manifest.json                    # MCPB extension manifest
├── .mcpbignore
├── server/
│   └── main.py                      # MCPB entry point (imports from src package)
├── data/
│   └── schema_reference.json        # Parsed from deid_uf_data_dictionary.xlsx
└── src/
    └── cdw_medcp/
        ├── __init__.py
        ├── __main__.py              # python -m cdw_medcp
        ├── cli.py                   # CLI entry point, reads env vars
        ├── server.py                # Creates FastMCP, registers all tool modules
        ├── config.py                # Pydantic config models
        ├── db.py                    # Database connection management (pymssql)
        ├── validation.py            # SQL read-only validation (identical to MedCP)
        └── tools/
            ├── __init__.py
            ├── schema.py            # Schema discovery (tiered access)
            ├── queries.py           # SQL execution + canned clinical queries
            ├── notes.py             # Clinical notes search and retrieval
            ├── export.py            # CSV extraction (user specifies output path)
            ├── concepts.py          # Vocabulary mapping, concept relationships
            └── stats.py             # Data summarization and cohort statistics
```

## Schema Access Strategy

The data dictionary (~115 tables, ~5,000 columns, ~320K tokens) is too large for a single context dump. We parse `deid_uf_data_dictionary.xlsx` into a structured `schema_reference.json` and serve it via tiered tools:

- `get_database_overview()` — table names + business descriptions (~115 rows, fits in context)
- `describe_table(table_name)` — all columns, types, descriptions, FKs for one table
- `search_schema(keyword)` — full-text search across table/column names and descriptions

## MCP Tools

### Schema Discovery (`tools/schema.py`)

| Tool | Description |
|---|---|
| `get_database_overview()` | All table names + business descriptions from bundled reference |
| `describe_table(table_name)` | Columns, types, descriptions, FKs for one table |
| `search_schema(keyword)` | Search table/column names and descriptions by keyword |

### SQL Execution (`tools/queries.py`)

| Tool | Description |
|---|---|
| `query(sql)` | Execute read-only SQL, return results (row limit, default 1000) |
| `get_patient_demographics(patient_key)` | Canned: demographics from PatientDim |
| `get_encounters(patient_key)` | Canned: encounter history |
| `get_medications(patient_key)` | Canned: medication records |
| `get_diagnoses(patient_key)` | Canned: diagnosis history |
| `get_labs(patient_key)` | Canned: lab results |

### Clinical Notes (`tools/notes.py`)

| Tool | Description |
|---|---|
| `search_notes(patient_key, keyword)` | Search note text for a patient |
| `get_note(note_id)` | Retrieve full text of a specific note |

### Data Export (`tools/export.py`)

| Tool | Description |
|---|---|
| `export_query_to_csv(sql, filepath)` | Execute query and save to user-specified CSV path |

### Concept Mapping (`tools/concepts.py`)

| Tool | Description |
|---|---|
| `map_to_standard(code, source_vocab)` | Map local code to standard vocabulary (ICD-10, SNOMED, LOINC, RxNorm) |
| `find_related_concepts(concept, relationship_type)` | Discover concept relationships within the CDW |

### Data Summarization (`tools/stats.py`)

| Tool | Description |
|---|---|
| `summarize_table(table_name)` | Row counts, null rates, value distributions |
| `cohort_summary(sql_filter)` | Aggregate demographics/stats for a filtered cohort |

## Configuration

Environment variables (identical pattern to MedCP):

```
CLINICAL_RECORDS_SERVER=        # SQL Server host
CLINICAL_RECORDS_DATABASE=      # Database name
CLINICAL_RECORDS_USERNAME=      # SQL Server username
CLINICAL_RECORDS_PASSWORD=      # SQL Server password
CDW_NAMESPACE=CDW               # Tool name prefix (default: "CDW")
LOG_LEVEL=INFO
```

## Security

Identical to MedCP:
- Regex-based SQL validation: only `SELECT`, `WITH`, `DECLARE` allowed
- Semicolon blocking to prevent injection
- `_is_write_query()` blocks all write operations
- All tools annotated `readOnlyHint=True, destructiveHint=False`
- Credentials marked `sensitive: true` in `manifest.json` for OS keychain storage

## Database Connection

Identical to MedCP:
- Per-query `pymssql` connections
- Pydantic config model from environment variables

## Deployment

### MCPB Extension (Claude Desktop)
- `manifest.json` defines user_config for credentials
- `server/main.py` entry point using bundled `.python/` runtime
- `.mcpbignore` excludes dev files from bundle
- `schema_reference.json` bundled alongside server

### pip/uvx Package (Claude Code)
- `cdw-medcp` CLI command
- Reads env vars
- stdio transport

### MCP Prompts
- `clinical_data_exploration` — guided CDW schema exploration and querying
- `cohort_building` — step-by-step cohort identification workflow
- `notes_analysis` — guided clinical notes investigation

## Namespace

All tools prefixed with `CDW-` (e.g., `CDW-get_database_overview`, `CDW-query`, etc.).
