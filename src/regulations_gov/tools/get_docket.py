from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from ..models import ResponseFormat
from ..utils import (
    READ_ONLY_ANNOTATIONS,
    format_detail_response_markdown,
    format_docket_markdown,
    handle_api_error,
    make_api_request,
    to_json_response,
)


def register(mcp: FastMCP) -> None:
    """Register the regulations_get_docket tool with the MCP server."""

    @mcp.tool(
        name="regulations_get_docket",
        annotations={
            "title": "Get Regulations.gov Docket Details",
            **READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_get_docket(
        docket_id: Annotated[
            str,
            Field(
                description="The docket ID (e.g., 'EPA-HQ-OAR-2021-0257')",
                min_length=1,
                max_length=100,
            ),
        ],
        response_format: Annotated[
            ResponseFormat,
            Field(description="Output format: 'markdown' for human-readable, 'json' for machine-readable"),
        ] = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get full details for a specific regulatory docket on regulations.gov.

        Retrieves comprehensive metadata for a single docket including title, agency,
        type, RIN (Regulatory Identifier Number), program, keywords, and modification
        dates. Use regulations_search_dockets to discover docket IDs first.

        Use when:
            - Get docket details: docket_id='EPA-HQ-OAR-2021-0257'
            - Get docket as JSON: docket_id='EPA-HQ-OAR-2021-0257', response_format='json'

        Returns full docket metadata including agency, type, RIN, program, keywords, and
        modification date. On error, returns a string beginning with 'Error:'.
        """
        try:
            data = await make_api_request(f"dockets/{docket_id}")

            if response_format == ResponseFormat.JSON:
                return to_json_response(data)

            return format_detail_response_markdown(
                data.get("data", data), "Docket", format_docket_markdown
            )
        except Exception as e:
            return handle_api_error(e)
