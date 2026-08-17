from enum import Enum
from typing import Optional


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class DocumentType(str, Enum):
    RULE = "Rule"
    PROPOSED_RULE = "Proposed Rule"
    NOTICE = "Notice"
    OTHER = "Other"


class DocketType(str, Enum):
    RULEMAKING = "Rulemaking"
    NONRULEMAKING = "Nonrulemaking"


def validate_date(v: Optional[str]) -> Optional[str]:
    """Validate that a date string is in YYYY-MM-DD format.

    Returns the value unchanged (None passes through). Raises ValueError on a
    malformed date so Pydantic surfaces a clear validation error to the caller.
    """
    if v is None:
        return v
    import re

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise ValueError("Date must be in YYYY-MM-DD format (e.g., '2024-01-15')")
    return v
