from __future__ import annotations

import socket
from pathlib import Path

import pytest

from my_agent.tools import safety


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.encoding = "utf-8"
        self._chunks = chunks or []
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int) -> list[bytes]:
        del chunk_size
        return self._chunks

    def close(self) -> None:
        self.closed = True


def public_dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
    del args, kwargs
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://user:password@example.com",
        "http://example.com:8080",
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]",
    ],
)
def test_validate_public_url_blocks_unsafe_destinations(url: str) -> None:
    with pytest.raises(safety.SafetyError):
        safety.validate_public_url(url)


def test_validate_public_url_accepts_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(safety.socket, "getaddrinfo", public_dns)
    assert safety.validate_public_url("https://example.com/page") == ("https://example.com/page")


def test_validate_public_url_rejects_mixed_public_private_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mixed_dns(*args: object, **kwargs: object) -> list[tuple[object, ...]]:
        del args, kwargs
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]

    monkeypatch.setattr(safety.socket, "getaddrinfo", mixed_dns)
    with pytest.raises(safety.SafetyError, match="non-public"):
        safety.validate_public_url("https://example.com")


def test_fetch_revalidates_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(
        status_code=302,
        headers={"Location": "http://127.0.0.1/admin"},
    )
    monkeypatch.setattr(safety.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(safety.requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(safety.SafetyError, match="non-public"):
        safety.fetch_public_content("https://example.com")
    assert response.closed


def test_fetch_rejects_declared_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(
        headers={"Content-Type": "text/html", "Content-Length": "101"},
    )
    monkeypatch.setattr(safety.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(safety.requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(safety.SafetyError, match="exceeds"):
        safety.fetch_public_content("https://example.com", max_bytes=100)


def test_fetch_rejects_stream_that_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(
        headers={"Content-Type": "text/plain"},
        chunks=[b"a" * 60, b"b" * 41],
    )
    monkeypatch.setattr(safety.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(safety.requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(safety.SafetyError, match="exceeds"):
        safety.fetch_public_content("https://example.com", max_bytes=100)


def test_fetch_rejects_binary_content(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(
        headers={"Content-Type": "application/octet-stream"},
        chunks=[b"binary"],
    )
    monkeypatch.setattr(safety.socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(safety.requests, "get", lambda *args, **kwargs: response)

    with pytest.raises(safety.SafetyError, match="content type"):
        safety.fetch_public_content("https://example.com")


def test_attachment_resolution_stays_in_allowed_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attachments = tmp_path / "benchmark" / "attachments"
    attachments.mkdir(parents=True)
    allowed = attachments / "sample.pdf"
    allowed.write_bytes(b"small")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"private")
    monkeypatch.setattr(safety, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(safety, "ATTACHMENTS_ROOT", attachments)

    assert (
        safety.resolve_attachment(
            "benchmark/attachments/sample.pdf",
            allowed_suffixes={".pdf"},
            max_bytes=10,
        )
        == allowed
    )

    with pytest.raises(safety.SafetyError, match="outside"):
        safety.resolve_attachment(
            str(outside),
            allowed_suffixes={".pdf"},
            max_bytes=10,
        )


def test_attachment_resolution_rejects_traversal_and_symlink_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attachments = tmp_path / "benchmark" / "attachments"
    attachments.mkdir(parents=True)
    outside = tmp_path / "benchmark" / "outside.pdf"
    outside.write_bytes(b"private")
    escape_link = attachments / "escape.pdf"
    escape_link.symlink_to(outside)
    monkeypatch.setattr(safety, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(safety, "ATTACHMENTS_ROOT", attachments)

    for unsafe_path in (
        "benchmark/attachments/../outside.pdf",
        "benchmark/attachments/escape.pdf",
    ):
        with pytest.raises(safety.SafetyError, match="outside"):
            safety.resolve_attachment(
                unsafe_path,
                allowed_suffixes={".pdf"},
                max_bytes=10,
            )


def test_attachment_resolution_rejects_type_and_size(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attachments = tmp_path / "benchmark" / "attachments"
    attachments.mkdir(parents=True)
    text_file = attachments / "notes.txt"
    text_file.write_bytes(b"notes")
    large_pdf = attachments / "large.pdf"
    large_pdf.write_bytes(b"123456")
    monkeypatch.setattr(safety, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(safety, "ATTACHMENTS_ROOT", attachments)

    with pytest.raises(safety.SafetyError, match="Unsupported"):
        safety.resolve_attachment(
            str(text_file),
            allowed_suffixes={".pdf"},
            max_bytes=10,
        )
    with pytest.raises(safety.SafetyError, match="exceeds"):
        safety.resolve_attachment(
            str(large_pdf),
            allowed_suffixes={".pdf"},
            max_bytes=5,
        )
