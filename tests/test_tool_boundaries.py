from __future__ import annotations

import importlib

from my_agent.tools.fetch_webpage import fetch_webpage
from my_agent.tools.read_pdf import read_pdf


def test_pdf_reader_accepts_benchmark_attachment() -> None:
    text = read_pdf("benchmark/attachments/7.pdf")
    assert len(text) > 100
    assert not text.startswith("Error")


def test_pdf_reader_rejects_external_path() -> None:
    assert "outside" in read_pdf("/etc/passwd")


def test_web_fetch_rejects_non_http_scheme() -> None:
    assert "Only HTTP and HTTPS" in fetch_webpage("file:///etc/passwd")


def test_image_reader_rejects_external_path_before_model_call(monkeypatch) -> None:
    image_module = importlib.import_module("my_agent.tools.read_image")

    def unexpected_client_call():
        raise AssertionError("Gemini must not receive a rejected local file")

    monkeypatch.setattr(image_module.genai, "Client", unexpected_client_call)
    result = image_module.read_image("/etc/passwd", "Describe this image")
    assert "outside" in result
