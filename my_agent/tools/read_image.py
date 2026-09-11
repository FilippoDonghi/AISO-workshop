import base64

from google import genai

from .safety import MAX_IMAGE_BYTES, SafetyError, resolve_attachment

_IMAGE_MIME_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
MAX_QUESTION_CHARS = 2_000


def read_image(file_path: str, question: str) -> str:
    """Analyze an image file and answer a question about it.

    Use this tool whenever a question mentions an attached image,
    a .png or .jpg file, or any visual content that needs to be interpreted.

    Args:
        file_path: The path to the image file (e.g. 'benchmark/attachments/14.png').
        question: The specific question to answer about the image.

    Returns:
        A description or answer based on the image content.
    """
    try:
        if not question or not question.strip():
            return "Error reading image: A question is required."
        if len(question) > MAX_QUESTION_CHARS:
            return "Error reading image: The question is too long."

        attachment = resolve_attachment(
            file_path,
            allowed_suffixes=set(_IMAGE_MIME_TYPES),
            max_bytes=MAX_IMAGE_BYTES,
        )
        image_data = base64.b64encode(attachment.read_bytes()).decode("ascii")
        mime = _IMAGE_MIME_TYPES[attachment.suffix.lower()]

        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": image_data}},
                        {"text": question.strip()},
                    ],
                }
            ],
        )
        return response.text or "Error reading image: The model returned no text."
    except (SafetyError, OSError) as exc:
        return f"Error reading image: {exc!s}"
    except Exception:
        return "Error reading image: Image analysis failed."
