import csv
import datetime as dt
import io
import logging
import re
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
import schemas
from pathlib import Path
from fastapi.staticfiles import StaticFiles

models.Base.metadata.create_all(bind=engine)

# Log every request to server.log (W09 Validations slides)
logging.basicConfig(filename="server.log", encoding="utf-8", level=logging.INFO)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def commit_or_409(db: Session, detail: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logging.warning("Rejected by the database: %s", detail)
        raise HTTPException(status_code=409, detail=detail)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Categories ----------

def get_category_or_404(category_id: int, db: Session):
    category = db.get(models.Category, category_id)
    if category is None:
        logging.warning("Category %s not found", category_id)
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@app.post("/categories/", response_model=schemas.Category, status_code=201)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    logging.info("CREATE CATEGORY : %s", category)
    db_category = models.Category(**category.model_dump())
    db.add(db_category)
    commit_or_409(db, "A category with this name already exists")
    db.refresh(db_category)
    return db_category


@app.get("/categories/", response_model=list[schemas.Category])
def read_categories(db: Session = Depends(get_db)):
    logging.info("READ ALL CATEGORIES")
    return db.query(models.Category).order_by(models.Category.name).all()


@app.get("/categories/{category_id}", response_model=schemas.Category)
def read_category(category_id: int, db: Session = Depends(get_db)):
    logging.info("READ CATEGORY : %s", category_id)
    return get_category_or_404(category_id, db)


@app.put("/categories/{category_id}", response_model=schemas.Category)
def update_category(category_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    logging.info("UPDATE CATEGORY: %s -> %s", category_id, category)
    db_category = get_category_or_404(category_id, db)
    db_category.name = category.name
    commit_or_409(db, "A category with this name already exists")
    db.refresh(db_category)
    return db_category


@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    logging.info("DELETE CATEGORY : %s", category_id)
    db_category = get_category_or_404(category_id, db)
    if db_category.transactions or db_category.budgets:
        logging.warning("Category %s still in use", category_id)
        raise HTTPException(status_code=409, detail="This category still has transactions or budgets")
    db.delete(db_category)
    db.commit()
    return {"message": "Category deleted successfully"}


# ---------- Transactions ----------

def get_transaction_or_404(transaction_id: int, db: Session):
    transaction = db.get(models.Transaction, transaction_id)
    if transaction is None:
        logging.warning("Transaction %s not found", transaction_id)
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def month_range(month: str):
    # "2026-10" -> (1 October 2026, 1 November 2026)
    start = dt.date.fromisoformat(month + "-01")
    if start.month == 12:
        end = dt.date(start.year + 1, 1, 1)
    else:
        end = dt.date(start.year, start.month + 1, 1)
    return start, end


@app.post("/transactions/", response_model=schemas.Transaction, status_code=201)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    logging.info("CREATE TRANSACTION : %s", transaction)
    get_category_or_404(transaction.category_id, db)
    db_transaction = models.Transaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@app.get("/transactions/", response_model=list[schemas.Transaction])
def read_transactions(
    month: str | None = Query(default=None, pattern=schemas.MONTH_PATTERN),  # ?month=2026-10 (optional)
    category_id: int | None = None,                                         # ?category_id=3 (optional)
    db: Session = Depends(get_db),
):
    logging.info("READ ALL TRANSACTIONS : month=%s category_id=%s", month, category_id)
    query = db.query(models.Transaction)
    if month is not None:
        start, end = month_range(month)
        query = query.filter(models.Transaction.date >= start, models.Transaction.date < end)
    if category_id is not None:
        query = query.filter(models.Transaction.category_id == category_id)
    return query.order_by(models.Transaction.date.desc(), models.Transaction.id.desc()).all()


@app.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
def read_transaction(transaction_id: int, db: Session = Depends(get_db)):
    logging.info("READ TRANSACTION : %s", transaction_id)
    return get_transaction_or_404(transaction_id, db)


@app.put("/transactions/{transaction_id}", response_model=schemas.Transaction)
def update_transaction(transaction_id: int, transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    logging.info("UPDATE TRANSACTION : %s -> %s", transaction_id, transaction)
    db_transaction = get_transaction_or_404(transaction_id, db)
    get_category_or_404(transaction.category_id, db)
    for field, value in transaction.model_dump().items():
        setattr(db_transaction, field, value)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    logging.info("DELETE TRANSACTION : %s", transaction_id)
    db_transaction = get_transaction_or_404(transaction_id, db)
    db.delete(db_transaction)
    db.commit()
    return {"message": "Transaction deleted successfully"}


# ---------- CSV import ----------

MAX_UPLOAD_BYTES = 1_000_000  # 1 MB limit from spec 5.1
MAX_IMPORT_ROWS = 1_000  # row limit from spec 5.1
AMOUNT_PATTERN = re.compile(r"\d{1,9}(\.\d{1,2})?")  # 64, 64.3 or 64.35: no signs, no €, no commas


def read_upload_or_400(file: UploadFile) -> bytes:  # runs every file check; returns the bytes if they pass
    filename = file.filename or ""  # the name can be missing; "" avoids a crash on .lower()
    if not filename.lower().endswith(".csv"):  # lower() so BANK.CSV passes too
        logging.warning("IMPORT REJECTED, not .csv : %r", filename)
        raise HTTPException(status_code=400, detail="Only .csv files can be imported")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)  # the +1 "peek" from lesson 1
    if len(data) > MAX_UPLOAD_BYTES:  # the extra byte arrived, so there's more than 1 MB
        logging.warning("IMPORT REJECTED, over 1 MB : %r", filename)
        raise HTTPException(status_code=413, detail="The file is larger than 1 MB")
    return data


EXPECTED_HEADER = ["date", "description", "amount", "type", "category"]  # the first row must be exactly this
BAD_ENCODING = "This file isn't UTF-8 text. In Excel, use Save As → CSV UTF-8."  # used by two checks below


def parse_csv_or_400(data: bytes) -> list[list[str]]:  # bytes in, rows out (each row is a list of cells)
    try:
        text = data.decode("utf-8-sig")  # bytes -> text; "-sig" also drops Excel's invisible marker at the start
    except UnicodeDecodeError:  # not valid UTF-8: an old encoding, or not text at all
        logging.warning("IMPORT REJECTED, not UTF-8")
        raise HTTPException(status_code=400, detail=BAD_ENCODING)
    if "\x00" in text:  # NUL byte: never in a real CSV, common in binary files and UTF-16 text
        logging.warning("IMPORT REJECTED, NUL byte")
        raise HTTPException(status_code=400, detail=BAD_ENCODING)
    try:
        rows = list(csv.reader(io.StringIO(text)))  # split into rows and cells, in memory only
    except csv.Error:  # e.g. a quote that never closes, so one cell runs on forever
        logging.warning("IMPORT REJECTED, broken CSV")
        raise HTTPException(status_code=400, detail="This file isn't a valid CSV file")
    if not rows or rows[0] != EXPECTED_HEADER:  # empty file, or the wrong columns
        logging.warning("IMPORT REJECTED, wrong header")
        raise HTTPException(status_code=400, detail="The header row must be: date,description,amount,type,category")
    data_rows = rows[1:]  # everything after the header
    filled = [row for row in data_rows if not is_blank(row)]  # blank lines don't count towards the limit
    if len(filled) > MAX_IMPORT_ROWS:
        logging.warning("IMPORT REJECTED, %s rows", len(filled))
        raise HTTPException(status_code=400, detail="This file has more than 1,000 rows. Split it into smaller files.")
    return data_rows  # blank lines kept, so row numbers still match the spreadsheet


def is_blank(row: list[str]) -> bool:  # an empty line, or one with only commas like ",,,,"
    return all(cell.strip() == "" for cell in row)


def euros_to_cents(text: str) -> int | None:  # "64.35" -> 6435, or None if it isn't a plain amount
    text = text.strip()  # " 2.00 " -> "2.00"
    if not AMOUNT_PATTERN.fullmatch(text):  # the whole text must match, not just part of it
        return None
    euros, _, cents = text.partition(".")  # "64.35" -> ("64", ".", "35"); "64" -> ("64", "", "")
    return int(euros) * 100 + int(cents.ljust(2, "0"))  # pad "3" to "30" and "" to "00"


@app.post("/transactions/import/validate")
def validate_import(file: UploadFile):  # FastAPI takes the file from the form field called "file"
    data = read_upload_or_400(file)  # stops here with 400 or 413 if the file fails a check
    rows = parse_csv_or_400(data)  # stops here with 400 if the content is wrong
    logging.info("IMPORT VALIDATE : %r, %s bytes, %s rows", file.filename, len(data), len(rows))
    return {"filename": file.filename, "size": len(data), "rows": len(rows)}


# ---------- Budgets ----------

BUDGET_EXISTS = "A budget for this category and month already exists"


def get_budget_or_404(budget_id: int, db: Session):
    budget = db.get(models.Budget, budget_id)
    if budget is None:
        logging.warning("Budget %s not found", budget_id)
        raise HTTPException(status_code=404, detail="Budget not found")
    return budget


@app.post("/budgets/", response_model=schemas.Budget, status_code=201)
def create_budget(budget: schemas.BudgetCreate, db: Session = Depends(get_db)):
    logging.info("CREATE BUDGET : %s", budget)
    get_category_or_404(budget.category_id, db)
    db_budget = models.Budget(**budget.model_dump())
    db.add(db_budget)
    commit_or_409(db, BUDGET_EXISTS)
    db.refresh(db_budget)
    return db_budget


@app.get("/budgets/", response_model=list[schemas.Budget])
def read_budgets(
    month: str | None = Query(default=None, pattern=schemas.MONTH_PATTERN),  # ?month=2026-10 (optional)
    db: Session = Depends(get_db),
):
    logging.info("READ ALL BUDGETS : month=%s", month)
    query = db.query(models.Budget)
    if month is not None:
        query = query.filter(models.Budget.month == month)
    return query.order_by(models.Budget.month.desc(), models.Budget.category_id).all()


@app.get("/budgets/{budget_id}", response_model=schemas.Budget)
def read_budget(budget_id: int, db: Session = Depends(get_db)):
    logging.info("READ BUDGET : %s", budget_id)
    return get_budget_or_404(budget_id, db)


@app.put("/budgets/{budget_id}", response_model=schemas.Budget)
def update_budget(budget_id: int, budget: schemas.BudgetCreate, db: Session = Depends(get_db)):
    logging.info("UPDATE BUDGET : %s -> %s", budget_id, budget)
    db_budget = get_budget_or_404(budget_id, db)
    get_category_or_404(budget.category_id, db)
    for field, value in budget.model_dump().items():
        setattr(db_budget, field, value)
    commit_or_409(db, BUDGET_EXISTS)
    db.refresh(db_budget)
    return db_budget


@app.delete("/budgets/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    logging.info("DELETE BUDGET : %s", budget_id)
    db_budget = get_budget_or_404(budget_id, db)
    db.delete(db_budget)
    db.commit()
    return {"message": "Budget deleted successfully"}


FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
