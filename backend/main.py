import datetime as dt
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, Query
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


def commit_or_409(db: Session, detail: str = "An item with this name already exists"):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logging.warning("Rejected by the database: %s", detail)
        raise HTTPException(status_code=409, detail=detail)


def get_item_or_404(item_id: int, db: Session):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item is None:
        logging.warning("Item %s not found", item_id)
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/items/", response_model=schemas.Item)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    logging.info("CREATE : %s", item)
    db_item = models.Item(**item.model_dump())
    db.add(db_item)
    commit_or_409(db)
    db.refresh(db_item)
    return db_item


@app.get("/items/", response_model=list[schemas.Item])
def read_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logging.info("READ ALL : skip=%s limit=%s", skip, limit)
    return db.query(models.Item).offset(skip).limit(limit).all()


@app.get("/items/{item_id}", response_model=schemas.Item)
def read_item(item_id: int, db: Session = Depends(get_db)):
    logging.info("READ ONE : %s", item_id)
    return get_item_or_404(item_id, db)


@app.put("/items/{item_id}", response_model=schemas.Item)
def update_item(item_id: int, item: schemas.ItemCreate, db: Session = Depends(get_db)):
    logging.info("UPDATE : %s -> %s", item_id, item)
    db_item = get_item_or_404(item_id, db)
    for field, value in item.model_dump().items():
        setattr(db_item, field, value)
    commit_or_409(db)
    db.refresh(db_item)
    return db_item


@app.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    logging.info("DELETE : %s", item_id)
    item = get_item_or_404(item_id, db)
    db.delete(item)
    db.commit()
    return {"message": "Item deleted successfully"}


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
