import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from main import app, get_db
from database import Base
import models

# In-memory test database: never touches the real test.db
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Every route that asks for get_db gets the test session instead
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_database():
    # Empty tables before each test, deleted after
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def create_test_item(name="Pen", description="Blue"):
    return client.post("/items/", json={"name": name, "description": description})

# --- Create ---


def test_create_item():
    response = create_test_item()
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Pen"
    assert data["description"] == "Blue"
    assert "id" in data


def test_create_item_missing_name():
    response = client.post("/items/", json={"description": "no name"})
    assert response.status_code == 422


def test_create_item_empty_name():
    response = client.post("/items/", json={"name": "", "description": "empty"})
    assert response.status_code == 422


def test_create_duplicate_name():
    create_test_item("Pen")
    response = create_test_item("Pen")
    assert response.status_code == 409
    assert response.json() == {"detail": "An item with this name already exists"}

# --- Read ---


def test_read_items():
    create_test_item("Pen")
    create_test_item("Book")
    response = client.get("/items/")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_read_item_not_found():
    response = client.get("/items/99")
    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}

# --- Update ---


def test_update_item():
    item_id = create_test_item().json()["id"]
    response = client.put(f"/items/{item_id}", json={"name": "Pen", "description": "Red"})
    assert response.status_code == 200
    assert response.json()["description"] == "Red"


def test_update_item_not_found():
    response = client.put("/items/99", json={"name": "Ghost"})
    assert response.status_code == 404


def test_update_to_existing_name():
    create_test_item("Pen")
    book_id = create_test_item("Book").json()["id"]
    response = client.put(f"/items/{book_id}", json={"name": "Pen"})
    assert response.status_code == 409

# --- Delete ---


def test_delete_item():
    item_id = create_test_item().json()["id"]
    response = client.delete(f"/items/{item_id}")
    assert response.status_code == 200
    assert client.get(f"/items/{item_id}").status_code == 404


def test_delete_item_not_found():
    response = client.delete("/items/99")
    assert response.status_code == 404


# ---------- Categories ----------

def create_test_category(name="Groceries"):
    return client.post("/categories/", json={"name": name})


def test_create_category():
    response = create_test_category(" Groceries ")
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Groceries"
    assert "id" in data


def test_create_category_blank_name():
    response = create_test_category("   ")
    assert response.status_code == 422


def test_create_category_duplicate_name():
    create_test_category("Groceries")
    response = create_test_category("Groceries")
    assert response.status_code == 409
    assert response.json() == {"detail": "A category with this name already exists"}


def test_read_categories_sorted_by_name():
    create_test_category("Rent")
    create_test_category("Groceries")
    response = client.get("/categories/")
    assert response.status_code == 200
    assert [c["name"] for c in response.json()] == ["Groceries", "Rent"]


def test_read_category_not_found():
    response = client.get("/categories/99")
    assert response.status_code == 404
    assert response.json() == {"detail": "Category not found"}


def test_update_category():
    category_id = create_test_category("Rent").json()["id"]
    response = client.put(f"/categories/{category_id}", json={"name": "Housing"})
    assert response.status_code == 200
    assert response.json() == {"id": category_id, "name": "Housing"}


def test_update_category_to_existing_name():
    create_test_category("Groceries")
    rent_id = create_test_category("Rent").json()["id"]
    response = client.put(f"/categories/{rent_id}", json={"name": "Groceries"})
    assert response.status_code == 409


def test_delete_category():
    category_id = create_test_category().json()["id"]
    response = client.delete(f"/categories/{category_id}")
    assert response.status_code == 200
    assert client.get(f"/categories/{category_id}").status_code == 404


def test_delete_category_in_use():
    category_id = create_test_category().json()["id"]
    # there's no transaction route yet, so put a transaction straight into the TEST database:
    db = TestingSessionLocal()
    db.add(models.Transaction(date=dt.date(2026, 10, 3), description="TESCO", amount_cents=1250,
                              type="expense", category_id=category_id))
    db.commit()
    db.close()
    response = client.delete(f"/categories/{category_id}")
    assert response.status_code == 409                                   # refused: still in use
    assert client.get(f"/categories/{category_id}").status_code == 200   # and it's still there


def test_delete_category_not_found():
    response = client.delete("/categories/99")
    assert response.status_code == 404
