# CDW_MedCP

An MCP (Model Context Protocol) server that connects LLMs (eg Claude Desktop or Claude Code) to a de-identified **Epic Caboodle Clinical Data Warehouse** via SQL Server.

Built for clinical researchers who need natural-language access to EHR data without writing SQL. Based on the [MedCP](https://github.com/BaranziniLab/MedCP) architecture by the UCSF Baranzini Lab, with a modular tool registry, expanded clinical tools, and no knowledge graph dependency.

## Authors

- **Gianmarco Bellucci**
- **Wanjun Gu**

## Features

- 17 MCP tools organized into 6 domain modules
- 3 guided workflow prompts for common research tasks
- Read-only SQL enforcement with comprehensive write-blocking
- Schema discovery from a pre-parsed data dictionary (no DB connection needed)
- Clinical notes search and retrieval
- Cohort building with aggregate demographics
- CSV export for large result sets
- Configurable tool namespace and database schema

## Tools

### Schema Discovery

| Tool | Description |
|------|-------------|
| `get_database_overview` | Overview of all CDW tables with descriptions, patient/encounter flags, and column counts |
| `describe_table` | Detailed column info for a specific table: names, types, descriptions, foreign keys |
| `search_schema` | Keyword search across table and column names/descriptions |

### Clinical Queries

| Tool | Description |
|------|-------------|
| `query` | Execute a read-only SQL SELECT query with security validation; results as CSV |
| `get_patient_demographics` | Demographics for a patient from PatientDim (most recent record) |
| `get_encounters` | Encounter history from EncounterFact, ordered by date |
| `get_medications` | Medication orders from MedicationOrderFact with treatment duration |
| `get_diagnoses` | Diagnosis history from DiagnosisEventFact |
| `get_labs` | Lab results from LabComponentResultFact |

### Clinical Notes

| Tool | Description |
|------|-------------|
| `search_notes` | Search clinical notes by patient and keyword; returns metadata and text snippets |
| `get_note` | Retrieve the full text of a clinical note by its key |

### Data Export

| Tool | Description |
|------|-------------|
| `export_query_to_csv` | Execute a read-only SQL query and save results to a CSV file |

### Concept Search

| Tool | Description |
|------|-------------|
| `search_diagnoses_by_code` | Search diagnoses by ICD/SNOMED code or name |
| `search_medications_by_code` | Search medications by code, brand name, or generic name |
| `search_procedures_by_code` | Search procedures by CPT/HCPCS code or name |

### Statistics

| Tool | Description |
|------|-------------|
| `summarize_table` | Summary statistics for a table: row counts, null rates, sample distributions |
| `cohort_summary` | Aggregate demographics for a cohort defined by a subquery |

## Guided Prompts

The server includes three MCP prompts that guide Claude through common workflows:

- **clinical_data_exploration** — Step-by-step CDW exploration: schema overview, table discovery, query building
- **cohort_building** — Cohort identification workflow with correct patient identifier patterns and query optimization tips
- **notes_analysis** — Clinical notes investigation from patient identification through note retrieval and summarization

## Installation

### Requirements

- Python >= 3.11
- Access to a SQL Server Clinical Data Warehouse
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/neuroGB/CDW_MedCP.git
cd CDW_MedCP

# Install dependencies
uv sync

# Copy and fill in your credentials
cp .env.example .env
# Edit .env with your database connection details
```

### Running

```bash
# Run with uv
uv run cdw-medcp

# Or install and run directly
uv pip install .
cdw-medcp

# Or run as a module
python -m cdw_medcp
```

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `CLINICAL_RECORDS_SERVER` | Yes | SQL Server hostname |
| `CLINICAL_RECORDS_DATABASE` | Yes | Database name |
| `CLINICAL_RECORDS_USERNAME` | Yes | SQL Server username |
| `CLINICAL_RECORDS_PASSWORD` | Yes | SQL Server password |
| `CDW_NAMESPACE` | No | Tool name prefix (default: `CDW`) |
| `CDW_SCHEMA` | No | Database schema for table qualification (default: `deid_uf`) |
| `CDW_LOG_LEVEL` | No | Logging level (default: `INFO`) |

### Claude Desktop Integration

CDW_MedCP can be installed as a Claude Desktop extension via the MCPB bundle format. The `manifest.json` defines the tool interface and credential configuration with OS keychain storage for passwords.

### Claude Code Integration

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "cdw-medcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/CDW_MedCP", "cdw-medcp"],
      "env": {
        "CLINICAL_RECORDS_SERVER": "your-server",
        "CLINICAL_RECORDS_DATABASE": "your-database",
        "CLINICAL_RECORDS_USERNAME": "your-username",
        "CLINICAL_RECORDS_PASSWORD": "your-password"
      }
    }
  }
}
```

## Project Structure

```
src/cdw_medcp/
├── __init__.py          # Package exports
├── __main__.py          # python -m cdw_medcp
├── cli.py               # CLI entry point
├── server.py            # FastMCP instance, tool registration, prompts
├── config.py            # Pydantic configuration models
├── db.py                # Per-query pymssql connection management
├── validation.py        # SQL read-only validation
└── tools/
    ├── schema.py        # Schema discovery tools
    ├── queries.py       # Query execution and clinical record retrieval
    ├── notes.py         # Clinical notes search and retrieval
    ├── export.py        # CSV export
    ├── concepts.py      # Diagnosis/medication/procedure code search
    └── stats.py         # Table and cohort summary statistics
```

## Security Policy

### Read-Only Enforcement

All SQL queries are validated before execution by `ClinicalQueryValidator`:

- Only `SELECT`, `WITH`, and `DECLARE` statements are allowed
- Write operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `EXEC`, `MERGE`, `CREATE`) are blocked
- Semicolons are rejected to prevent statement chaining
- Queries are validated after stripping SQL comments

### Credential Handling

- Database credentials are passed via environment variables, never hardcoded
- The MCPB manifest marks the password field as `sensitive: true` for OS keychain storage in Claude Desktop
- No credentials are logged or included in tool responses

## Disclaimer

**THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.** The authors (Gianmarco Bellucci and Wanjun Gu) make no representations or warranties regarding the accuracy, completeness, or reliability of the software or its outputs.

**Important notices:**

- This tool is designed for **research purposes only** and is **not intended for clinical decision-making** or direct patient care.
- The authors are **not responsible** for any consequences arising from the use or misuse of this software, including but not limited to: incorrect query results, data misinterpretation, security incidents, or regulatory non-compliance.
- Users are solely responsible for ensuring their use of this software complies with all applicable **institutional policies**, **data use agreements**, **IRB protocols**, and **privacy regulations** (including HIPAA where applicable).
- The read-only SQL validation provides a defense-in-depth layer but should **not be the sole security control**. Database-level permissions and network controls should be configured independently.
- Clinical data accessed through this tool is **de-identified** per the source data warehouse configuration. Users must not attempt to re-identify patients.

## License

MIT

## Acknowledgments

Based on the [MedCP](https://github.com/BaranziniLab/MedCP) project by the UCSF Baranzini Lab.
