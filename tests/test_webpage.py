"""Tests for online webpage extraction and URL safety."""

import unittest

from vocab.webpage import WebpageFetchError, extract_readable_html, validate_public_url


class WebpageTextTests(unittest.TestCase):
    def test_extracts_article_text_without_page_chrome(self) -> None:
        source = """
        <html><head><title>  Example Article  </title></head><body>
          <header>Site banner</header><nav>Navigation</nav>
          <main><article><h1>Useful title</h1><p>First paragraph.</p>
          <p>Second <strong>paragraph</strong>.</p></article></main>
          <aside>Advertisement</aside><footer>Copyright</footer>
          <script>ignored()</script>
        </body></html>
        """

        title, text = extract_readable_html(source)

        self.assertEqual(title, "Example Article")
        self.assertIn("Useful title", text)
        self.assertIn("First paragraph.", text)
        self.assertIn("Second", text)
        self.assertNotIn("Site banner", text)
        self.assertNotIn("Navigation", text)
        self.assertNotIn("Advertisement", text)
        self.assertNotIn("ignored", text)

    def test_rejects_non_http_urls(self) -> None:
        with self.assertRaisesRegex(WebpageFetchError, "http"):
            validate_public_url("file:///etc/passwd")

    def test_rejects_loopback_urls(self) -> None:
        with self.assertRaisesRegex(WebpageFetchError, "local or private"):
            validate_public_url("http://127.0.0.1:8000/private")


if __name__ == "__main__":
    unittest.main()
