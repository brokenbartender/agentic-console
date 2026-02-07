import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.schemas import VerifySchema


class TestVerifySchema(unittest.TestCase):
    def test_verify_schema_defaults(self):
        verify = VerifySchema(type="output_contains")
        self.assertEqual(verify.type, "output_contains")
        self.assertEqual(verify.params, {})

    def test_verify_schema_params(self):
        verify = VerifySchema(type="test_passes", params={"command": "python -m pytest"})
        self.assertIn("command", verify.params)
        self.assertEqual(verify.params["command"], "python -m pytest")


if __name__ == "__main__":
    unittest.main()
