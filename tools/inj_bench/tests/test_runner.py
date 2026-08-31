"""Builtin runner and HTTP adapter tests."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

import pytest

from inj_bench.corpus import load_corpus
from inj_bench.runner import _verdict_from_http_payload, run_benchmark


def test_builtin_scores_shipped_scanners():
    corpus = load_corpus("sampler")
    report = run_benchmark(corpus, target="builtin")
    assert report.metrics.total == len(corpus.entries)
    assert report.metrics.detection_rate >= 0.9
    assert report.metrics.false_positive_rate == 0.0


def test_verdict_from_findings_array():
    caught, actual, sev, _ = _verdict_from_http_payload(
        {
            "findings": [
                {"scanner": "custom", "category": "injection", "severity": 0.9}
            ]
        }
    )
    assert caught is True
    assert actual == "block"
    assert sev >= 0.9


def test_verdict_from_effective_block():
    caught, actual, _, _ = _verdict_from_http_payload({"effective_block": True})
    assert caught is True
    assert actual == "block"


def test_http_scan_live():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            blocked = "ignore all previous" in body.get("text", "").lower()
            payload = {"blocked": blocked, "findings": []}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        corpus = load_corpus("sampler")
        report = run_benchmark(
            corpus,
            target=f"http://127.0.0.1:{port}/scan",
        )
        assert report.metrics.detection_rate > 0
    finally:
        server.shutdown()
