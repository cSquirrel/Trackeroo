"""Unit tests for server.py's URL validation and HTTP error handling.

These exercise the error paths in _resolve_base_url() and _request() without
needing a live backend — they monkeypatch the module-level state to isolate
each scenario.

IMPORTANT: server.py must NOT be imported at module level here — the
session-scoped conftest fixture sets TRACKEROO_API_URL before the first
import, and an early import would cache None and break the whole suite.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _server():
    import server
    return server


class TestResolveBaseUrlValidation:
    """TRACKEROO_API_URL env var rejects non-HTTP schemes."""

    @pytest.mark.parametrize("bad_url", [
        "ftp://host:8787",
        "not-a-url",
        "://no-scheme",
        "localhost:8787",
    ])
    def test_rejects_malformed_explicit_url(self, bad_url: str):
        s = _server()
        with patch.object(s, "_EXPLICIT_API_URL", bad_url):
            with pytest.raises(RuntimeError, match="not a valid HTTP URL"):
                s._resolve_base_url()

    def test_accepts_http_url(self):
        s = _server()
        with patch.object(s, "_EXPLICIT_API_URL", "http://example.com:8787"):
            assert s._resolve_base_url() == "http://example.com:8787"

    def test_accepts_https_url(self):
        s = _server()
        with patch.object(s, "_EXPLICIT_API_URL", "https://example.com"):
            assert s._resolve_base_url() == "https://example.com"

    def test_strips_trailing_slash(self):
        s = _server()
        with patch.object(s, "_EXPLICIT_API_URL", "http://example.com:8787/"):
            assert s._resolve_base_url() == "http://example.com:8787"


class TestRequestErrors:
    """_request() surfaces clear errors for network and URL problems."""

    def test_unreachable_server(self):
        s = _server()
        with patch.object(s, "_EXPLICIT_API_URL", "http://localhost:1"):
            with patch.object(s, "_PROJECT_PATH", None):
                with pytest.raises(RuntimeError, match="Could not reach Trackeroo API"):
                    s._request("GET", "/api/health")

    def test_invalid_url_caught(self):
        s = _server()
        with patch.object(s, "_EXPLICIT_API_URL", "http://localhost:notaport"):
            with patch.object(s, "_PROJECT_PATH", None):
                with pytest.raises(RuntimeError, match="Malformed Trackeroo API URL"):
                    s._request("GET", "/api/health")

    def test_http_error_includes_status(self, backend_server):
        """A 404 from the backend produces a RuntimeError with the status code."""
        s = _server()
        with pytest.raises(RuntimeError, match="404"):
            s._request("GET", "/api/nonexistent-endpoint")
