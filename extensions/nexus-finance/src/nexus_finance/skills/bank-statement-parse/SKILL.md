---
name: bank-statement-parse
description: Parse an uploaded bank statement PDF/CSV and extract holdings
execution: sequential
tool_groups: [finance]
---

When the user uploads a bank statement (PDF or CSV):

1. Detect the bank from the document format (HDFC, SBI, ICICI, etc.)
2. Extract structured data:
   - FDs: principal, interest rate, tenure, maturity date
   - RDs: monthly deposit, rate, tenure, maturity date
   - Loans: outstanding principal, EMI, rate, tenure remaining
   - Account balance: savings/current account balances
3. Store extracted holdings in finance_holdings table (asset_class='debt')
4. Update finance_reminders with current timestamp
5. Report what was found and what was updated in the portfolio

Supported formats: HDFC PDF, HDFC CSV, SBI PDF, SBI CSV.
