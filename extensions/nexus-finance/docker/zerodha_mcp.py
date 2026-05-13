"""Zerodha Kite API MCP server — thin wrapper over pykiteconnect."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from kiteconnect import KiteConnect
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KITE_API_KEY = os.environ.get("KITE_API_KEY", "")
KITE_API_SECRET = os.environ.get("KITE_API_SECRET", "")
KITE_ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN", "")

mcp = FastMCP("nexus-finance-zerodha", stateless_http=True, json_response=True)

_kite: KiteConnect | None = None


def _get_kite() -> KiteConnect:
    global _kite  # noqa: PLW0603
    if _kite is None:
        _kite = KiteConnect(api_key=KITE_API_KEY)
        if KITE_ACCESS_TOKEN:
            _kite.set_access_token(KITE_ACCESS_TOKEN)
    return _kite


@mcp.tool()
def get_login_url() -> str:
    """Get the Zerodha Kite login URL for OAuth2 authentication."""
    kite = _get_kite()
    return str(kite.login_url())


@mcp.tool()
def exchange_token(request_token: str) -> dict[str, Any]:
    """Exchange a request_token for an access_token after OAuth2 redirect.

    Args:
        request_token: Token from the OAuth2 redirect callback query param.

    Returns:
        Session data including access_token.
    """
    kite = _get_kite()
    session = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
    if "access_token" in session:
        kite.set_access_token(session["access_token"])
    return dict(session)


@mcp.tool()
def get_holdings() -> list[dict[str, Any]]:
    """Fetch equity and MF holdings from Zerodha portfolio."""
    kite = _get_kite()
    holdings = kite.holdings()
    return [dict(h) for h in holdings]


@mcp.tool()
def get_positions() -> dict[str, list[dict[str, Any]]]:
    """Fetch current open positions (net and day)."""
    kite = _get_kite()
    positions = kite.positions()
    return {
        "net": [dict(p) for p in positions.get("net", [])],
        "day": [dict(p) for p in positions.get("day", [])],
    }


@mcp.tool()
def get_profile() -> dict[str, Any]:
    """Fetch user profile information."""
    kite = _get_kite()
    return dict(kite.profile())


@mcp.tool()
def check_token_valid() -> dict[str, Any]:
    """Check if the current access token is valid by fetching the profile."""
    kite = _get_kite()
    try:
        profile = kite.profile()
        return {"valid": True, "user_name": profile.get("user_name", "")}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


@mcp.tool()
def set_access_token(access_token: str) -> dict[str, str]:
    """Update the access token for this session (token rotates daily).

    Args:
        access_token: New access token from OAuth2 flow.
    """
    kite = _get_kite()
    kite.set_access_token(access_token)
    return {"status": "ok"}


@mcp.tool()
def generate_checksum(request_token: str) -> str:
    """Generate SHA256 checksum for Kite token exchange.

    Args:
        request_token: The request token from OAuth2 redirect.

    Returns:
        Hex digest of sha256(api_key + request_token + api_secret).
    """
    raw = KITE_API_KEY + request_token + KITE_API_SECRET
    return hashlib.sha256(raw.encode()).hexdigest()


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
