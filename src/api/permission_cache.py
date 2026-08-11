"""Demo proposal intentionally reviewed by Trace Guardkeeper."""

CACHE_TTL_SECONDS = 600


def cache_authorization(user_id: str, allowed: bool) -> tuple[str, bool, int]:
    """Cache an authorization result until its TTL expires."""
    return user_id, allowed, CACHE_TTL_SECONDS
