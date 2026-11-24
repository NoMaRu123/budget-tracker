# budget-analytics

Pure budget maths for Python. It has no database and no web framework, and no dependencies outside the standard library.

Every amount is in whole cents (`6435` means 64.35), so there are no float rounding errors. A transaction is a plain dict:

```python
{"date": "2026-11-14", "description": "Tesco", "amount_cents": 6435, "type": "expense", "category_id": 1}
```

## Install

```
pip install budget-analytics
```

## Functions

| Function | What it gives back |
|---|---|
| `monthly_totals(transactions)` | `{"income_cents", "expenses_cents", "balance_cents"}` |
| `spending_by_category(transactions)` | `{category_id: cents spent}`; income isn't counted |
| `budget_status(limit_cents, spent_cents)` | `limit_cents`, `spent_cents`, `left_cents` (negative when over), `percent_used`, and `status`: `ok` under 80%, `warning` from 80% to 100%, `over` above 100% |
| `find_recurring(transactions, min_months=3, tolerance_percent=10)` | payments with the same description in at least 3 different months, each within 10% of the typical amount; biggest first |
| `normalise_description(text)` | `"NETFLIX.COM 8472"` → `"netflix com"`, used to match bank descriptions |

## Example

```python
from budget_analytics import budget_status, spending_by_category

transactions = [
    {"date": "2026-11-10", "description": "Dinner", "amount_cents": 12860, "type": "expense", "category_id": 2},
    {"date": "2026-11-20", "description": "Pizza night", "amount_cents": 4280, "type": "expense", "category_id": 2},
]
spent = spending_by_category(transactions)  # {2: 17140}
budget_status(15000, spent[2])
# {'limit_cents': 15000, 'spent_cents': 17140, 'left_cents': -2140, 'percent_used': 114, 'status': 'over'}
```

## Run the tests

```
cd library
pip install pytest
pytest
```

## Licence

MIT
