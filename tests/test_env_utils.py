from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.utils.env import load_env_file


class EnvUtilsTest(unittest.TestCase):
    def test_load_env_file_sets_missing_values_without_overriding_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "OPENAI_MODEL=gpt-5-mini\n"
                "EXISTING=from-file\n"
                "QUOTED='hello world'\n",
                encoding="utf-8",
            )
            os.environ["EXISTING"] = "from-env"
            self.addCleanup(os.environ.pop, "OPENAI_MODEL", None)
            self.addCleanup(os.environ.pop, "EXISTING", None)
            self.addCleanup(os.environ.pop, "QUOTED", None)

            loaded = load_env_file(env_file)

        self.assertEqual(os.environ["OPENAI_MODEL"], "gpt-5-mini")
        self.assertEqual(os.environ["EXISTING"], "from-env")
        self.assertEqual(os.environ["QUOTED"], "hello world")
        self.assertEqual(loaded["EXISTING"], "from-env")


if __name__ == "__main__":
    unittest.main()
