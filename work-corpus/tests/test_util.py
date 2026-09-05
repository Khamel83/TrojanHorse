from __future__ import annotations

import unittest

from work_corpus.util import parse_date_hint, scrub_derived_text, vtt_or_srt_to_markdown


class UtilTests(unittest.TestCase):
    def test_date_hint(self):
        self.assertEqual(parse_date_hint("meeting-2026-09-01"), "2026-09-01")
        self.assertEqual(parse_date_hint("20260901-note"), "2026-09-01")

    def test_vtt_conversion(self):
        text = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello.\n"
        result = vtt_or_srt_to_markdown(text, "Example")
        self.assertIn("# Example", result)
        self.assertIn("Hello.", result)
        self.assertIn("00:00:00.000", result)

    def test_redacts_signed_urls(self):
        value = "https://files.example.test/a?X-Amz-Signature=signature-value"
        scrubbed = scrub_derived_text(value)
        self.assertNotIn("signature-value", scrubbed)
        self.assertIn("REDACTED_SIGNED_URL", scrubbed)

    def test_redacts_bearer_and_api_key_values(self):
        value = (
            'Authorization: Bearer bearer-value\napi_key="api-value"\n'
            "sk-123456789012345678901234"
        )
        scrubbed = scrub_derived_text(value)
        self.assertNotIn("bearer-value", scrubbed)
        self.assertNotIn("api-value", scrubbed)
        self.assertNotIn("sk-123456789012345678901234", scrubbed)
        self.assertGreaterEqual(scrubbed.count("REDACTED_SECRET"), 2)

    def test_preserves_ordinary_paths_and_timestamp_text(self):
        value = "/Users/example/work/report.txt at 2026-09-04T10:30:00Z"
        scrubbed = scrub_derived_text(value)
        self.assertEqual(scrubbed, value)


if __name__ == "__main__":
    unittest.main()
