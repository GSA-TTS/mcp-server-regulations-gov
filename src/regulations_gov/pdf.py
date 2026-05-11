import io
from urllib.parse import urlparse

import httpx

ALLOWED_HOST = "downloads.regulations.gov"
MAX_TEXT_CHARS = 50_000


def _validate_download_url(url: str) -> str | None:
    """Return an error string if the URL is not an allowed attachment URL, else None."""
    try:
        parsed = urlparse(url)
    except Exception:
        return f"Error: Could not parse URL '{url}'."
    if parsed.scheme != "https":
        return f"Error: URL must use HTTPS (got '{parsed.scheme}')."
    if parsed.hostname != ALLOWED_HOST:
        return (
            f"Error: URL host must be '{ALLOWED_HOST}' "
            f"(got '{parsed.hostname}'). Only regulations.gov attachment URLs are supported."
        )
    return None


def _extract_text_from_bytes(content: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts)


async def fetch_pdf_text(url: str) -> str:
    """Download a PDF from downloads.regulations.gov and return its extracted text.

    Returns an error string on any failure so callers can safely embed the result
    in a larger response without try/except.
    """
    err = _validate_download_url(url)
    if err:
        return err

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"Error: Could not download file — HTTP {e.response.status_code}."
    except httpx.TimeoutException:
        return "Error: Download timed out after 60 seconds."
    except httpx.ConnectError:
        return "Error: Could not connect to downloads.regulations.gov."
    except Exception as e:
        return f"Error: Unexpected error downloading file: {e}"

    text = _extract_text_from_bytes(response.content)

    if not text.strip():
        return (
            "No text could be extracted from this file. "
            "It may be a scanned image without OCR text. "
            f"Download it directly: {url}"
        )

    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + f"\n\n…[truncated at {MAX_TEXT_CHARS:,} of {len(text):,} characters]"

    return text
