"""Shared safety boundaries for network and local-file tools."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ATTACHMENTS_ROOT = PROJECT_ROOT / "benchmark" / "attachments"

MAX_WEB_BYTES = 2_000_000
MAX_PDF_BYTES = 15_000_000
MAX_IMAGE_BYTES = 8_000_000
MAX_REDIRECTS = 3

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home", ".lan")
_ALLOWED_MEDIA_TYPES = {
    "application/json",
    "application/xhtml+xml",
    "application/xml",
}


class SafetyError(ValueError):
    """Raised when a tool request crosses a configured safety boundary."""


@dataclass(frozen=True)
class FetchedContent:
    """A bounded response body returned by :func:`fetch_public_content`."""

    body: bytes
    content_type: str
    encoding: str
    final_url: str


def resolve_attachment(
    file_path: str,
    *,
    allowed_suffixes: set[str],
    max_bytes: int,
) -> Path:
    """Resolve a regular benchmark attachment without allowing path escape."""
    if not file_path or "\x00" in file_path:
        raise SafetyError("An attachment path is required.")

    root = ATTACHMENTS_ROOT.resolve(strict=True)
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate

    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SafetyError("The requested attachment does not exist.") from exc

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SafetyError(
            "The requested file is outside the allowed benchmark attachment directory."
        ) from exc

    if not resolved.is_file():
        raise SafetyError("The requested attachment is not a regular file.")

    normalized_suffixes = {suffix.lower() for suffix in allowed_suffixes}
    if resolved.suffix.lower() not in normalized_suffixes:
        allowed = ", ".join(sorted(normalized_suffixes))
        raise SafetyError(f"Unsupported attachment type; expected one of: {allowed}.")

    try:
        size = resolved.stat().st_size
    except OSError as exc:
        raise SafetyError("The requested attachment cannot be inspected.") from exc
    if size > max_bytes:
        raise SafetyError(f"The requested attachment exceeds the {max_bytes}-byte limit.")

    return resolved


def validate_public_url(url: str) -> str:
    """Validate an HTTP(S) URL and reject non-public DNS destinations."""
    if not isinstance(url, str) or not url.strip():
        raise SafetyError("A URL is required.")
    if len(url) > 2_048:
        raise SafetyError("The URL is too long.")

    normalized = url.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise SafetyError("Only HTTP and HTTPS URLs are supported.")
    if not parsed.hostname:
        raise SafetyError("The URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise SafetyError("Credentials embedded in URLs are not allowed.")

    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise SafetyError("The URL contains an invalid port.") from exc

    expected_port = 443 if parsed.scheme == "https" else 80
    if explicit_port is not None and explicit_port != expected_port:
        raise SafetyError("Only the standard HTTP and HTTPS ports are allowed.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in _BLOCKED_HOSTS or hostname.endswith(_BLOCKED_HOST_SUFFIXES):
        raise SafetyError("Local and internal hostnames are not allowed.")

    try:
        literal_address = ipaddress.ip_address(hostname.split("%", maxsplit=1)[0])
    except ValueError:
        literal_address = None

    if literal_address is not None:
        addresses = {literal_address}
    else:
        try:
            records = socket.getaddrinfo(
                hostname,
                explicit_port or expected_port,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise SafetyError("The hostname could not be resolved safely.") from exc
        addresses = {
            ipaddress.ip_address(record[4][0].split("%", maxsplit=1)[0]) for record in records
        }

    if not addresses or any(not address.is_global for address in addresses):
        raise SafetyError("The URL resolves to a non-public network address.")

    return normalized


def fetch_public_content(
    url: str,
    *,
    max_bytes: int = MAX_WEB_BYTES,
    max_redirects: int = MAX_REDIRECTS,
) -> FetchedContent:
    """Fetch a bounded text-like response while validating each redirect."""
    current_url = validate_public_url(url)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/json,application/xml;q=0.9,text/plain;q=0.8",
        "User-Agent": "AISO-workshop-agent/1.0 (+https://github.com/FilippoDonghi/AISO-workshop)",
    }

    for redirect_count in range(max_redirects + 1):
        response = requests.get(
            current_url,
            allow_redirects=False,
            headers=headers,
            stream=True,
            timeout=(3.05, 15),
        )
        try:
            if response.status_code in _REDIRECT_STATUSES:
                if redirect_count >= max_redirects:
                    raise SafetyError("The webpage exceeded the redirect limit.")
                location = response.headers.get("Location")
                if not location:
                    raise SafetyError("The webpage returned an invalid redirect.")
                current_url = validate_public_url(urljoin(current_url, location))
                continue

            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            media_type = content_type.partition(";")[0].strip().lower()
            if media_type and not (
                media_type.startswith("text/") or media_type in _ALLOWED_MEDIA_TYPES
            ):
                raise SafetyError(f"Unsupported response content type: {media_type}.")

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError as exc:
                    raise SafetyError("The webpage returned an invalid content length.") from exc
                if declared_size > max_bytes:
                    raise SafetyError(f"The webpage exceeds the {max_bytes}-byte limit.")

            chunks: list[bytes] = []
            downloaded = 0
            for chunk in response.iter_content(chunk_size=65_536):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    raise SafetyError(f"The webpage exceeds the {max_bytes}-byte limit.")
                chunks.append(chunk)

            return FetchedContent(
                body=b"".join(chunks),
                content_type=media_type,
                encoding=response.encoding or "utf-8",
                final_url=current_url,
            )
        finally:
            response.close()

    raise SafetyError("The webpage could not be fetched safely.")
