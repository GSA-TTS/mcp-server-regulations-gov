import json
from typing import TYPE_CHECKING

from .models import (
    GetCommentInput,
    GetDocumentInput,
    GetDocketInput,
    ResponseFormat,
    SearchCommentsInput,
    SearchDocumentsInput,
    SearchDocketsInput,
)
from .utils import (
    build_pagination_meta,
    build_search_params,
    format_comment_markdown,
    format_detail_response_markdown,
    format_document_markdown,
    format_docket_markdown,
    format_search_response_markdown,
    handle_api_error,
    make_api_request,
    to_json_response,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

_READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def register_tools(mcp: "FastMCP") -> None:

    @mcp.tool(
        name="regulations_search_documents",
        annotations={
            "title": "Search Regulations.gov Documents",
            **_READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_search_documents(params: SearchDocumentsInput) -> str:
        """Search for federal regulatory documents on regulations.gov.

        Searches across Rules, Proposed Rules, Notices, and Other documents published
        by US federal agencies. Supports full-text search, agency/docket filtering,
        date ranges, and pagination.

        Note: Results are capped at 5,000 per query sequence. For datasets larger than
        5,000, use narrow date ranges or the docket_id filter to retrieve all records.

        Args:
            params (SearchDocumentsInput): Search parameters including:
                - search_term (Optional[str]): Full-text keyword search
                - agency_ids (Optional[List[str]]): Filter by agency IDs (e.g., ['EPA', 'DOT'])
                - docket_id (Optional[str]): Filter by docket (e.g., 'EPA-HQ-OAR-2021-0257')
                - posted_date_start (Optional[str]): Start date YYYY-MM-DD
                - posted_date_end (Optional[str]): End date YYYY-MM-DD
                - document_type (Optional[DocumentType]): 'Rule', 'Proposed Rule', 'Notice', 'Other'
                - sort (Optional[str]): Sort field, prefix '-' for descending (e.g., '-postedDate')
                - page_size (int): Results per page, 1-250, default 20
                - page_number (int): Page number, default 1
                - include_attachments (bool): Include attachment metadata, default False
                - response_format (ResponseFormat): 'markdown' or 'json', default 'markdown'

        Returns:
            str: Paginated list of documents with title, ID, type, agency, docket,
                 posted date, and comment period. Includes pagination metadata.

        Examples:
            - Find EPA air quality rules: agency_ids=['EPA'], document_type='Rule', search_term='air quality'
            - Recent proposed rules: document_type='Proposed Rule', sort='-postedDate'
            - Documents in a docket: docket_id='EPA-HQ-OAR-2021-0257'
        """
        try:
            extra = {}
            if params.document_type:
                extra["filter[documentType]"] = params.document_type.value

            api_params = build_search_params(
                search_term=params.search_term,
                agency_ids=params.agency_ids,
                docket_id=params.docket_id,
                posted_date_start=params.posted_date_start,
                posted_date_end=params.posted_date_end,
                page_size=params.page_size,
                page_number=params.page_number,
                sort=params.sort,
                include_attachments=params.include_attachments,
                extra=extra,
            )

            data = await make_api_request("documents", api_params)
            items = data.get("data", [])
            total = data.get("meta", {}).get("totalElements", len(items))
            pagination = build_pagination_meta(total, params.page_size, params.page_number, len(items))

            if params.response_format == ResponseFormat.JSON:
                return to_json_response({"pagination": pagination, "documents": items})

            return format_search_response_markdown(
                items, "Documents", format_document_markdown, pagination, params.search_term
            )
        except Exception as e:
            return handle_api_error(e)

    @mcp.tool(
        name="regulations_get_document",
        annotations={
            "title": "Get Regulations.gov Document Details",
            **_READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_get_document(params: GetDocumentInput) -> str:
        """Get full details for a specific document on regulations.gov.

        Retrieves comprehensive metadata for a single document including title, agency,
        docket, comment period dates, Federal Register number, and optionally attachment
        metadata. Use this after regulations_search_documents to get complete document details.

        Args:
            params (GetDocumentInput): Parameters including:
                - document_id (str): Document object ID or document ID
                  (e.g., '09000064846eae46' or 'EPA-HQ-OAR-2021-0257-0001')
                - include_attachments (bool): Include attachment metadata, default False
                - response_format (ResponseFormat): 'markdown' or 'json', default 'markdown'

        Returns:
            str: Full document metadata. If include_attachments=True, also returns
                 attachment list with file formats and sizes.

        Examples:
            - Get document details: document_id='EPA-HQ-OAR-2021-0257-0001'
            - Get document with attachments: document_id='...', include_attachments=True
        """
        try:
            api_params = {}
            if params.include_attachments:
                api_params["include"] = "attachments"

            data = await make_api_request(f"documents/{params.document_id}", api_params or None)

            if params.response_format == ResponseFormat.JSON:
                return to_json_response(data)

            return format_detail_response_markdown(data.get("data", data), "Document", format_document_markdown)
        except Exception as e:
            return handle_api_error(e)

    @mcp.tool(
        name="regulations_search_comments",
        annotations={
            "title": "Search Regulations.gov Public Comments",
            **_READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_search_comments(params: SearchCommentsInput) -> str:
        """Search for public comments submitted to regulations.gov.

        Searches across public comments submitted by individuals, organizations, and
        government entities in response to proposed rules and notices. The comment text
        field is public, but personally identifiable information (address, email, phone)
        is never returned by the API.

        Note: Rate limit for comment endpoints is 50 requests/minute, 500/hour.

        Args:
            params (SearchCommentsInput): Search parameters including:
                - search_term (Optional[str]): Full-text search across comment content
                - agency_ids (Optional[List[str]]): Filter by agency IDs
                - docket_id (Optional[str]): Filter by docket ID
                - comment_on_id (Optional[str]): Filter by document object ID being commented on.
                  Use regulations_get_document to find objectId values.
                - posted_date_start (Optional[str]): Start date YYYY-MM-DD
                - posted_date_end (Optional[str]): End date YYYY-MM-DD
                - sort (Optional[str]): Sort field, prefix '-' for descending
                - page_size (int): Results per page, 1-250, default 20
                - page_number (int): Page number, default 1
                - response_format (ResponseFormat): 'markdown' or 'json', default 'markdown'

        Returns:
            str: Paginated list of comments with title, ID, agency, docket, tracking
                 number, and comment excerpt (first 300 characters).

        Examples:
            - Comments on a proposed rule: docket_id='EPA-HQ-OAR-2021-0257'
            - Comments mentioning jobs: search_term='jobs', agency_ids=['DOL']
            - Comments on specific document: comment_on_id='09000064846eae46'
        """
        try:
            api_params = build_search_params(
                search_term=params.search_term,
                agency_ids=params.agency_ids,
                docket_id=params.docket_id,
                posted_date_start=params.posted_date_start,
                posted_date_end=params.posted_date_end,
                page_size=params.page_size,
                page_number=params.page_number,
                sort=params.sort,
                extra={"filter[commentOnId]": params.comment_on_id} if params.comment_on_id else None,
            )

            data = await make_api_request("comments", api_params)
            items = data.get("data", [])
            total = data.get("meta", {}).get("totalElements", len(items))
            pagination = build_pagination_meta(total, params.page_size, params.page_number, len(items))

            if params.response_format == ResponseFormat.JSON:
                return to_json_response({"pagination": pagination, "comments": items})

            return format_search_response_markdown(
                items, "Comments", format_comment_markdown, pagination, params.search_term
            )
        except Exception as e:
            return handle_api_error(e)

    @mcp.tool(
        name="regulations_get_comment",
        annotations={
            "title": "Get Regulations.gov Comment Details",
            **_READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_get_comment(params: GetCommentInput) -> str:
        """Get full details for a specific public comment on regulations.gov.

        Retrieves the full text and metadata for a single public comment. Note that
        personally identifiable information (address, email, phone) is never returned
        by the API per regulations.gov policy.

        Args:
            params (GetCommentInput): Parameters including:
                - comment_id (str): Comment document ID (e.g., 'EPA-HQ-OAR-2021-0257-0542')
                - include_attachments (bool): Include attachment metadata, default False
                - response_format (ResponseFormat): 'markdown' or 'json', default 'markdown'

        Returns:
            str: Full comment text and metadata including organization, tracking number,
                 docket, and receive/post dates.

        Examples:
            - Get comment text: comment_id='EPA-HQ-OAR-2021-0257-0542'
            - Get comment with attachments: comment_id='...', include_attachments=True
        """
        try:
            api_params = {}
            if params.include_attachments:
                api_params["include"] = "attachments"

            data = await make_api_request(f"comments/{params.comment_id}", api_params or None)

            if params.response_format == ResponseFormat.JSON:
                return to_json_response(data)

            return format_detail_response_markdown(data.get("data", data), "Comment", format_comment_markdown)
        except Exception as e:
            return handle_api_error(e)

    @mcp.tool(
        name="regulations_search_dockets",
        annotations={
            "title": "Search Regulations.gov Dockets",
            **_READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_search_dockets(params: SearchDocketsInput) -> str:
        """Search for regulatory dockets on regulations.gov.

        Dockets are the top-level organizational unit that groups related documents
        and comments for a rulemaking or nonrulemaking action. Each docket represents
        a regulatory action from initiation through final rule.

        Args:
            params (SearchDocketsInput): Search parameters including:
                - search_term (Optional[str]): Full-text search across docket titles
                - agency_ids (Optional[List[str]]): Filter by agency IDs (e.g., ['EPA', 'NHTSA'])
                - docket_id (Optional[str]): Filter by specific docket ID
                - posted_date_start (Optional[str]): Start date YYYY-MM-DD
                - posted_date_end (Optional[str]): End date YYYY-MM-DD
                - docket_type (Optional[DocketType]): 'Rulemaking' or 'Nonrulemaking'
                - sort (Optional[str]): Sort field, prefix '-' for descending (e.g., '-modifyDate')
                - page_size (int): Results per page, 1-250, default 20
                - page_number (int): Page number, default 1
                - response_format (ResponseFormat): 'markdown' or 'json', default 'markdown'

        Returns:
            str: Paginated list of dockets with title, ID, agency, type, RIN,
                 program, keywords, and last modified date.

        Examples:
            - Find EPA rulemaking dockets: agency_ids=['EPA'], docket_type='Rulemaking'
            - Search by topic: search_term='methane emissions'
            - Recently updated: sort='-modifyDate'
        """
        try:
            extra = {}
            if params.docket_type:
                extra["filter[docketType]"] = params.docket_type.value

            api_params = build_search_params(
                search_term=params.search_term,
                agency_ids=params.agency_ids,
                docket_id=params.docket_id,
                posted_date_start=params.posted_date_start,
                posted_date_end=params.posted_date_end,
                page_size=params.page_size,
                page_number=params.page_number,
                sort=params.sort,
                extra=extra if extra else None,
            )

            data = await make_api_request("dockets", api_params)
            items = data.get("data", [])
            total = data.get("meta", {}).get("totalElements", len(items))
            pagination = build_pagination_meta(total, params.page_size, params.page_number, len(items))

            if params.response_format == ResponseFormat.JSON:
                return to_json_response({"pagination": pagination, "dockets": items})

            return format_search_response_markdown(
                items, "Dockets", format_docket_markdown, pagination, params.search_term
            )
        except Exception as e:
            return handle_api_error(e)

    @mcp.tool(
        name="regulations_get_docket",
        annotations={
            "title": "Get Regulations.gov Docket Details",
            **_READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_get_docket(params: GetDocketInput) -> str:
        """Get full details for a specific regulatory docket on regulations.gov.

        Retrieves comprehensive metadata for a single docket including title, agency,
        type, RIN (Regulatory Identifier Number), program, keywords, and modification
        dates. Use regulations_search_dockets to discover docket IDs first.

        Args:
            params (GetDocketInput): Parameters including:
                - docket_id (str): Docket ID (e.g., 'EPA-HQ-OAR-2021-0257')
                - response_format (ResponseFormat): 'markdown' or 'json', default 'markdown'

        Returns:
            str: Full docket metadata including agency, type, RIN, program, keywords,
                 and modification date.

        Examples:
            - Get docket details: docket_id='EPA-HQ-OAR-2021-0257'
            - Get docket as JSON: docket_id='EPA-HQ-OAR-2021-0257', response_format='json'
        """
        try:
            data = await make_api_request(f"dockets/{params.docket_id}")

            if params.response_format == ResponseFormat.JSON:
                return to_json_response(data)

            return format_detail_response_markdown(data.get("data", data), "Docket", format_docket_markdown)
        except Exception as e:
            return handle_api_error(e)
