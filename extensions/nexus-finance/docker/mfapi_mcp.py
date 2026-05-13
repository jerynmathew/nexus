"""MFapi.in MCP server — mutual fund NAV data wrapper."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MFAPI_BASE = os.environ.get("MFAPI_BASE_URL", "https://api.mfapi.in")

mcp = FastMCP("nexus-finance-mfapi", stateless_http=True, json_response=True)

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = httpx.AsyncClient(base_url=MFAPI_BASE, timeout=30.0)
    return _client


@mcp.tool()
async def search_funds(query: str) -> list[dict[str, str]]:
    """Search mutual fund schemes by name.

    Args:
        query: Fund name or partial match (e.g. 'parag parikh', 'nifty 50').

    Returns:
        List of matching schemes with schemeCode and schemeName.
    """
    client = await _get_client()
    resp = await client.get("/mf/search", params={"q": query})
    resp.raise_for_status()
    results = resp.json()
    if isinstance(results, list):
        return [
            {"schemeCode": str(r.get("schemeCode", "")), "schemeName": r.get("schemeName", "")}
            for r in results[:20]
        ]
    return []


@mcp.tool()
async def get_nav(scheme_code: str) -> dict[str, Any]:
    """Get current and historical NAV for a mutual fund scheme.

    Args:
        scheme_code: The AMFI scheme code (e.g. '119551' for Parag Parikh Flexi Cap).

    Returns:
        Scheme metadata and NAV history.
    """
    client = await _get_client()
    resp = await client.get(f"/mf/{scheme_code}")
    resp.raise_for_status()
    return dict(resp.json())


@mcp.tool()
async def get_latest_nav(scheme_code: str) -> dict[str, Any]:
    """Get only the latest NAV for a scheme (faster than full history).

    Args:
        scheme_code: The AMFI scheme code.

    Returns:
        Latest NAV with date.
    """
    client = await _get_client()
    resp = await client.get(f"/mf/{scheme_code}/latest")
    resp.raise_for_status()
    data = resp.json()
    meta = data.get("meta", {})
    nav_data = data.get("data", [{}])
    latest = nav_data[0] if nav_data else {}
    return {
        "scheme_code": meta.get("scheme_code", scheme_code),
        "scheme_name": meta.get("scheme_name", ""),
        "scheme_category": meta.get("scheme_category", ""),
        "nav": latest.get("nav", ""),
        "date": latest.get("date", ""),
    }


@mcp.tool()
async def get_scheme_details(scheme_code: str) -> dict[str, Any]:
    """Get scheme metadata (fund house, category, type) without full NAV history.

    Args:
        scheme_code: The AMFI scheme code.

    Returns:
        Scheme metadata.
    """
    client = await _get_client()
    resp = await client.get(f"/mf/{scheme_code}/latest")
    resp.raise_for_status()
    data = resp.json()
    return dict(data.get("meta", {}))


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8002)
