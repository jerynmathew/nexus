from __future__ import annotations

from nexus_finance.gold import parse_goodreturns_html


class TestParseGoodreturns:
    def test_parses_22k(self) -> None:
        html = "<div>22 Karat Gold Price: ₹6,500 per gram</div>"
        result = parse_goodreturns_html(html, "bangalore")
        assert result is not None
        assert result.gold_22k == 6500
        assert result.city == "bangalore"

    def test_parses_24k(self) -> None:
        html = "<div>24 Karat Gold: ₹7,100</div>"
        result = parse_goodreturns_html(html, "kerala")
        assert result is not None
        assert result.gold_24k == 7100

    def test_no_prices_found(self) -> None:
        result = parse_goodreturns_html("<div>No gold here</div>", "mumbai")
        assert result is None

    def test_both_karats(self) -> None:
        html = "<div>22K Gold: ₹6,500</div><div>24K Gold: ₹7,100</div>"
        result = parse_goodreturns_html(html, "bangalore")
        assert result is not None
        assert result.gold_22k == 6500
        assert result.gold_24k == 7100
