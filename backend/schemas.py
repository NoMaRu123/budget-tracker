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


class BudgetBase(BaseModel):
    month: str = Field(pattern=MONTH_PATTERN)
    limit_cents: int = Field(gt=0, le=MAX_CENTS)
    category_id: int = Field(gt=0)


class BudgetCreate(BudgetBase):
    pass


class Budget(BudgetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
