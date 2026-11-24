import datetime as dt

import pytest

from budget_analytics import (
    budget_status,
    find_recurring,
    monthly_totals,
    normalise_description,
    spending_by_category,
)


def txn(amount_cents, kind="expense", category_id=1, date="2026-11-14", description="Tesco"):
    # a normal transaction; a test only changes the part it cares about
    return {"date": date, "description": description, "amount_cents": amount_cents, "type": kind,
            "category_id": category_id}


# ---------- monthly_totals ----------

def test_monthly_totals_with_no_transactions():
    assert monthly_totals([]) == {"income_cents": 0, "expenses_cents": 0, "balance_cents": 0}


def test_monthly_totals_adds_income_and_expenses_separately():
    result = monthly_totals([txn(250000, kind="income"), txn(6435), txn(1200)])
    assert result == {"income_cents": 250000, "expenses_cents": 7635, "balance_cents": 242365}


def test_monthly_totals_balance_can_go_negative():
    assert monthly_totals([txn(1000, kind="income"), txn(1500)])["balance_cents"] == -500


# ---------- spending_by_category ----------

def test_spending_by_category_with_no_transactions():
    assert spending_by_category([]) == {}


def test_spending_by_category_totals_each_category():
    transactions = [txn(12860, category_id=2), txn(4280, category_id=2), txn(6435, category_id=1)]
    assert spending_by_category(transactions) == {2: 17140, 1: 6435}


def test_spending_by_category_ignores_income():
    assert spending_by_category([txn(99999, kind="income"), txn(500)]) == {1: 500}


# ---------- budget_status ----------

@pytest.mark.parametrize("spent, status", [
    (0, "ok"),
    (7999, "ok"),          # just under 80%
    (8000, "warning"),     # exactly 80%
    (10000, "warning"),    # exactly at the limit is not over
    (10001, "over"),       # 1 cent over
])
def test_budget_status_boundaries(spent, status):
    assert budget_status(10000, spent)["status"] == status


def test_budget_status_over_budget_example():
    # the spec's Eating out example: 171.40 spent of 150.00
    assert budget_status(15000, 17140) == {
        "limit_cents": 15000, "spent_cents": 17140, "left_cents": -2140, "percent_used": 114, "status": "over",
    }


def test_budget_status_custom_warning_line():
    assert budget_status(10000, 5000, warning_percent=50)["status"] == "warning"


@pytest.mark.parametrize("limit", [0, -100])
def test_budget_status_rejects_a_limit_of_zero_or_less(limit):
    with pytest.raises(ValueError):
        budget_status(limit, 100)


# ---------- normalise_description ----------

@pytest.mark.parametrize("text, expected", [
    ("NETFLIX.COM 8472", "netflix com"),
    ("Netflix.com   9921", "netflix com"),
    ("  Rent - November  ", "rent november"),
    ("12345", ""),
])
def test_normalise_description(text, expected):
    assert normalise_description(text) == expected


# ---------- find_recurring ----------

def test_find_recurring_spots_a_monthly_subscription():
    transactions = [
        txn(1799, date="2026-09-03", description="NETFLIX.COM 1111"),
        txn(1799, date="2026-10-03", description="NETFLIX.COM 2222"),
        txn(1799, date="2026-11-03", description="Netflix.com 3333"),
    ]
    assert find_recurring(transactions) == [{
        "description": "Netflix.com 3333", "category_id": 1, "amount_cents": 1799, "months": 3,
        "last_date": "2026-11-03",
    }]


def test_find_recurring_needs_three_different_months():
    transactions = [txn(1799, date="2026-10-03", description="Netflix"),
                    txn(1799, date="2026-11-03", description="Netflix"),
                    txn(1799, date="2026-11-20", description="Netflix")]   # 3 payments, but only 2 months
    assert find_recurring(transactions) == []


def test_find_recurring_allows_small_changes_in_the_amount():
    # electricity: a little different every month, but within 10%
    transactions = [txn(5000, date="2026-09-15", description="Electric Ireland"),
                    txn(5300, date="2026-10-15", description="Electric Ireland"),
                    txn(4800, date="2026-11-15", description="Electric Ireland")]
    assert find_recurring(transactions)[0]["amount_cents"] == 5000   # the middle amount


def test_find_recurring_rejects_amounts_that_vary_too_much():
    # the same shop every month, but different baskets: not a regular payment
    transactions = [txn(6435, date="2026-09-01"), txn(1200, date="2026-10-01"), txn(9900, date="2026-11-01")]
    assert find_recurring(transactions) == []


def test_find_recurring_ignores_income():
    transactions = [txn(250000, kind="income", date=f"2026-{m}-28", description="Salary") for m in ("09", "10", "11")]
    assert find_recurring(transactions) == []


def test_find_recurring_sorts_biggest_first_and_accepts_date_objects():
    transactions = []
    for month in (9, 10, 11):
        transactions.append(txn(1799, date=dt.date(2026, month, 3), description="Netflix"))
        transactions.append(txn(120000, date=dt.date(2026, month, 1), description="Rent"))
    assert [r["description"] for r in find_recurring(transactions)] == ["Rent", "Netflix"]


def test_find_recurring_with_no_transactions():
    assert find_recurring([]) == []
