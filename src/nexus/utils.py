from __future__ import annotations


def parse_key_value_params(text: str) -> dict[str, str]:
    """Parse ``key=value`` tokens from whitespace-separated text."""
    params: dict[str, str] = {}
    for token in text.split():
        if "=" in token:
            key, _, value = token.partition("=")
            params[key.lower()] = value
    return params
