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
