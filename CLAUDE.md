# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CDW_MedCP** — An MCP (Model Context Protocol) server that connects Claude Desktop to an EHR (Electronic Health Records) database via SQL Server. Based on the [MedCP template](https://github.com/BaranziniLab/MedCP) by UCSF Baranzini Lab, but tailored for a different clinical data warehouse with expanded functionality. No knowledge graph component.

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

# Run server locally
uvx --from . medcp

# Run as module
python -m medcp

# Install as package
uv pip install .
medcp
```

No test suite, linter, or CI currently configured.

## Architecture

### Entry Points

Two parallel paths exist by design:

1. **pip/uvx package** (`src/medcp/`): `cli.py` reads env vars → calls `server.main()` → `create_medcp_server(config)` → `mcp.run()`
2. **MCPB extension** (`server/main.py`): Standalone copy invoked directly by Claude Desktop's bundled Python runtime. The `.mcpbignore` excludes `src/` from the bundle.

`server/main.py` and `src/medcp/server.py` are intentionally near-identical. Changes to server logic must be synchronized between both files.

### Server Pattern

```
create_medcp_server(config: MedCPConfig) -> FastMCP
  └─ Conditionally registers MCP tools based on which databases are configured
  └─ Tools are namespace-prefixed via MEDCP_NAMESPACE env var (default: "MedCP")
  └─ All tools annotated readOnlyHint=True, destructiveHint=False
```

### Security Model (Critical)

- **SQL validation**: `ClinicalQueryValidator.is_read_only_clinical_query()` enforces SELECT/WITH/DECLARE-only queries via regex. Blocks semicolons to prevent injection.
- **Write blocking**: `_is_write_query()` detects and blocks write operations (CREATE, INSERT, UPDATE, DELETE, MERGE, etc.)
- **Credentials**: Marked `sensitive: true` in `manifest.json` for OS keychain storage via Claude Desktop

### Configuration

All config via environment variables (see `.env.example`):
- `CLINICAL_RECORDS_SERVER`, `CLINICAL_RECORDS_DATABASE`, `CLINICAL_RECORDS_USERNAME`, `CLINICAL_RECORDS_PASSWORD`
- `MEDCP_NAMESPACE` (tool name prefix, default "MedCP")
- `LOG_LEVEL`

### Key Files

| File | Purpose |
|---|---|
| `src/medcp/server.py` | Core server: config models, tool registration, query validation |
| `src/medcp/cli.py` | CLI entry point, env var reading |
| `server/main.py` | Standalone server for MCPB bundle (keep in sync with server.py) |
| `manifest.json` | MCPB extension manifest with user_config schema |
| `.env.example` | Environment variable template |
| `pyproject.toml` | Package metadata, dependencies, entry point |

