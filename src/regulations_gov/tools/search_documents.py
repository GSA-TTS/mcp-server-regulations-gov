from __future__ import annotations

from typing import Annotated, List, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import DocumentType, ResponseFormat, validate_date
from ..utils import (
    READ_ONLY_ANNOTATIONS,
    build_pagination_meta,
    build_search_params,
    format_document_markdown,
    format_search_response_markdown,
    handle_api_error,
    make_api_request,
    to_json_response,
)


def register(mcp: FastMCP) -> None:
    """Register the regulations_search_documents tool with the MCP server."""

    @mcp.tool(
        name="regulations_search_documents",
        annotations={
            "title": "Search Regulations.gov Documents",
            **READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_search_documents(
        search_term: Annotated[
            Optional[str],
            Field(
                description="Full-text keyword search across document content and metadata (e.g., 'clean air', 'emissions standards')",
                max_length=500,
            ),
        ] = None,
        agency_ids: Annotated[
            Optional[List[str]],
            Field(
                description="Filter by one or more agency IDs (e.g., ['EPA', 'DOT']). Use regulations_search_dockets to discover agency IDs.",
                max_length=20,
            ),
        ] = None,
        docket_id: Annotated[
            Optional[str],
            Field(
                description="Filter documents belonging to a specific docket (e.g., 'EPA-HQ-OAR-2021-0257')",
                max_length=100,
            ),
        ] = None,
        posted_date_start: Annotated[
            Optional[str],
            Field(description="Filter documents posted on or after this date. Format: YYYY-MM-DD (e.g., '2024-01-01')"),
        ] = None,
        posted_date_end: Annotated[
            Optional[str],
            Field(description="Filter documents posted on or before this date. Format: YYYY-MM-DD (e.g., '2024-12-31')"),
        ] = None,
        document_type: Annotated[
            Optional[DocumentType],
            Field(description="Filter by document type: 'Rule', 'Proposed Rule', 'Notice', or 'Other'"),
        ] = None,
        sort: Annotated[
            Optional[str],
            Field(
                description="Sort field. Prefix with '-' for descending (e.g., '-postedDate' for newest first, 'title' for alphabetical). Common fields: postedDate, title, commentEndDate",
                max_length=50,
            ),
        ] = None,
        page_size: Annotated[
            int, Field(description="Number of results per page (1-250)", ge=1, le=250)
        ] = 20,
        page_number: Annotated[
            int, Field(description="Page number for pagination (starts at 1)", ge=1)
        ] = 1,
        include_attachments: Annotated[
            bool, Field(description="Include attachment metadata in results")
        ] = False,
        response_format: Annotated[
            ResponseFormat,
            Field(description="Output format: 'markdown' for human-readable, 'json' for machine-readable"),
        ] = ResponseFormat.MARKDOWN,
    ) -> str:
        """Search for federal regulatory documents on regulations.gov.

        Searches across Rules, Proposed Rules, Notices, and Other documents published
        by US federal agencies. Supports full-text search, agency/docket filtering,
        date ranges, and pagination.

        Note: Results are capped at 5,000 per query sequence. For datasets larger than
        5,000, use narrow date ranges or the docket_id filter to retrieve all records.

        Use when:
            - Find EPA air quality rules: agency_ids=['EPA'], document_type='Rule', search_term='air quality'
            - Recent proposed rules: document_type='Proposed Rule', sort='-postedDate'
            - Documents in a docket: docket_id='EPA-HQ-OAR-2021-0257'

        Returns a paginated list of documents with title, ID, type, agency, docket,
        posted date, and comment period, plus pagination metadata. On error, returns a
        string beginning with 'Error:'.
        """
        try:
            validate_date(posted_date_start)
            validate_date(posted_date_end)

            extra = {}
            if document_type:
                extra["filter[documentType]"] = document_type.value

            api_params = build_search_params(
                search_term=search_term,
                agency_ids=agency_ids,
                docket_id=docket_id,
                posted_date_start=posted_date_start,
                posted_date_end=posted_date_end,
                page_size=page_size,
                page_number=page_number,
                sort=sort,
                include_attachments=include_attachments,
                extra=extra,
            )

            data = await make_api_request("documents", api_params)
            items = data.get("data", [])
            total = data.get("meta", {}).get("totalElements", len(items))
            pagination = build_pagination_meta(total, page_size, page_number, len(items))

            if response_format == ResponseFormat.JSON:
                return to_json_response({"pagination": pagination, "documents": items})

            return format_search_response_markdown(
                items, "Documents", format_document_markdown, pagination, search_term
            )
        except Exception as e:
            return handle_api_error(e)
