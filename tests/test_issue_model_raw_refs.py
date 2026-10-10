"""exp/gpt-4o-mini: code names taken from the raw issue without the model, and A2 rounds that go on without new queries."""
import sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src" / "modules")]
from src.modules.issue_model import raw_code_refs


class RawRefsTest(unittest.TestCase):
    def test_frames_and_fenced_identifiers(self):
        text = ('Crash:\n```\nTraceback (most recent call last):\n  File "/x/django/db/models/query.py", line 10, in get_or_create\n'
                "    obj = self.model._base_manager.filter(**kw)\nValueError: bad\n```\nSee `QuerySet.update` too, ignore this_text outside.")
        refs = raw_code_refs(text)
        self.assertEqual(refs[:2], ["query", "get_or_create"])            # traceback frame: module, function
        self.assertIn("self.model._base_manager.filter", refs)             # dotted name in the fenced block
        self.assertIn("ValueError", refs)                                  # CamelCase
        self.assertNotIn("this_text", refs)                                # outside code: left to the model and backticks


if __name__ == "__main__":
    unittest.main()
