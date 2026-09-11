import pymupdf

from .safety import MAX_PDF_BYTES, SafetyError, resolve_attachment

MAX_EXTRACTED_TEXT_CHARS = 100_000


def read_pdf(file_path: str) -> str:
    """Read a PDF file and return all of its text content.

    Use this tool whenever a question references an attached file or PDF.
    Pass the exact file path mentioned in the question.

    Args:
        file_path: The path to the PDF file to read.

    Returns:
        The full text content of the PDF.
    """
    try:
        attachment = resolve_attachment(
            file_path,
            allowed_suffixes={".pdf"},
            max_bytes=MAX_PDF_BYTES,
        )
        text_parts: list[str] = []
        extracted_chars = 0
        with pymupdf.open(str(attachment)) as document:
            for page in document:
                page_text = page.get_text()
                remaining = MAX_EXTRACTED_TEXT_CHARS - extracted_chars
                if len(page_text) > remaining:
                    text_parts.append(page_text[:remaining])
                    text_parts.append("\n...(truncated)")
                    break
                text_parts.append(page_text)
                extracted_chars += len(page_text)
        return "".join(text_parts)
    except (SafetyError, OSError, RuntimeError, ValueError) as exc:
        return f"Error reading PDF: {exc!s}"
