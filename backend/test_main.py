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


# ---------- Transactions ----------

def create_test_transaction(category_id, date="2026-10-03", amount_cents=1250, kind="expense"):
    # a normal valid transaction; a test only changes the part it cares about
    return client.post("/transactions/", json={
        "date": date,
        "description": "TESCO",
        "amount_cents": amount_cents,
        "type": kind,
        "category_id": category_id,
    })


def test_create_transaction():
    category_id = create_test_category().json()["id"]
    response = create_test_transaction(category_id)
    assert response.status_code == 201
    data = response.json()
    assert data["date"] == "2026-10-03"
    assert data["amount_cents"] == 1250
    assert "id" in data


def test_create_transaction_unknown_category():
    response = create_test_transaction(category_id=99)
    assert response.status_code == 404
    assert response.json() == {"detail": "Category not found"}


def test_create_transaction_zero_amount():
    category_id = create_test_category().json()["id"]
    response = create_test_transaction(category_id, amount_cents=0)
    assert response.status_code == 422


def test_create_transaction_bad_type():
    category_id = create_test_category().json()["id"]
    response = create_test_transaction(category_id, kind="gift")
    assert response.status_code == 422


def test_read_transactions_newest_first():
    category_id = create_test_category().json()["id"]
    create_test_transaction(category_id, date="2026-10-01")
    create_test_transaction(category_id, date="2026-10-20")
    response = client.get("/transactions/")
    assert response.status_code == 200
    assert [t["date"] for t in response.json()] == ["2026-10-20", "2026-10-01"]


def test_read_transactions_filter_by_month():
    category_id = create_test_category().json()["id"]
    create_test_transaction(category_id, date="2026-11-30")   # day before December: left out
    create_test_transaction(category_id, date="2026-12-01")   # first day: kept
    create_test_transaction(category_id, date="2026-12-31")   # last day: kept
    create_test_transaction(category_id, date="2027-01-01")   # next year: left out (December rollover)
    response = client.get("/transactions/?month=2026-12")
    assert [t["date"] for t in response.json()] == ["2026-12-31", "2026-12-01"]


def test_read_transactions_bad_month():
    response = client.get("/transactions/?month=2026-13")
    assert response.status_code == 422


def test_read_transactions_filter_by_category():
    groceries_id = create_test_category("Groceries").json()["id"]
    rent_id = create_test_category("Rent").json()["id"]
    create_test_transaction(groceries_id)
    create_test_transaction(rent_id)
    data = client.get(f"/transactions/?category_id={rent_id}").json()
    assert len(data) == 1
    assert data[0]["category_id"] == rent_id


def test_read_transaction_not_found():
    response = client.get("/transactions/99")
    assert response.status_code == 404
    assert response.json() == {"detail": "Transaction not found"}


def test_update_transaction():
    category_id = create_test_category().json()["id"]
    transaction_id = create_test_transaction(category_id).json()["id"]
    response = client.put(f"/transactions/{transaction_id}", json={
        "date": "2026-10-04",
        "description": "Lidl",
        "amount_cents": 900,
        "type": "expense",
        "category_id": category_id,
    })
    assert response.status_code == 200
    assert response.json()["description"] == "Lidl"
    assert response.json()["amount_cents"] == 900


def test_delete_transaction():
    category_id = create_test_category().json()["id"]
    transaction_id = create_test_transaction(category_id).json()["id"]
    response = client.delete(f"/transactions/{transaction_id}")
    assert response.status_code == 200
    assert client.get(f"/transactions/{transaction_id}").status_code == 404


# ---------- Budgets ----------

def create_test_budget(category_id, month="2026-10", limit_cents=30000):
    return client.post("/budgets/", json={"month": month, "limit_cents": limit_cents, "category_id": category_id})


def test_create_budget():
    category_id = create_test_category().json()["id"]
    response = create_test_budget(category_id)
    assert response.status_code == 201
    data = response.json()
    assert data["month"] == "2026-10"
    assert data["limit_cents"] == 30000
    assert "id" in data


def test_create_budget_unknown_category():
    response = create_test_budget(category_id=99)
    assert response.status_code == 404
    assert response.json() == {"detail": "Category not found"}


def test_create_budget_duplicate_month():
    category_id = create_test_category().json()["id"]
    create_test_budget(category_id, month="2026-10")
    response = create_test_budget(category_id, month="2026-10")
    assert response.status_code == 409
    assert response.json() == {"detail": "A budget for this category and month already exists"}


def test_create_budget_same_category_other_month():
    category_id = create_test_category().json()["id"]
    create_test_budget(category_id, month="2026-10")
    response = create_test_budget(category_id, month="2026-11")   # a new month is fine
    assert response.status_code == 201


def test_create_budget_bad_month():
    category_id = create_test_category().json()["id"]
    response = create_test_budget(category_id, month="2026-13")
    assert response.status_code == 422


def test_create_budget_zero_limit():
    category_id = create_test_category().json()["id"]
    response = create_test_budget(category_id, limit_cents=0)
    assert response.status_code == 422


def test_read_budgets_filter_by_month():
    groceries_id = create_test_category("Groceries").json()["id"]
    rent_id = create_test_category("Rent").json()["id"]
    create_test_budget(groceries_id, month="2026-10")
    create_test_budget(rent_id, month="2026-10")
    create_test_budget(groceries_id, month="2026-11")
    response = client.get("/budgets/?month=2026-10")
    assert response.status_code == 200
    assert [b["category_id"] for b in response.json()] == [groceries_id, rent_id]


def test_read_budget_not_found():
    response = client.get("/budgets/99")
    assert response.status_code == 404
    assert response.json() == {"detail": "Budget not found"}


def test_update_budget():
    category_id = create_test_category().json()["id"]
    budget_id = create_test_budget(category_id).json()["id"]
    response = client.put(f"/budgets/{budget_id}", json={"month": "2026-10", "limit_cents": 40000, "category_id": category_id})
    assert response.status_code == 200
    assert response.json()["limit_cents"] == 40000


def test_update_budget_to_taken_month():
    category_id = create_test_category().json()["id"]
    create_test_budget(category_id, month="2026-10")
    november_id = create_test_budget(category_id, month="2026-11").json()["id"]
    response = client.put(f"/budgets/{november_id}", json={"month": "2026-10", "limit_cents": 100, "category_id": category_id})
    assert response.status_code == 409


def test_delete_budget():
    category_id = create_test_category().json()["id"]
    budget_id = create_test_budget(category_id).json()["id"]
    response = client.delete(f"/budgets/{budget_id}")
    assert response.status_code == 200
    assert client.get(f"/budgets/{budget_id}").status_code == 404


def test_delete_category_with_budget():
    category_id = create_test_category().json()["id"]
    create_test_budget(category_id)
    response = client.delete(f"/categories/{category_id}")
    assert response.status_code == 409   # a budget still uses this category
