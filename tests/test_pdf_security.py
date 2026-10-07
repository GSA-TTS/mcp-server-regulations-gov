import unittest
from unittest.mock import patch

import httpx

from regulations_gov.pdf import _validate_download_url, fetch_pdf_text


class TestDownloadUrlValidation(unittest.TestCase):
    def test_accepts_expected_download_url(self):
        assert _validate_download_url(
            "https://downloads.regulations.gov/example/document.pdf"
        ) is None

    def test_rejects_non_https_url(self):
        assert _validate_download_url(
            "http://downloads.regulations.gov/example/document.pdf"
        ) is not None

    def test_rejects_different_host(self):
        assert _validate_download_url(
            "https://downloads.regulations.gov.example.com/document.pdf"
        ) is not None

    def test_rejects_credentials(self):
        assert _validate_download_url(
            "https://user:password@downloads.regulations.gov/document.pdf"
        ) is not None

    def test_rejects_non_default_port(self):
        assert _validate_download_url(
            "https://downloads.regulations.gov:8443/document.pdf"
        ) is not None


class TestRedirectHandling(unittest.IsolatedAsyncioTestCase):
    async def test_does_not_follow_redirect(self):
        for status_code in (301, 302, 303, 307, 308):
            with self.subTest(status_code=status_code):
                requested_urls = []

                def handler(request: httpx.Request) -> httpx.Response:
                    requested_urls.append(str(request.url))
                    return httpx.Response(
                        status_code,
                        headers={"Location": "http://169.254.169.254/latest/meta-data/"},
                    )

                transport = httpx.MockTransport(handler)
                real_async_client = httpx.AsyncClient

                def make_client(**kwargs):
                    self.assertFalse(kwargs["follow_redirects"])
                    return real_async_client(transport=transport, **kwargs)

                with patch(
                    "regulations_gov.pdf.httpx.AsyncClient", side_effect=make_client
                ):
                    result = await fetch_pdf_text(
                        "https://downloads.regulations.gov/example/document.pdf"
                    )

                self.assertEqual(
                    result, "Error: Attachment redirects are not allowed."
                )
                self.assertEqual(
                    requested_urls,
                    ["https://downloads.regulations.gov/example/document.pdf"],
                )


if __name__ == "__main__":
    unittest.main()
