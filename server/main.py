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
