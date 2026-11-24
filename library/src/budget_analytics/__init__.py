"""budget-analytics: pure functions for budget maths (totals, spending per category, budget status, recurring payments)."""
from budget_analytics.analytics import (
    WARNING_PERCENT,
    budget_status,
    find_recurring,
    monthly_totals,
    normalise_description,
    spending_by_category,
)

__version__ = "0.1.0"
__all__ = [  # what "from budget_analytics import *" gives you: the public functions
    "WARNING_PERCENT",
    "budget_status",
    "find_recurring",
    "monthly_totals",
    "normalise_description",
    "spending_by_category",
]
