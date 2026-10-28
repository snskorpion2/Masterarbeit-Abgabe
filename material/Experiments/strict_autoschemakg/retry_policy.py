"""Explicit repair-only transient transport predicate, never outcome-based."""
from urllib.error import HTTPError, URLError


def transient_transport(error):
    if isinstance(error, RuntimeError) and isinstance(error.__cause__, HTTPError):
        return transient_transport(error.__cause__)
    if isinstance(error, HTTPError):
        return error.code in (408, 429, 500, 502, 503, 504)
    if isinstance(error, URLError):
        return isinstance(error.reason, (TimeoutError, ConnectionError))
    return isinstance(error, (TimeoutError, ConnectionError))
