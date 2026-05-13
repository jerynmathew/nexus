from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SBIStatementResult:
    account_balance: float | None
    raw_transactions: int


def parse_sbi_csv(content: str) -> SBIStatementResult:
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return SBIStatementResult(account_balance=None, raw_transactions=0)

    balance = _extract_balance(rows)
    return SBIStatementResult(account_balance=balance, raw_transactions=len(rows) - 1)


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
