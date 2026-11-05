"""Reusable OpenAPI `responses=` entries, so /docs shows each route's real error codes.

Usage:
    @router.patch("/{team_id}", responses=errors(401, 403, (404, "Team or league not found")))

Pass a bare status code for the default description, or a (code, description) tuple
to say what exactly was not found / conflicted. 422 is added by FastAPI automatically
for routes with parameters or a body, so it is only listed here when we add our own meaning.
"""

from typing import Any

from pydantic import BaseModel


class ErrorOut(BaseModel):
    """Body of every error raised with HTTPException."""

    detail: str


_DEFAULTS = {
    400: "Bad request",
    401: "Not authenticated: missing, invalid, expired or logged-out token",
    403: "Admin privileges required",
    404: "Not found",
    409: "Conflict with existing data",
    429: "Rate limit exceeded; see the Retry-After header",
    503: "Service temporarily unavailable",
}

# Shown on every route of a router that has the general API rate limit.
RATE_LIMITED: dict[int | str, dict[str, Any]] = {
    429: {"description": _DEFAULTS[429], "model": ErrorOut},
}


def errors(*codes: int | tuple[int, str]) -> dict[int | str, dict[str, Any]]:
    """Build a `responses=` dict from status codes or (code, description) pairs."""
    out: dict[int | str, dict[str, Any]] = {}
    for item in codes:
        code, description = item if isinstance(item, tuple) else (item, _DEFAULTS[item])
        out[code] = {"description": description, "model": ErrorOut}
    return out
