import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from a2a_network import A2ANetwork


class DummyBus:
    def send(self, *_args, **_kwargs):
        return None


class TestA2APayload(unittest.TestCase):
    def setUp(self):
        self.net = A2ANetwork(
            bus=DummyBus(),
            host="127.0.0.1",
            port=9451,
            shared_secret="",
            peers_raw="",
        )

    def test_normalize_payload_string(self):
        payload = self.net._normalize_payload("alice", "bob", "hello")
        self.assertEqual(payload["sender"], "alice")
        self.assertEqual(payload["receiver"], "bob")
        self.assertEqual(payload["message"], "hello")
        self.assertIn("message_id", payload)
        self.assertIn("thread_id", payload)
        self.assertIn("trace_id", payload)
        self.assertIn("timestamp", payload)

    def test_normalize_payload_dict(self):
        payload = self.net._normalize_payload("alice", "bob", {"content": "hello"})
        self.assertEqual(payload["message"], "hello")
        self.assertEqual(payload["sender"], "alice")
        self.assertEqual(payload["receiver"], "bob")


if __name__ == "__main__":
    unittest.main()
