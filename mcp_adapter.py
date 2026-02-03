from __future__ import annotations

import os
from typing import Dict, Any

import requests


class MCPAdapter:
    def __init__(self) -> None:
        self.providers = {}
        self.remote_endpoints = {
            "github": os.getenv("MCP_GITHUB_URL", ""),
            "drive": os.getenv("MCP_DRIVE_URL", ""),
        }
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.drive_token = os.getenv("GOOGLE_DRIVE_TOKEN", "")

    def register(self, name: str, provider) -> None:
        self.providers[name] = provider

    def call(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if name in self.providers:
            return self.providers[name](payload)
        if name in self.remote_endpoints and self.remote_endpoints[name]:
            return self._call_remote(self.remote_endpoints[name], payload)
        if name == "github":
            return self._call_github(payload)
        if name == "drive":
            return self._call_drive(payload)
        raise RuntimeError(f"Unknown MCP provider: {name}")

    def list_resources(self, name: str) -> Dict[str, Any]:
        return self.call(name, {"action": "resources"})

    def list_prompts(self, name: str) -> Dict[str, Any]:
        return self.call(name, {"action": "prompts"})

    def list_tools(self, name: str) -> Dict[str, Any]:
        return self.call(name, {"action": "tools"})

    def _call_remote(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _call_github(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.github_token:
            raise RuntimeError("GITHUB_TOKEN not set")
        action = payload.get("action")
        base = "https://api.github.com"
        headers = {"Authorization": f"Bearer {self.github_token}", "Accept": "application/vnd.github+json"}
        if action == "repo":
            owner = payload.get("owner")
            repo = payload.get("repo")
            resp = requests.get(f"{base}/repos/{owner}/{repo}", headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        if action == "issues":
            owner = payload.get("owner")
            repo = payload.get("repo")
            resp = requests.get(f"{base}/repos/{owner}/{repo}/issues", headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        if action == "resources":
            return {"resources": ["repo", "issues"]}
        if action == "prompts":
            return {"prompts": []}
        if action == "tools":
            return {"tools": ["repo", "issues"]}
        raise RuntimeError("Unsupported github action")

    def _call_drive(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.drive_token:
            raise RuntimeError("GOOGLE_DRIVE_TOKEN not set")
        action = payload.get("action")
        base = "https://www.googleapis.com/drive/v3"
        headers = {"Authorization": f"Bearer {self.drive_token}"}
        if action == "files":
            resp = requests.get(f"{base}/files", headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        if action == "resources":
            return {"resources": ["files"]}
        if action == "prompts":
            return {"prompts": []}
        if action == "tools":
            return {"tools": ["files"]}
        raise RuntimeError("Unsupported drive action")
