from __future__ import annotations

import asyncio
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from ..models import ResponseFormat
from ..pdf import fetch_pdf_text
from ..utils import (
    READ_ONLY_ANNOTATIONS,
    collect_pdf_file_urls,
    format_detail_response_markdown,
    format_document_markdown,
    handle_api_error,
    make_api_request,
    to_json_response,
)


def register(mcp: FastMCP) -> None:
    """Register the regulations_get_document tool with the MCP server."""

    @mcp.tool(
        name="regulations_get_document",
        annotations={
            "title": "Get Regulations.gov Document Details",
            **READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_get_document(
        document_id: Annotated[
            str,
            Field(
                description="The document object ID or document ID (e.g., '09000064846eae46' or 'EPA-HQ-OAR-2021-0257-0001')",
                min_length=1,
                max_length=100,
            ),
        ],
        download_content: Annotated[
            bool,
            Field(
                description=(
                    "Download and extract text from all PDF files attached to this document. "
                    "Uses the API's include=attachments parameter to discover file URLs, "
                    "then fetches each PDF and extracts its text content. "
                    "Use this to read the actual document or supporting file text."
                )
            ),
        ] = False,
        response_format: Annotated[
            ResponseFormat,
            Field(description="Output format: 'markdown' for human-readable, 'json' for machine-readable"),
        ] = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get full details for a specific document on regulations.gov, optionally downloading its content.

        Retrieves comprehensive metadata for a single document including title, agency,
        docket, comment period dates, and Federal Register number.

        When download_content=True, calls the API with include=attachments to discover all
        file URLs (from data.attributes.fileFormats and included[].attributes.fileFormats),
        downloads each PDF, and extracts the full text.

        Use when:
            - Get document metadata: document_id='FDA-2009-N-0501-0012'
            - Read document text: document_id='FDA-2009-N-0501-0012', download_content=True

        Returns document metadata. If download_content=True, also includes the extracted
        text from each PDF file under labeled sections. On error, returns a string
        beginning with 'Error:'.
        """
        try:
            api_params = {"include": "attachments"} if download_content else {}
            data = await make_api_request(f"documents/{document_id}", api_params or None)

            if download_content:
                pdf_urls = collect_pdf_file_urls(data)
                if pdf_urls:
                    texts = await asyncio.gather(*[fetch_pdf_text(url) for url in pdf_urls])
                    if response_format == ResponseFormat.JSON:
                        result = dict(data)
                        result["extracted_content"] = [
                            {"url": url, "text": text}
                            for url, text in zip(pdf_urls, texts)
                        ]
                        return to_json_response(result)
                    meta = format_detail_response_markdown(
                        data.get("data", data), "Document", format_document_markdown
                    )
                    sections = [meta, ""]
                    for url, text in zip(pdf_urls, texts):
                        name = url.rsplit("/", 1)[-1]
                        sections += [f"## Content: {name}", "", text, ""]
                    return "\n".join(sections)

            if response_format == ResponseFormat.JSON:
                return to_json_response(data)

            return format_detail_response_markdown(
                data.get("data", data), "Document", format_document_markdown
            )
        except Exception as e:
            return handle_api_error(e)
