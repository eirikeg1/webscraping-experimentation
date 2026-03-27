import httpx

_client: httpx.AsyncClient | None = None

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


async def get_client() -> httpx.AsyncClient:
    """Get or create the shared async HTTP client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
    return _client


async def close_client() -> None:
    """Close the shared HTTP client."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
