import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app as app_mod


class TestToolsAllowlist(unittest.TestCase):
    def setUp(self):
        self.app = app_mod.AgentApp.__new__(app_mod.AgentApp)
        self._old = os.environ.get("AGENTIC_ALLOWED_SHELL")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("AGENTIC_ALLOWED_SHELL", None)
        else:
            os.environ["AGENTIC_ALLOWED_SHELL"] = self._old

    def test_shell_allowlist_blocks(self):
        os.environ["AGENTIC_ALLOWED_SHELL"] = "git,python"
        self.assertTrue(self.app._shell_allowed("git status"))
        self.assertTrue(self.app._shell_allowed("python -V"))
        self.assertFalse(self.app._shell_allowed("curl http://example.com"))

    def test_shell_allowlist_empty_allows(self):
        os.environ["AGENTIC_ALLOWED_SHELL"] = ""
        self.assertTrue(self.app._shell_allowed("anything"))


if __name__ == "__main__":
    unittest.main()
