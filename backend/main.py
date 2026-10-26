import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException
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


FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
