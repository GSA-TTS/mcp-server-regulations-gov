import json
import os
from typing import Any, Dict, List, Optional

import httpx

API_BASE_URL = "https://api.regulations.gov/v4"

# Shared tool annotations: every tool in this server is a read-only, idempotent
# query against the public regulations.gov API (an external/open-world service).
READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def get_api_key() -> str:
    key = os.environ.get("REGULATIONS_GOV_API_KEY")
    if not key:
        raise EnvironmentError(
            "REGULATIONS_GOV_API_KEY environment variable is not set. "
            "Register for a free API key at https://api.data.gov/signup/ "
            "and set it before starting the server."
        )
    return key


async def make_api_request(
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    api_key = get_api_key()
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        return response.json()


def handle_api_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 400:
            try:
                body = e.response.json()
                errors = body.get("errors", [])
                detail = "; ".join(err.get("detail", "") for err in errors) if errors else str(body)
                return f"Error: Bad request — {detail}. Check your filter parameters and try again."
            except Exception:
                return "Error: Bad request. Check your filter parameters and try again."
        if status == 401:
            return (
                "Error: Invalid API key. Verify REGULATIONS_GOV_API_KEY is correct. "
                "Register at https://api.data.gov/signup/"
            )
        if status == 403:
            return "Error: Access forbidden. Your API key may not have permission for this resource."
        if status == 404:
            return "Error: Resource not found. Check that the ID is correct and try again."
        if status == 429:
            return (
                "Error: Rate limit exceeded (limit: 50 requests/minute, 500/hour for comment endpoints). "
                "Wait a moment before retrying."
            )
        return f"Error: API request failed with HTTP {status}. Try again later."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out after 30 seconds. The regulations.gov API may be slow — try again."
    if isinstance(e, httpx.ConnectError):
        return "Error: Could not connect to regulations.gov. Check your internet connection and try again."
    if isinstance(e, EnvironmentError):
        return f"Error: {e}"
    return f"Error: Unexpected error ({type(e).__name__}): {e}"


def build_pagination_meta(
    total: int,
    page_size: int,
    page_number: int,
    count: int,
) -> Dict[str, Any]:
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    return {
        "total_count": total,
        "page": page_number,
        "page_size": page_size,
        "count": count,
        "total_pages": total_pages,
        "has_more": page_number < total_pages,
    }


def _field(data: Dict[str, Any], key: str, default: str = "N/A") -> str:
    val = data.get(key)
    return str(val) if val is not None else default


def _attrs(item: Dict[str, Any]) -> Dict[str, Any]:
    return item.get("attributes", {})


def collect_pdf_file_urls(api_response: Dict[str, Any]) -> List[str]:
    """Collect all PDF fileUrls from a document API response.

    Reads both the primary document files (data.attributes.fileFormats) and any
    included attachment files (included[].attributes.fileFormats), returning the
    URL of every format whose type is PDF.
    """
    urls: List[str] = []

    def _extract(fmt_list: Any) -> None:
        if not isinstance(fmt_list, list):
            return
        for fmt in fmt_list:
            if isinstance(fmt, dict) and fmt.get("format", "").lower() == "pdf":
                url = fmt.get("fileUrl", "")
                if url:
                    urls.append(url)

    data = api_response.get("data", {})
    _extract(_attrs(data).get("fileFormats", []))

    for item in api_response.get("included", []):
        _extract(_attrs(item).get("fileFormats", []))

    return urls


def format_document_markdown(doc: Dict[str, Any]) -> str:
    attrs = _attrs(doc)
    lines = [
        f"### {_field(attrs, 'title')}",
        f"- **ID**: {_field(doc, 'id')}",
        f"- **Type**: {_field(attrs, 'documentType')}",
        f"- **Agency**: {_field(attrs, 'agencyId')}",
        f"- **Docket**: {_field(attrs, 'docketId')}",
        f"- **Posted**: {_field(attrs, 'postedDate')}",
        f"- **Comment Period**: {_field(attrs, 'commentStartDate')} → {_field(attrs, 'commentEndDate')}",
        f"- **Open for Comment**: {_field(attrs, 'openForComment')}",
    ]
    if attrs.get("frDocNum"):
        lines.append(f"- **Federal Register Doc**: {attrs['frDocNum']}")
    if attrs.get("attachmentCount"):
        lines.append(f"- **Attachments**: {attrs['attachmentCount']}")
    return "\n".join(lines)


def format_comment_markdown(comment: Dict[str, Any]) -> str:
    attrs = _attrs(comment)
    lines = [
        f"### {_field(attrs, 'title')}",
        f"- **ID**: {_field(comment, 'id')}",
        f"- **Agency**: {_field(attrs, 'agencyId')}",
        f"- **Docket**: {_field(attrs, 'docketId')}",
        f"- **Posted**: {_field(attrs, 'postedDate')}",
        f"- **Received**: {_field(attrs, 'receiveDate')}",
        f"- **Tracking #**: {_field(attrs, 'trackingNbr')}",
    ]
    if attrs.get("organization"):
        lines.append(f"- **Organization**: {attrs['organization']}")
    if attrs.get("comment"):
        excerpt = attrs["comment"][:300]
        if len(attrs["comment"]) > 300:
            excerpt += "…"
        lines.append(f"- **Comment**: {excerpt}")
    return "\n".join(lines)


def format_docket_markdown(docket: Dict[str, Any]) -> str:
    attrs = _attrs(docket)
    lines = [
        f"### {_field(attrs, 'title')}",
        f"- **ID**: {_field(docket, 'id')}",
        f"- **Agency**: {_field(attrs, 'agencyId')}",
        f"- **Type**: {_field(attrs, 'docketType')}",
        f"- **Modified**: {_field(attrs, 'modifyDate')}",
    ]
    if attrs.get("program"):
        lines.append(f"- **Program**: {attrs['program']}")
    if attrs.get("rin"):
        lines.append(f"- **RIN**: {attrs['rin']}")
    if attrs.get("keywords"):
        kw = attrs["keywords"]
        if isinstance(kw, list):
            lines.append(f"- **Keywords**: {', '.join(kw)}")
    return "\n".join(lines)


def build_search_params(
    search_term: Optional[str],
    agency_ids: Optional[List[str]],
    docket_id: Optional[str],
    posted_date_start: Optional[str],
    posted_date_end: Optional[str],
    page_size: int,
    page_number: int,
    sort: Optional[str],
    include_attachments: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "page[size]": page_size,
        "page[number]": page_number,
    }
    if search_term:
        params["filter[searchTerm]"] = search_term
    if agency_ids:
        params["filter[agencyId]"] = ",".join(agency_ids)
    if docket_id:
        params["filter[docketId]"] = docket_id
    if posted_date_start:
        params["filter[postedDate][ge]"] = posted_date_start
    if posted_date_end:
        params["filter[postedDate][le]"] = posted_date_end
    if sort:
        params["sort"] = sort
    if include_attachments:
        params["include"] = "attachments"
    if extra:
        params.update(extra)
    return params


def format_search_response_markdown(
    items: List[Dict[str, Any]],
    resource_type: str,
    formatter,
    pagination: Dict[str, Any],
    search_term: Optional[str],
) -> str:
    header = f"# {resource_type} Search Results"
    if search_term:
        header += f": '{search_term}'"
    lines = [
        header,
        "",
        f"**Total**: {pagination['total_count']} | "
        f"**Page**: {pagination['page']}/{pagination['total_pages']} | "
        f"**Showing**: {pagination['count']}",
        "",
    ]
    if not items:
        lines.append(f"No {resource_type.lower()} found matching your criteria.")
        return "\n".join(lines)
    for item in items:
        lines.append(formatter(item))
        lines.append("")
    if pagination["has_more"]:
        lines.append(f"*Use page_number={pagination['page'] + 1} to see more results.*")
    return "\n".join(lines)


def format_detail_response_markdown(
    item: Dict[str, Any],
    resource_type: str,
    formatter,
) -> str:
    lines = [f"# {resource_type} Details", "", formatter(item)]
    included = item.get("included", [])
    if included:
        lines += ["", "## Attachments", ""]
        for att in included:
            att_attrs = _attrs(att)
            title = att_attrs.get("title", att.get("id", "Untitled"))
            file_formats = att_attrs.get("fileFormats", [])
            lines.append(f"- **{title}**")
            for fmt in file_formats:
                if isinstance(fmt, dict):
                    size = fmt.get("size", "")
                    fmt_type = fmt.get("format", "")
                    file_url = fmt.get("fileUrl", "")
                    size_str = f" ({size} bytes)" if size else ""
                    url_str = f" — {file_url}" if file_url else ""
                    lines.append(f"  - {fmt_type}{size_str}{url_str}")
    return "\n".join(lines)


def to_json_response(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)
