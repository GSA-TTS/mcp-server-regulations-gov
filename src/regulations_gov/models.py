from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


def _date_validator(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise ValueError("Date must be in YYYY-MM-DD format (e.g., '2024-01-15')")
    return v


class SearchDocumentsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    search_term: Optional[str] = Field(
        default=None,
        description="Full-text keyword search across document content and metadata (e.g., 'clean air', 'emissions standards')",
        max_length=500,
    )
    agency_ids: Optional[List[str]] = Field(
        default=None,
        description="Filter by one or more agency IDs (e.g., ['EPA', 'DOT']). Use regulations_search_dockets to discover agency IDs.",
        max_length=20,
    )
    docket_id: Optional[str] = Field(
        default=None,
        description="Filter documents belonging to a specific docket (e.g., 'EPA-HQ-OAR-2021-0257')",
        max_length=100,
    )
    posted_date_start: Optional[str] = Field(
        default=None,
        description="Filter documents posted on or after this date. Format: YYYY-MM-DD (e.g., '2024-01-01')",
    )
    posted_date_end: Optional[str] = Field(
        default=None,
        description="Filter documents posted on or before this date. Format: YYYY-MM-DD (e.g., '2024-12-31')",
    )
    document_type: Optional[DocumentType] = Field(
        default=None,
        description="Filter by document type: 'Rule', 'Proposed Rule', 'Notice', or 'Other'",
    )
    sort: Optional[str] = Field(
        default=None,
        description="Sort field. Prefix with '-' for descending (e.g., '-postedDate' for newest first, 'title' for alphabetical). Common fields: postedDate, title, commentEndDate",
        max_length=50,
    )
    page_size: int = Field(
        default=20,
        description="Number of results per page (1-250, default 20)",
        ge=1,
        le=250,
    )
    page_number: int = Field(
        default=1,
        description="Page number for pagination (starts at 1)",
        ge=1,
    )
    include_attachments: bool = Field(
        default=False,
        description="Include attachment metadata in results",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable, 'json' for machine-readable",
    )

    @field_validator("posted_date_start", "posted_date_end")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        return _date_validator(v)


class GetDocumentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    document_id: str = Field(
        ...,
        description="The document object ID or document ID (e.g., '09000064846eae46' or 'EPA-HQ-OAR-2021-0257-0001')",
        min_length=1,
        max_length=100,
    )
    include_attachments: bool = Field(
        default=False,
        description="Include attachment metadata in the response",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable, 'json' for machine-readable",
    )


class SearchCommentsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    search_term: Optional[str] = Field(
        default=None,
        description="Full-text keyword search across comment content (e.g., 'public health', 'small business')",
        max_length=500,
    )
    agency_ids: Optional[List[str]] = Field(
        default=None,
        description="Filter by one or more agency IDs (e.g., ['EPA', 'FDA'])",
        max_length=20,
    )
    docket_id: Optional[str] = Field(
        default=None,
        description="Filter comments belonging to a specific docket (e.g., 'EPA-HQ-OAR-2021-0257')",
        max_length=100,
    )
    comment_on_id: Optional[str] = Field(
        default=None,
        description="Filter comments submitted in response to a specific document object ID. Use regulations_get_document to find objectId values.",
        max_length=100,
    )
    posted_date_start: Optional[str] = Field(
        default=None,
        description="Filter comments posted on or after this date. Format: YYYY-MM-DD",
    )
    posted_date_end: Optional[str] = Field(
        default=None,
        description="Filter comments posted on or before this date. Format: YYYY-MM-DD",
    )
    sort: Optional[str] = Field(
        default=None,
        description="Sort field. Prefix with '-' for descending (e.g., '-postedDate'). Common fields: postedDate, title",
        max_length=50,
    )
    page_size: int = Field(
        default=20,
        description="Number of results per page (1-250, default 20)",
        ge=1,
        le=250,
    )
    page_number: int = Field(
        default=1,
        description="Page number for pagination (starts at 1)",
        ge=1,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable, 'json' for machine-readable",
    )

    @field_validator("posted_date_start", "posted_date_end")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        return _date_validator(v)


class GetCommentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    comment_id: str = Field(
        ...,
        description="The comment object ID or document ID (e.g., 'EPA-HQ-OAR-2021-0257-0542')",
        min_length=1,
        max_length=100,
    )
    include_attachments: bool = Field(
        default=False,
        description="Include attachment metadata in the response",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable, 'json' for machine-readable",
    )


class SearchDocketsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    search_term: Optional[str] = Field(
        default=None,
        description="Full-text keyword search across docket titles and content (e.g., 'vehicle emissions', 'food labeling')",
        max_length=500,
    )
    agency_ids: Optional[List[str]] = Field(
        default=None,
        description="Filter by one or more agency IDs (e.g., ['EPA', 'NHTSA', 'FDA'])",
        max_length=20,
    )
    docket_id: Optional[str] = Field(
        default=None,
        description="Filter by specific docket ID (e.g., 'EPA-HQ-OAR-2021-0257')",
        max_length=100,
    )
    posted_date_start: Optional[str] = Field(
        default=None,
        description="Filter dockets created on or after this date. Format: YYYY-MM-DD",
    )
    posted_date_end: Optional[str] = Field(
        default=None,
        description="Filter dockets created on or before this date. Format: YYYY-MM-DD",
    )
    docket_type: Optional[DocketType] = Field(
        default=None,
        description="Filter by docket type: 'Rulemaking' (formal regulatory process) or 'Nonrulemaking' (notices, guidance)",
    )
    sort: Optional[str] = Field(
        default=None,
        description="Sort field. Prefix with '-' for descending (e.g., '-modifyDate'). Common fields: title, modifyDate",
        max_length=50,
    )
    page_size: int = Field(
        default=20,
        description="Number of results per page (1-250, default 20)",
        ge=1,
        le=250,
    )
    page_number: int = Field(
        default=1,
        description="Page number for pagination (starts at 1)",
        ge=1,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable, 'json' for machine-readable",
    )

    @field_validator("posted_date_start", "posted_date_end")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        return _date_validator(v)


class GetDocketInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    docket_id: str = Field(
        ...,
        description="The docket ID (e.g., 'EPA-HQ-OAR-2021-0257')",
        min_length=1,
        max_length=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable, 'json' for machine-readable",
    )
