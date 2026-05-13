from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoldPrice:
    city: str
    gold_22k: float | None
    gold_24k: float | None
    currency: str = "INR"


def parse_goodreturns_html(html: str, city: str) -> GoldPrice | None:
    price_22k = _extract_price(html, "22")
    price_24k = _extract_price(html, "24")
    if price_22k is None and price_24k is None:
        return None
    return GoldPrice(city=city, gold_22k=price_22k, gold_24k=price_24k)


def _extract_price(html: str, karat: str) -> float | None:
    patterns = [
        rf"{karat}\s*(?:Karat|K|Carat).*?₹\s*([\d,]+)",
        rf"₹\s*([\d,]+).*?{karat}\s*(?:Karat|K|Carat)",
        rf"{karat}K.*?([\d,]+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            price_str = match.group(1).replace(",", "")
            try:
                return float(price_str)
            except ValueError:
                continue
    return None
