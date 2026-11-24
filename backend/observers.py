"""Observer pattern: when a transaction is saved, every attached observer is told about it."""
import datetime as dt
import logging
from abc import ABC, abstractmethod

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas


class TransactionObserver(ABC):  # the Observer interface: every observer must have an update() method
    @abstractmethod
    def update(self, transaction: models.Transaction, db: Session) -> list[schemas.BudgetAlert]:
        """React to a saved transaction. Return any alerts for the user (or an empty list)."""


class TransactionEvents:  # the Subject: keeps a list of observers and tells each one when a transaction is saved
    def __init__(self):
        self._observers: list[TransactionObserver] = []  # made in __init__, so every subject gets its own list

    def attach(self, observer: TransactionObserver) -> None:  # start telling this observer
        self._observers.append(observer)

    def detach(self, observer: TransactionObserver) -> None:  # stop telling this observer
        self._observers.remove(observer)

    def notify(self, transaction: models.Transaction, db: Session) -> list[schemas.BudgetAlert]:
        alerts = []
        for observer in self._observers:  # the subject doesn't know what each observer does; it just calls update()
            alerts.extend(observer.update(transaction, db))  # collect every observer's alerts in one list
        return alerts


def month_bounds(day: dt.date) -> tuple[dt.date, dt.date]:  # 2026-11-14 -> (2026-11-01, 2026-12-01)
    start = day.replace(day=1)  # first day of the month
    end = (start + dt.timedelta(days=32)).replace(day=1)  # 32 days on is always in the next month; go to its 1st
    return start, end


class BudgetChecker(TransactionObserver):  # warns when a saved expense pushes its category over the month's budget
    def update(self, transaction: models.Transaction, db: Session) -> list[schemas.BudgetAlert]:
        if transaction.type != "expense":  # income never uses up a budget
            return []
        month = transaction.date.strftime("%Y-%m")  # 2026-11-14 -> "2026-11", the format budgets are saved in
        budget = db.query(models.Budget).filter_by(category_id=transaction.category_id, month=month).first()
        if budget is None:  # no budget set for this category and month, so nothing to go over
            return []
        start, end = month_bounds(transaction.date)
        spent = db.query(func.sum(models.Transaction.amount_cents)).filter(  # add up the month's spending in SQL
            models.Transaction.category_id == transaction.category_id,
            models.Transaction.type == "expense",
            models.Transaction.date >= start,
            models.Transaction.date < end,
        ).scalar() or 0  # SUM of no rows is None, so "or 0"
        if spent <= budget.limit_cents:  # exactly at the limit is not over
            return []
        over_by = spent - budget.limit_cents
        logging.warning("OVER BUDGET : %s is %s cents over for %s", transaction.category.name, over_by, month)
        return [schemas.BudgetAlert(category=transaction.category.name, over_by_cents=over_by)]


class TransactionLogger(TransactionObserver):  # a second observer: writes every save to server.log
    def update(self, transaction: models.Transaction, db: Session) -> list[schemas.BudgetAlert]:
        logging.info("TRANSACTION SAVED : id=%s, %s, %s cents", transaction.id, transaction.type,
                     transaction.amount_cents)
        return []  # logging never produces an alert
