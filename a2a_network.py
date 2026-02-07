from __future__ import annotations

import json
import uuid
import time
import threading
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Tuple


def _parse_peers(raw: str) -> Dict[str, Tuple[str, int]]:
    peers: Dict[str, Tuple[str, int]] = {}
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            continue
        name, addr = item.split("=", 1)
        name = name.strip()
        addr = addr.strip()
        if not name or not addr:
            continue
        if ":" not in addr:
            continue
        host, port_str = addr.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            continue
        peers[name] = (host, port)
    return peers


class A2ANetwork:
    def __init__(
        self,
        bus,
        host: str,
        port: int,
        shared_secret: str,
        peers_raw: str,
        on_message=None,
    ) -> None:
        self.bus = bus
        self.host = host
        self.port = port
        self.shared_secret = shared_secret
        self.peers = _parse_peers(peers_raw)
        self.on_message = on_message
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server:
            return
        handler = self._make_handler()
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None

    def send(self, peer: str, sender: str, receiver: str, message, retries: int = 2, backoff_s: float = 0.5) -> str:
        if peer not in self.peers:
            raise RuntimeError(f"Unknown peer: {peer}")
        host, port = self.peers[peer]
        payload = self._normalize_payload(sender, receiver, message)
        payload["shared_secret"] = self.shared_secret
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://{host}:{port}/a2a",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        last_err = None
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"A2A send failed: {resp.status}")
                    body = resp.read().decode("utf-8", errors="ignore")
                    try:
                        ack = json.loads(body) if body else {}
                    except Exception:
                        ack = {}
                    return ack.get("message_id") or payload.get("message_id") or ""
            except (urllib.error.URLError, RuntimeError) as exc:
                last_err = exc
                if attempt < retries:
                    time.sleep(backoff_s * (attempt + 1))
                else:
                    raise RuntimeError(f"A2A send failed: {exc}") from exc
        raise RuntimeError(f"A2A send failed: {last_err}")

    def broadcast(self, sender: str, receiver: str, message: str) -> None:
        for peer in self.peers:
            self.send(peer, sender, receiver, message)

    def _normalize_payload(self, sender: str, receiver: str, message):
        payload = {}
        if isinstance(message, dict):
            payload.update(message)
        else:
            payload["message"] = message
        payload.setdefault("sender", sender)
        payload.setdefault("receiver", receiver)
        if "message" not in payload and "content" in payload:
            payload["message"] = payload.get("content")
        payload.setdefault("message_id", str(uuid.uuid4()))
        payload.setdefault("thread_id", payload.get("message_id"))
        payload.setdefault("trace_id", str(uuid.uuid4()))
        payload.setdefault("timestamp", time.time())
        return payload

    def _make_handler(self):
        bus = self.bus
        shared_secret = self.shared_secret
        on_message = self.on_message

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/a2a":
                    self.send_response(404)
                    self.end_headers()
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:
                    self.send_response(400)
                    self.end_headers()
                    return
                if shared_secret and payload.get("shared_secret") != shared_secret:
                    self.send_response(403)
                    self.end_headers()
                    return
                sender = payload.get("sender") or "unknown"
                receiver = payload.get("receiver") or "local"
                if "message" not in payload and "content" in payload:
                    payload["message"] = payload.get("content")
                if "message_id" not in payload:
                    payload["message_id"] = str(uuid.uuid4())
                if "thread_id" not in payload:
                    payload["thread_id"] = payload.get("message_id")
                if "trace_id" not in payload:
                    payload["trace_id"] = str(uuid.uuid4())
                if "timestamp" not in payload:
                    payload["timestamp"] = time.time()
                bus.send(sender, receiver, json.dumps(payload, separators=(",", ":")))
                if on_message:
                    try:
                        on_message(sender, receiver, json.dumps(payload, separators=(",", ":")))
                    except Exception:
                        pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                body = json.dumps({"ok": True, "message_id": payload.get("message_id")}).encode("utf-8")
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        return Handler
