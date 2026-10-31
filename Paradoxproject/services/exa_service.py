import os
import logging
from dotenv import load_dotenv
import requests

load_dotenv()

logger = logging.getLogger(__name__)


class ExaConfigError(Exception):
    """Raised when the Exa API configuration is missing or invalid."""
    pass


class ExaAPIError(Exception):
    """Raised when upstream Exa API communication fails."""
    pass


EXA_SEARCH_ENDPOINT = "https://api.exa.ai/search"


def search_web(query: str) -> list:
    """
    Search the web using Exa's official Search API.

    Args:
        query: Non-empty search query string.

    Returns:
        list: Structured search results with title, url, published_date, text.

    Raises:
        ExaConfigError: When EXA_API_KEY is not set or empty.
        ExaAPIError: When the Exa API call fails upstream.
        ValueError: When query is invalid.
    """
    # Validate input
    if query is None or not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must be a non-empty text string.")

    query = query.strip()

    # Read API key from environment (never logged or returned)
    api_key = os.getenv("EXA_API_KEY")
    if not api_key or not api_key.strip():
        logger.error("Exa API key is missing from environment variables.")
        raise ExaConfigError("EXA_API_KEY is not configured.")

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "contents": {
            "highlights": True
        }
    }

    try:
        response = requests.post(
            EXA_SEARCH_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.exceptions.Timeout as exc:
        logger.error("Exa API request timed out.")
        raise ExaAPIError("The search service timed out. Please try again shortly.") from exc
    except requests.exceptions.ConnectionError as exc:
        logger.error("Exa API connection error.")
        raise ExaAPIError("Unable to connect to the search service. Please check your connection.") from exc
    except requests.exceptions.RequestException as exc:
        logger.error(f"Exa API request error: {type(exc).__name__}")
        raise ExaAPIError("An error occurred while communicating with the search service.") from exc

    # Handle HTTP error status codes
    if response.status_code in (401, 403):
        logger.error(f"Exa API authentication error (status {response.status_code}).")
        raise ExaAPIError("Authentication error with the search service.")

    if response.status_code == 429:
        logger.warning("Exa API rate limit exceeded.")
        raise ExaAPIError("The search service is rate-limited. Please try again shortly.")

    if response.status_code >= 400:
        logger.error(f"Exa API error (status {response.status_code}).")
        raise ExaAPIError(f"The search service returned an error (status {response.status_code}).")

    # Parse JSON response
    try:
        data = response.json()
    except ValueError as exc:
        logger.error("Exa API returned invalid JSON.")
        raise ExaAPIError("The search service returned an invalid response.") from exc

    # Extract structured results
    results = []
    raw_results = data.get("results", []) if isinstance(data, dict) else []

    for item in raw_results:
        if not isinstance(item, dict):
            continue
        result = {
            "title": item.get("title") or "",
            "url": item.get("url") or "",
            "published_date": item.get("publishedDate") or item.get("published_date") or None,
            "text": item.get("text") or (item.get("highlights") or [""])[0] or "",
        }
        results.append(result)

    return results