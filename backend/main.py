import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, schemas
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

def commit_or_409(db: Session):
    # unique=True on name makes the database reject duplicates with an IntegrityError
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logging.warning("Duplicate name rejected")
        raise HTTPException(status_code=409, detail="An item with this name already exists")

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

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist" 
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")