import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MAX_CENTS = 100_000_000
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class CategoryBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=50)


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class TransactionBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    date: dt.date
    description: str = Field(min_length=1, max_length=200)
    amount_cents: int = Field(gt=0, le=MAX_CENTS)
    type: Literal["expense", "income"]
    category_id: int = Field(gt=0)


class TransactionCreate(TransactionBase):
    pass


class Transaction(TransactionBase):
    id: int

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class BudgetAlert(BaseModel):  # one "over budget" warning, e.g. Eating out, 2140
    category: str
    over_by_cents: int


class TransactionSaved(Transaction):  # the POST/PUT reply: the saved transaction plus any alerts it set off
    alerts: list[BudgetAlert] = []


class BudgetBase(BaseModel):
    month: str = Field(pattern=MONTH_PATTERN)
    limit_cents: int = Field(gt=0, le=MAX_CENTS)
    category_id: int = Field(gt=0)


class BudgetCreate(BudgetBase):
    pass


class Budget(BudgetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class BudgetStatus(BaseModel):  # one row of GET /budgets/status: how much of a budget is used
    category_id: int
    category_name: str
    limit_cents: int
    spent_cents: int
    left_cents: int  # negative when over budget
    percent_used: int
    status: Literal["ok", "warning", "over"]  # ok under 80%, warning 80 to 100%, over above 100%
