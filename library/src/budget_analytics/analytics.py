"""Pure budget maths: no database and no web framework, so any Python app can use it.

Every amount is in whole cents (6435 means 64.35), so there are no float rounding errors.
A transaction is a plain dict with the keys "date", "description", "amount_cents", "type" and "category_id".
"""
import re
from collections import defaultdict
from statistics import median

WARNING_PERCENT = 80  # from 80% used, a budget is in "warning"


def monthly_totals(transactions: list[dict]) -> dict:
    """Income, expenses and what's left over, for whatever transactions you pass in (usually one month)."""
    income = sum(t["amount_cents"] for t in transactions if t["type"] == "income")  # add up only the income
    expenses = sum(t["amount_cents"] for t in transactions if t["type"] == "expense")  # add up only the spending
    return {"income_cents": income, "expenses_cents": expenses, "balance_cents": income - expenses}


def spending_by_category(transactions: list[dict]) -> dict[int, int]:
    """Total spending per category id, e.g. {1: 17140, 3: 2500}. Income is not spending, so it's left out."""
    spent = defaultdict(int)  # a dict that starts every new key at 0, so += works the first time
    for t in transactions:
        if t["type"] == "expense":
            spent[t["category_id"]] += t["amount_cents"]
    return dict(spent)  # hand back a normal dict


def budget_status(limit_cents: int, spent_cents: int, warning_percent: int = WARNING_PERCENT) -> dict:
    """How much of one budget is used: ok under 80%, warning from 80% to 100%, over above 100%."""
    if limit_cents <= 0:  # a budget of 0 would mean dividing by 0 below
        raise ValueError("limit_cents must be more than 0")
    if spent_cents > limit_cents:  # exactly at the limit is not over
        status = "over"
    elif spent_cents * 100 >= limit_cents * warning_percent:  # whole numbers only: no float rounding at the 80% line
        status = "warning"
    else:
        status = "ok"
    return {
        "limit_cents": limit_cents,
        "spent_cents": spent_cents,
        "left_cents": limit_cents - spent_cents,  # negative when over: -2140 means 21.40 over
        "percent_used": round(spent_cents * 100 / limit_cents),  # for the bar and the label, e.g. 86
        "status": status,
    }


def normalise_description(text: str) -> str:
    """'NETFLIX.COM 8472' and 'Netflix.com 9921' are the same payment: keep only the lower-case letters."""
    words = re.sub(r"[^a-z]+", " ", text.lower())  # anything that isn't a letter becomes a space
    return " ".join(words.split())  # squash runs of spaces: "netflix com"


def find_recurring(transactions: list[dict], min_months: int = 3, tolerance_percent: int = 10) -> list[dict]:
    """Spot repeating payments, like rent or a subscription.

    A payment counts as recurring when the same description (see normalise_description) is spent in at least
    `min_months` different months, and every amount is within `tolerance_percent` of the typical amount.
    """
    groups = defaultdict(list)  # "netflix com" -> every Netflix expense
    for t in transactions:
        if t["type"] == "expense":
            key = normalise_description(t["description"])
            if key:  # a description with no letters at all can't be matched with anything
                groups[key].append(t)

    found = []
    for payments in groups.values():
        months = {str(p["date"])[:7] for p in payments}  # "2026-11-03" -> "2026-11"; a set keeps each month once
        if len(months) < min_months:
            continue
        typical = round(median(p["amount_cents"] for p in payments))  # the middle amount, so one odd payment can't drag it
        allowed = typical * tolerance_percent / 100  # how far an amount may be from the typical one
        if any(abs(p["amount_cents"] - typical) > allowed for p in payments):  # one amount too far off: not regular
            continue
        latest = max(payments, key=lambda p: str(p["date"]))  # the most recent payment
        found.append({
            "description": latest["description"],  # shown as the bank last wrote it
            "category_id": latest["category_id"],
            "amount_cents": typical,
            "months": len(months),
            "last_date": str(latest["date"]),
        })
    return sorted(found, key=lambda r: r["amount_cents"], reverse=True)  # biggest first
