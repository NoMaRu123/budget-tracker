import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from main import app, get_db, MAX_UPLOAD_BYTES, MAX_IMPORT_ROWS, euros_to_cents
from observers import TransactionEvents, TransactionObserver
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


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


# ---------- CSV import ----------

HEADER = b"date,description,amount,type,category\n"   # the only header the import accepts
BAD_ENCODING = "This file isn't UTF-8 text. In Excel, use Save As → CSV UTF-8."
BAD_HEADER = "The header row must be: date,description,amount,type,category"


def upload_csv(content: bytes, filename="bank.csv"):
    # files= sends a multipart/form-data upload, the same as the browser's "Choose file"
    return client.post("/transactions/import/validate", files={"file": (filename, content, "text/csv")})


def test_validate_import_without_file():
    response = client.post("/transactions/import/validate")  # no file attached
    assert response.status_code == 422


# File name and size

def test_validate_import_rejects_non_csv():
    response = upload_csv(b"not really a spreadsheet", filename="statement.xlsx")
    assert response.status_code == 400
    assert response.json() == {"detail": "Only .csv files can be imported"}


def test_validate_import_accepts_upper_case_extension():
    response = upload_csv(HEADER, filename="BANK.CSV")       # Windows often saves .CSV in capitals
    assert response.status_code == 200


def test_validate_import_accepts_exactly_1mb():
    content = HEADER + b"\n" * (MAX_UPLOAD_BYTES - len(HEADER))   # padded with blank lines to exactly 1 MB
    response = upload_csv(content)
    assert response.status_code == 200


def test_validate_import_rejects_file_over_1mb():
    response = upload_csv(b"a" * (MAX_UPLOAD_BYTES + 1))     # one byte over: rejected
    assert response.status_code == 413
    assert response.json() == {"detail": "The file is larger than 1 MB"}


# File content: encoding, header, CSV format

def test_validate_import_accepts_excel_bom():
    response = upload_csv(b"\xef\xbb\xbf" + HEADER)          # Excel's "CSV UTF-8" starts with these 3 bytes
    assert response.status_code == 200


def test_validate_import_rejects_latin1():
    content = HEADER + "2026-11-14,Café,4.50,expense,Eating out\n".encode("latin-1")   # é in an old encoding
    response = upload_csv(content)
    assert response.status_code == 400
    assert response.json() == {"detail": BAD_ENCODING}


def test_validate_import_rejects_nul_byte():
    response = upload_csv(HEADER + b"2026-11-14,Tes\x00co,64.35,expense,Groceries\n")
    assert response.status_code == 400
    assert response.json() == {"detail": BAD_ENCODING}


def test_validate_import_rejects_wrong_header():
    response = upload_csv(b"Date,Details,Debit,Credit\n2026-11-14,Tesco,64.35,\n")   # a real bank's layout
    assert response.status_code == 400
    assert response.json() == {"detail": BAD_HEADER}


def test_validate_import_rejects_empty_file():
    response = upload_csv(b"")
    assert response.status_code == 400
    assert response.json() == {"detail": BAD_HEADER}


def test_validate_import_rejects_broken_csv():
    content = HEADER + b'2026-11-14,"' + b"a" * 200_000 + b"\n"   # a quote that never closes
    response = upload_csv(content)
    assert response.status_code == 400
    assert response.json() == {"detail": "This file isn't a valid CSV file"}


# Row limit and amounts

ROW = b"2026-11-14,Tesco,64.35,expense,Groceries\n"   # one data row


def test_validate_import_allows_1000_rows():
    response = upload_csv(HEADER + ROW * MAX_IMPORT_ROWS)        # right on the limit: allowed
    assert response.status_code == 200


def test_validate_import_rejects_1001_rows():
    response = upload_csv(HEADER + ROW * (MAX_IMPORT_ROWS + 1))  # one row over: rejected
    assert response.status_code == 400
    assert response.json() == {"detail": "This file has more than 1,000 rows. Split it into smaller files."}


def test_validate_import_blank_lines_dont_count():
    content = HEADER + ROW * MAX_IMPORT_ROWS + b"\n,,,,\n\n"    # Excel often leaves empty lines at the end
    response = upload_csv(content)
    assert response.status_code == 200


# Unit tests: euros_to_cents on its own, no server or database involved.
# parametrize runs the same test once for each pair in the list.

@pytest.mark.parametrize("text, cents", [
    ("64.35", 6435),    # float maths would give 6434 here
    ("0.29", 29),
    ("19.99", 1999),
    ("64.3", 6430),     # one decimal means tens of cents
    ("64", 6400),       # no decimals
    (" 2.00 ", 200),    # spaces around it are fine
    ("0.00", 0),        # parses; the schema rejects 0 later
])
def test_euros_to_cents(text, cents):
    assert euros_to_cents(text) == cents


@pytest.mark.parametrize("text", [
    "", "abc", "-5.00", "+5", "€5", "1,250.00", "5.555", "5.", ".50", "1e5", "NaN", "1234567890",
])
def test_euros_to_cents_rejects(text):
    assert euros_to_cents(text) is None


# Checking each row

def test_validate_import_previews_valid_rows():
    groceries = create_test_category("Groceries").json()["id"]
    transport = create_test_category("Transport").json()["id"]
    content = HEADER + b'2026-11-14,"Tesco, Ranelagh",64.35,expense,Groceries\n2026-11-15,Dublin Bus,2.00,expense,Transport\n'
    response = upload_csv(content)
    assert response.status_code == 200
    assert response.json() == {
        "valid": 2,
        "skipped": 0,
        "rows": [
            {"date": "2026-11-14", "description": "Tesco, Ranelagh", "amount_cents": 6435,
             "type": "expense", "category_id": groceries},
            {"date": "2026-11-15", "description": "Dublin Bus", "amount_cents": 200,
             "type": "expense", "category_id": transport},
        ],
        "errors": [],
        "imported": 0,
    }


def test_validate_import_saves_nothing():
    create_test_category("Groceries")
    upload_csv(HEADER + ROW)
    assert client.get("/transactions/").json() == []   # validate only checks; nothing reaches the database


def test_validate_import_category_name_ignores_case():
    create_test_category("Groceries")
    response = upload_csv(HEADER + b"2026-11-14,Tesco,64.35,expense,groceries\n")
    assert response.json()["valid"] == 1


def test_validate_import_reports_row_errors():
    create_test_category("Groceries")
    content = HEADER + (
        b"2026-11-14,Tesco,64.35,expense,Groceries\n"           # row 2: fine
        b"2026-11-14,Tesco,0.00,expense,Groceries\n"            # row 3: amount 0
        b"2026-11-14,Gym membership,30.00,expense,Gym\n"        # row 4: no such category
        b"2026-11-14,=HYPERLINK(\"x\"),1.00,expense,Groceries\n"  # row 5: formula
        b"\n"                                                     # row 6: blank, skipped
        b"2026-11-14,Tesco,64.35,spending,Groceries\n"          # row 7: wrong type
        b"2026-11-14,Tesco,abc,expense,Groceries\n"             # row 8: amount isn't a number
        b"2026-11-14,Tesco,64.35\n"                             # row 9: only 3 cells
        b"14/11/2026,Tesco,64.35,expense,Groceries\n"           # row 10: wrong date format
    )
    data = upload_csv(content).json()
    assert data["valid"] == 1
    assert data["skipped"] == 7
    assert [(e["row"], e["column"]) for e in data["errors"]] == [
        (3, "amount"), (4, "category"), (5, "description"), (7, "type"), (8, "amount"), (9, "row"), (10, "date"),
    ]
    messages = {e["row"]: e["message"] for e in data["errors"]}
    assert messages[4] == "no category called 'Gym'"
    assert messages[5] == "can't start with =, +, - or @"
    assert messages[8] == "must be a number like 64.35"
    assert messages[9] == "must have 5 cells: date, description, amount, type, category"


@pytest.mark.parametrize("description", ["=1+1", "+SUM(A1:A9)", "-2+3", "@cmd", "\t=1+1"])
def test_validate_import_blocks_formulas(description):
    # A spreadsheet runs a cell starting with these as a formula when someone opens an export
    create_test_category("Groceries")
    row = f'2026-11-14,"{description}",1.00,expense,Groceries\n'.encode()
    data = upload_csv(HEADER + row).json()
    assert data["valid"] == 0
    assert data["errors"][0]["column"] == "description"


def test_validate_import_preview_shows_10_rows():
    create_test_category("Groceries")
    data = upload_csv(HEADER + ROW * 15).json()
    assert data["valid"] == 15            # all 15 count
    assert len(data["rows"]) == 10        # but only the first 10 are sent back for the preview


def test_validate_import_returns_at_most_100_errors():
    data = upload_csv(HEADER + ROW * 150).json()   # no categories exist, so every row fails
    assert data["skipped"] == 150
    assert len(data["errors"]) == 100


# Confirm: POST /transactions/import saves the valid rows

def confirm_csv(content: bytes, filename="bank.csv"):
    return client.post("/transactions/import", files={"file": (filename, content, "text/csv")})


def test_import_saves_valid_rows():
    create_test_category("Groceries")
    content = HEADER + ROW + ROW + b"2026-11-14,Tesco,0.00,expense,Groceries\n"   # 2 good rows, 1 bad
    response = confirm_csv(content)
    assert response.status_code == 201
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 1
    assert data["errors"][0]["row"] == 4
    assert len(client.get("/transactions/").json()) == 2   # really in the database


def test_import_with_no_valid_rows_saves_nothing():
    response = confirm_csv(HEADER + ROW)                     # no categories, so the only row fails
    assert response.status_code == 400
    assert response.json() == {"detail": "None of the rows can be imported"}
    assert client.get("/transactions/").json() == []


def test_import_runs_the_file_checks_again():
    response = confirm_csv(b"not really a spreadsheet", filename="statement.xlsx")
    assert response.status_code == 400


def test_import_is_all_or_nothing(monkeypatch):
    # Simulate a category being deleted between the check and the save: one row points at a missing category.
    # The database refuses that row, and the good row must not be saved either.
    import main
    create_test_category("Groceries")
    real_check_rows = main.check_rows

    def check_rows_with_a_missing_category(rows, db):
        valid, errors, skipped = real_check_rows(rows, db)
        broken = valid[0].model_copy(update={"category_id": 999})   # no category 999 exists
        return valid + [broken], errors, skipped

    monkeypatch.setattr(main, "check_rows", check_rows_with_a_missing_category)
    response = confirm_csv(HEADER + ROW)
    assert response.status_code == 409
    assert client.get("/transactions/").json() == []          # the good row was rolled back too


# ---------- Budget alerts (Observer pattern) ----------

def eating_out_with_budget():
    # The spec's example (flow 4.5): Eating out has a 150.00 budget for November and 128.60 already spent
    category_id = create_test_category("Eating out").json()["id"]
    create_test_budget(category_id, month="2026-11", limit_cents=15000)
    create_test_transaction(category_id, date="2026-11-10", amount_cents=12860)
    return category_id


def test_transaction_under_budget_has_no_alerts():
    category_id = eating_out_with_budget()
    response = create_test_transaction(category_id, date="2026-11-20", amount_cents=1000)   # 138.60 of 150.00
    assert response.status_code == 201
    assert response.json()["alerts"] == []


def test_transaction_exactly_at_limit_has_no_alerts():
    category_id = eating_out_with_budget()
    response = create_test_transaction(category_id, date="2026-11-20", amount_cents=2140)   # exactly 150.00
    assert response.json()["alerts"] == []


def test_transaction_over_budget_returns_alert():
    category_id = eating_out_with_budget()
    response = create_test_transaction(category_id, date="2026-11-20", amount_cents=4280)   # "Pizza night", 171.40
    assert response.status_code == 201
    assert response.json()["alerts"] == [{"category": "Eating out", "over_by_cents": 2140}]


def test_income_never_triggers_an_alert():
    category_id = eating_out_with_budget()
    response = create_test_transaction(category_id, date="2026-11-20", amount_cents=99999, kind="income")
    assert response.json()["alerts"] == []


def test_no_budget_means_no_alert():
    category_id = create_test_category().json()["id"]
    response = create_test_transaction(category_id, amount_cents=99999)
    assert response.json()["alerts"] == []


def test_other_months_are_not_counted():
    category_id = eating_out_with_budget()
    create_test_transaction(category_id, date="2026-10-31", amount_cents=50000)       # October: not November's budget
    response = create_test_transaction(category_id, date="2026-11-30", amount_cents=100)
    assert response.json()["alerts"] == []


def test_december_budget_counts_the_31st():
    category_id = create_test_category().json()["id"]
    create_test_budget(category_id, month="2026-12", limit_cents=1000)
    create_test_transaction(category_id, date="2026-12-01", amount_cents=600)
    response = create_test_transaction(category_id, date="2026-12-31", amount_cents=600)   # month end rolls into 2027
    assert response.json()["alerts"] == [{"category": "Groceries", "over_by_cents": 200}]


def test_edit_that_goes_over_budget_returns_alert():
    category_id = eating_out_with_budget()
    transaction_id = create_test_transaction(category_id, date="2026-11-20", amount_cents=100).json()["id"]
    response = client.put(f"/transactions/{transaction_id}", json={
        "date": "2026-11-20",
        "description": "Pizza night",
        "amount_cents": 4280,                                  # edited up from 1.00 to 42.80
        "type": "expense",
        "category_id": category_id,
    })
    assert response.status_code == 200
    assert response.json()["alerts"] == [{"category": "Eating out", "over_by_cents": 2140}]


class FakeObserver(TransactionObserver):
    # Records what it was told, so the test can check the subject called it
    def __init__(self):
        self.seen = []

    def update(self, transaction, db):
        self.seen.append(transaction)
        return []


def test_subject_notifies_every_attached_observer():
    events = TransactionEvents()
    first, second = FakeObserver(), FakeObserver()
    events.attach(first)
    events.attach(second)
    events.notify("a transaction", db=None)
    assert first.seen == ["a transaction"]
    assert second.seen == ["a transaction"]


def test_detached_observer_is_not_notified():
    events = TransactionEvents()
    observer = FakeObserver()
    events.attach(observer)
    events.detach(observer)
    events.notify("a transaction", db=None)
    assert observer.seen == []
