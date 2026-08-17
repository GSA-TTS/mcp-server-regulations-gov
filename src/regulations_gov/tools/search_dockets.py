from __future__ import annotations

from typing import Annotated, List, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import DocketType, ResponseFormat, validate_date
from ..utils import (
    READ_ONLY_ANNOTATIONS,
    build_pagination_meta,
    build_search_params,
    format_docket_markdown,
    format_search_response_markdown,
    handle_api_error,
    make_api_request,
    to_json_response,
)


def register(mcp: FastMCP) -> None:
    """Register the regulations_search_dockets tool with the MCP server."""

    @mcp.tool(
        name="regulations_search_dockets",
        annotations={
            "title": "Search Regulations.gov Dockets",
            **READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_search_dockets(
        search_term: Annotated[
            Optional[str],
            Field(
                description="Full-text keyword search across docket titles and content (e.g., 'vehicle emissions', 'food labeling')",
                max_length=500,
            ),
        ] = None,
        agency_ids: Annotated[
            Optional[List[str]],
            Field(
                description="Filter by one or more agency IDs (e.g., ['EPA', 'NHTSA', 'FDA'])",
                max_length=20,
            ),
        ] = None,
        docket_id: Annotated[
            Optional[str],
            Field(description="Filter by specific docket ID (e.g., 'EPA-HQ-OAR-2021-0257')", max_length=100),
        ] = None,
        posted_date_start: Annotated[
            Optional[str],
            Field(description="Filter dockets created on or after this date. Format: YYYY-MM-DD"),
        ] = None,
        posted_date_end: Annotated[
            Optional[str],
            Field(description="Filter dockets created on or before this date. Format: YYYY-MM-DD"),
        ] = None,
        docket_type: Annotated[
            Optional[DocketType],
            Field(
                description="Filter by docket type: 'Rulemaking' (formal regulatory process) or 'Nonrulemaking' (notices, guidance)"
            ),
        ] = None,
        sort: Annotated[
            Optional[str],
            Field(
                description="Sort field. Prefix with '-' for descending (e.g., '-modifyDate'). Common fields: title, modifyDate",
                max_length=50,
            ),
        ] = None,
        page_size: Annotated[
            int, Field(description="Number of results per page (1-250)", ge=1, le=250)
        ] = 20,
        page_number: Annotated[
            int, Field(description="Page number for pagination (starts at 1)", ge=1)
        ] = 1,
        response_format: Annotated[
            ResponseFormat,
            Field(description="Output format: 'markdown' for human-readable, 'json' for machine-readable"),
        ] = ResponseFormat.MARKDOWN,
    ) -> str:
        """Search for regulatory dockets on regulations.gov.

        Dockets are the top-level organizational unit that groups related documents
        and comments for a rulemaking or nonrulemaking action. Each docket represents
        a regulatory action from initiation through final rule.

        Use when:
            - Find EPA rulemaking dockets: agency_ids=['EPA'], docket_type='Rulemaking'
            - Search by topic: search_term='methane emissions'
            - Recently updated: sort='-modifyDate'

        Returns a paginated list of dockets with title, ID, agency, type, RIN, program,
        keywords, and last modified date, plus pagination metadata. On error, returns a
        string beginning with 'Error:'.
        """
        try:
            validate_date(posted_date_start)
            validate_date(posted_date_end)

            extra = {}
            if docket_type:
                extra["filter[docketType]"] = docket_type.value

            api_params = build_search_params(
                search_term=search_term,
                agency_ids=agency_ids,
                docket_id=docket_id,
                posted_date_start=posted_date_start,
                posted_date_end=posted_date_end,
                page_size=page_size,
                page_number=page_number,
                sort=sort,
                extra=extra if extra else None,
            )

            data = await make_api_request("dockets", api_params)
            items = data.get("data", [])
            total = data.get("meta", {}).get("totalElements", len(items))
            pagination = build_pagination_meta(total, page_size, page_number, len(items))

            if response_format == ResponseFormat.JSON:
                return to_json_response({"pagination": pagination, "dockets": items})

            return format_search_response_markdown(
                items, "Dockets", format_docket_markdown, pagination, search_term
            )
        except Exception as e:
            return handle_api_error(e)
