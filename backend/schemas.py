import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    # API-level validation (W09): reject empty or overly long values with 422
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ItemCreate(ItemBase):
    pass


class Item(ItemBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


MAX_CENTS = 100_000_000


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
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    limit_cents: int = Field(gt=0, le=MAX_CENTS)
    category_id: int = Field(gt=0)


class BudgetCreate(BudgetBase):
    pass


class Budget(BudgetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
