from __future__ import annotations

from typing import Annotated, List, Optional

from fastmcp import FastMCP
from pydantic import Field

from ..models import ResponseFormat, validate_date
from ..utils import (
    READ_ONLY_ANNOTATIONS,
    build_pagination_meta,
    build_search_params,
    format_comment_markdown,
    format_search_response_markdown,
    handle_api_error,
    make_api_request,
    to_json_response,
)


def register(mcp: FastMCP) -> None:
    """Register the regulations_search_comments tool with the MCP server."""

    @mcp.tool(
        name="regulations_search_comments",
        annotations={
            "title": "Search Regulations.gov Public Comments",
            **READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_search_comments(
        search_term: Annotated[
            Optional[str],
            Field(
                description="Full-text keyword search across comment content (e.g., 'public health', 'small business')",
                max_length=500,
            ),
        ] = None,
        agency_ids: Annotated[
            Optional[List[str]],
            Field(description="Filter by one or more agency IDs (e.g., ['EPA', 'FDA'])", max_length=20),
        ] = None,
        docket_id: Annotated[
            Optional[str],
            Field(
                description="Filter comments belonging to a specific docket (e.g., 'EPA-HQ-OAR-2021-0257')",
                max_length=100,
            ),
        ] = None,
        comment_on_id: Annotated[
            Optional[str],
            Field(
                description="Filter comments submitted in response to a specific document object ID. Use regulations_get_document to find objectId values.",
                max_length=100,
            ),
        ] = None,
        posted_date_start: Annotated[
            Optional[str],
            Field(description="Filter comments posted on or after this date. Format: YYYY-MM-DD"),
        ] = None,
        posted_date_end: Annotated[
            Optional[str],
            Field(description="Filter comments posted on or before this date. Format: YYYY-MM-DD"),
        ] = None,
        sort: Annotated[
            Optional[str],
            Field(
                description="Sort field. Prefix with '-' for descending (e.g., '-postedDate'). Common fields: postedDate, title",
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
        """Search for public comments submitted to regulations.gov.

        Searches across public comments submitted by individuals, organizations, and
        government entities in response to proposed rules and notices. The comment text
        field is public, but personally identifiable information (address, email, phone)
        is never returned by the API.

        Note: Rate limit for comment endpoints is 50 requests/minute, 500/hour.

        Use when:
            - Comments on a proposed rule: docket_id='EPA-HQ-OAR-2021-0257'
            - Comments mentioning jobs: search_term='jobs', agency_ids=['DOL']
            - Comments on specific document: comment_on_id='09000064846eae46'

        Returns a paginated list of comments with title, ID, agency, docket, tracking
        number, and comment excerpt (first 300 characters), plus pagination metadata.
        On error, returns a string beginning with 'Error:'.
        """
        try:
            validate_date(posted_date_start)
            validate_date(posted_date_end)

            api_params = build_search_params(
                search_term=search_term,
                agency_ids=agency_ids,
                docket_id=docket_id,
                posted_date_start=posted_date_start,
                posted_date_end=posted_date_end,
                page_size=page_size,
                page_number=page_number,
                sort=sort,
                extra={"filter[commentOnId]": comment_on_id} if comment_on_id else None,
            )

            data = await make_api_request("comments", api_params)
            items = data.get("data", [])
            total = data.get("meta", {}).get("totalElements", len(items))
            pagination = build_pagination_meta(total, page_size, page_number, len(items))

            if response_format == ResponseFormat.JSON:
                return to_json_response({"pagination": pagination, "comments": items})

            return format_search_response_markdown(
                items, "Comments", format_comment_markdown, pagination, search_term
            )
        except Exception as e:
            return handle_api_error(e)
