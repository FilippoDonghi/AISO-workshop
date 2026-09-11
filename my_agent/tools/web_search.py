from ddgs import DDGS


def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return results.

    Use this tool when you need to find information on the internet,
    look up facts, find URLs, or answer questions about real-world topics.

    Args:
        query: The search query string.

    Returns:
        A list of search results with titles, URLs, and snippets.
    """
    normalized_query = query.strip()
    if not normalized_query:
        return "Error searching: A query is required."
    if len(normalized_query) > 500:
        return "Error searching: The query is too long."

    try:
        results = DDGS().text(normalized_query, max_results=5)
        if not results:
            return "No results found."
        output: list[str] = []
        for result in results:
            output.append(f"Title: {result.get('title', '')}")
            output.append(f"URL: {result.get('href', '')}")
            output.append(f"Snippet: {result.get('body', '')}\n")
        return "\n".join(output)[:10_000]
    except Exception:
        return "Error searching: The search provider request failed."
