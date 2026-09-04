from __future__ import annotations

import unittest

from work_corpus.util import parse_date_hint, vtt_or_srt_to_markdown


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


if __name__ == "__main__":
    unittest.main()
