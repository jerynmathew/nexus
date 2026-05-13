from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedFD:
    principal: float
    rate: float
    tenure_months: int
    maturity_date: str | None


@dataclass(frozen=True)
class HDFCStatementResult:
    fds: list[ParsedFD]
    account_balance: float | None
    raw_transactions: int


def parse_hdfc_csv(content: str) -> HDFCStatementResult:
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return HDFCStatementResult(fds=[], account_balance=None, raw_transactions=0)

    balance = _extract_balance(rows)
    return HDFCStatementResult(fds=[], account_balance=balance, raw_transactions=len(rows) - 1)


def _extract_balance(rows: list[list[str]]) -> float | None:
    for row in reversed(rows):
        for cell in reversed(row):
            cleaned = cell.strip().replace(",", "")
            try:
                val = float(cleaned)
                if val > 0:
                    return val
            except ValueError:
                continue
    return None
