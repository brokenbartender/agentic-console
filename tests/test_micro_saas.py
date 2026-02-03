import unittest
from micro_saas_tools import parse_assumption, pricing_simulator


class TestMicroSaasTools(unittest.TestCase):
    def test_parse_assumption(self):
        a = parse_assumption("SaaS market | $390B | unverified | source")
        self.assertEqual(a.label, "SaaS market")
        self.assertEqual(a.status, "unverified")

    def test_pricing_simulator(self):
        out = pricing_simulator(20.0, 1000.0)
        self.assertIn("Customers needed", out)


if __name__ == "__main__":
    unittest.main()
