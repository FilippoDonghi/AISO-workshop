from bs4 import BeautifulSoup

from .safety import SafetyError, fetch_public_content

MAX_EXTRACTED_TEXT_CHARS = 10_000


def fetch_webpage(url: str) -> str:
    """Fetch a webpage and return its text content.

    Use this tool when you have a specific URL and need to read its content.
    Use this after web_search to read a specific result, or when a question
    provides a URL directly.

    Args:
        url: The full URL of the webpage to fetch.

    Returns:
        The text content of the webpage (truncated to 10000 characters).
    """
    try:
        content = fetch_public_content(url)
        soup = BeautifulSoup(content.body, "html.parser", from_encoding=content.encoding)

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        if len(text) > MAX_EXTRACTED_TEXT_CHARS:
            text = text[:MAX_EXTRACTED_TEXT_CHARS] + "\n...(truncated)"
        return text
    except (SafetyError, OSError) as exc:
        return f"Error fetching webpage: {exc!s}"
    except Exception:
        return "Error fetching webpage: The remote request failed."
