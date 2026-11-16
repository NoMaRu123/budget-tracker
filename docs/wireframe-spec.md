# Budget tracker: wireframe spec

Source of truth: `backend/main.py`, `backend/schemas.py`, `backend/models.py` as of commit `d85443c` (5 Nov 2026). Everything below marked **(gap)** is something the UI needs that the API can't do yet. Section 5 turns the gaps into backend tasks.

One user, no logins, euros only. Money is stored as whole cents (`1250` = €12.50) and shown in Irish format (`€1,250.00`).

Approved 16 Nov 2026 with changes: CSV import is validate-then-confirm with a preview, `/transactions` gets a pagination state, "can't reach server" is one state, and the upload follows the OWASP file upload rules in 5.1.

## 1. Screens and dialogs

Routes are written as React pages. The current front-end uses hash routes (`#transactions`), which map one to one.

| Route / dialog | What it's for | Endpoints |
|---|---|---|
| `/` Overview | One month at a glance: income, expenses, balance, budget bars, latest transactions | `GET /transactions/?month=YYYY-MM`, `GET /budgets/?month=YYYY-MM`, `GET /categories/` |
| `/transactions` | List, filter, page through, add, edit, delete transactions | `GET /transactions/?month=&category_id=` (paging is a gap, 5.4), `GET /categories/` |
| Transaction modal (add / edit) | The transaction form | `POST /transactions/`, `PUT /transactions/{id}` |
| Delete transaction modal | Confirm before deleting | `DELETE /transactions/{id}` |
| `/budgets` | One month's budgets with spent vs limit | `GET /budgets/?month=`, `GET /transactions/?month=`, `GET /categories/` (status endpoint is a gap, 5.3) |
| Budget modal (add / edit) | The budget form | `POST /budgets/`, `PUT /budgets/{id}` |
| Delete budget modal | Confirm before deleting | `DELETE /budgets/{id}` |
| `/categories` | List, add, rename, delete categories | `GET /categories/` |
| Category modal (add / rename) | The category form | `POST /categories/`, `PUT /categories/{id}` |
| Delete category modal | Confirm, or explain why it can't be deleted | `DELETE /categories/{id}` |
| `/import` **(gap)** | Upload a bank-statement CSV, check a preview, then confirm | none yet, see 5.1 |
| Over-budget alert (toast + banner) **(gap)** | Tell the user a save pushed a category over its limit | none yet, see 5.2 and 5.3 |

Shared on every page: a nav bar (Overview, Transactions, Budgets, Categories, Import) and a month picker (previous / month name / next). The month is shared: changing it on one page keeps it on the others.

`GET /health` exists but has no screen. It's for the deploy smoke test.

## 2. Form fields

All three forms send **every field** on edit, because the API uses `PUT` (full replace), not `PATCH`. Text fields are trimmed by the API before checking length (`str_strip_whitespace`), so "   " counts as empty.

### Transaction form (`TransactionCreate`)

| Field (label) | API field | Input | Required | Rules from the schema | Error shown |
|---|---|---|---|---|---|
| Date | `date` | date picker | yes | a real date, `YYYY-MM-DD`. No min or max: future dates are allowed | 422 |
| Description | `description` | text | yes | 1 to 200 characters after trimming | 422 |
| Amount (€) | `amount_cents` | number, 2 decimals, prefix "€" | yes | whole cents, more than 0, at most 100,000,000 (€1,000,000.00). The user types euros, the front-end sends cents | 422 |
| Type | `type` | two-option toggle: Expense / Income | yes | exactly `expense` or `income` | 422 |
| Category | `category_id` | dropdown of categories | yes | more than 0, and the category must exist | 422 if missing, **404 "Category not found"** if it was deleted meanwhile |

The amount is always positive. Whether money goes in or out is the Type field, not a minus sign.

### Budget form (`BudgetCreate`)

| Field | API field | Input | Required | Rules | Error |
|---|---|---|---|---|---|
| Category | `category_id` | dropdown | yes | must exist | 422 / 404 "Category not found" |
| Month | `month` | month picker, defaults to the page's month | yes | `YYYY-MM`, month 01 to 12 | 422 |
| Limit (€) | `limit_cents` | number, 2 decimals, prefix "€" | yes | more than 0, at most €1,000,000.00 | 422 |
| (pair) | category + month | | | one budget per category per month | **409 "A budget for this category and month already exists"** |

Not every browser shows a picker for `<input type="month">`. Some fall back to a text box, so the wireframe shows the hint "e.g. 2026-11" under it.

### Category form (`CategoryCreate`)

| Field | API field | Input | Required | Rules | Error |
|---|---|---|---|---|---|
| Name | `name` | text | yes | 1 to 50 characters after trimming, unique | 422, **409 "A category with this name already exists"** |

### CSV file (import, gap)

| Column | Maps to | Rules (each row is checked with `TransactionCreate`) |
|---|---|---|
| `date` | `date` | `YYYY-MM-DD` |
| `description` | `description` | 1 to 200 characters. Must not start with `=`, `+`, `-`, `@`, tab or carriage return (formula injection, 5.1) |
| `amount` | `amount_cents` | euros with up to 2 decimals, more than 0, at most 1,000,000.00 |
| `type` | `type` | `expense` or `income` |
| `category` | `category_id` | the name of an existing category (matched without regard to case once 5.5 is done) |

File rules: `.csv` only, UTF-8, at most 1 MB, at most 1,000 rows, header row exactly `date,description,amount,type,category`.

## 3. States for each screen

How the API reports problems decides how each state looks:

- **422** sends a list: `{"detail": [{"loc": ["body", "amount_cents"], "msg": "Input should be greater than 0"}]}`. The last part of `loc` is the field name, so the error can sit **under the right input** instead of only at the top.
- **404 and 409** send one sentence: `{"detail": "Category not found"}`. Shown as an alert inside the modal (or on the page for deletes).
- **Server error (500)**: the server answered, but something broke. Shown as a page or modal alert: "Something went wrong on the server." + "Try again".
- **Can't reach server**: one state for every case where no answer arrives at all: the backend is down, the address is wrong, or CORS blocked the reply. The browser can't tell these apart (`fetch` fails with no status), so the UI doesn't try: "Can't reach the server. Check your connection and try again." + "Try again".

There are no detail pages (no `/transactions/12`), so a 404 only happens inside a modal or on delete: someone (or another tab) deleted the item first.

### `/` Overview

| State | What the user sees |
|---|---|
| Loading | Three grey summary cards and grey bars (skeleton) |
| Success | Cards: Income €2,800.00, Expenses €1,680.75, Balance €1,119.25. Budget bars per category. Last 5 transactions with "See all" |
| Over budget | Red bar and banner "Eating out is €21.40 over its €150.00 budget" |
| Empty month | "No transactions in November 2026" + "Add transaction" + "Import CSV" |
| No budgets yet | Budget area says "No budgets for this month" + "Set a budget" |
| Server error | Page alert with "Try again" |
| Can't reach server | Page alert with "Try again" |
| 422 / 404 | Not possible from this page (the month picker always sends a valid month) |

### `/transactions`

| State | What the user sees |
|---|---|
| Loading | Table with grey rows |
| Success | Table: Date, Description, Category, Type, Amount, actions (Edit, Delete). Newest first (the API sorts by date, then id, descending). Filters: month (or "All months"), category |
| Paginated **(gap 5.4)** | More than 25 rows: the table shows 25, with "Showing 1 to 25 of 54" and Previous / page numbers / Next under it. Happens with "All months" or after a CSV import |
| Empty (no transactions at all this month) | "No transactions in November 2026" + "Add transaction" + "Import CSV" |
| Empty (filter matches nothing) | "No Transport transactions in October 2026" + "Clear filter" (every category has a transaction in November, so the example uses October) |
| Server error | Page alert with "Try again" |
| Can't reach server | Page alert with "Try again" |

Transaction modal (add / edit):

| State | What the user sees |
|---|---|
| Default (add) | Empty form, date = today, type = Expense, title "Add transaction" |
| Default (edit) | Form filled in, title "Edit transaction" |
| Submitting | Save button shows a spinner and is disabled, so it can't be sent twice |
| 422 | Red text under each wrong field, e.g. under Amount: "Must be more than €0.00". Modal stays open, the typed values stay |
| 404 category | Under Category: "This category was deleted. Pick another." The dropdown reloads |
| 404 transaction (edit) | Alert in the modal: "This transaction no longer exists." Button: "Close" (closing reloads the list) |
| Server error / can't reach server | Alert in the modal, the matching message from above: "Your changes weren't saved." + "Try again" |
| Success | Modal closes, success toast "Transaction added" / "Transaction saved", list reloads. If a budget is now over: the over-budget toast too |

Delete transaction modal: default ("Delete 'Tesco Ranelagh' (€64.35)? This can't be undone."), deleting (spinner), 404 ("Already deleted", close reloads the list), server error / can't reach server, success (toast "Transaction deleted").

### `/budgets`

| State | What the user sees |
|---|---|
| Loading | Grey rows |
| Success | Rows: Category, Limit, Spent, Left, progress bar, actions. Spent comes from this month's expenses in that category (worked out in the browser until 5.3 is built) |
| Bar variants | Under 80%: normal. 80 to 100%: warning. Over 100%: danger + "€21.40 over" |
| Over budget | The danger bar plus a banner at the top |
| Empty | "No budgets for November 2026" + "Set a budget" |
| No categories yet | "Create a category first" + link to `/categories` (the budget form would have an empty dropdown) |
| Server error | Page alert with "Try again" |
| Can't reach server | Page alert with "Try again" |

Budget modal: default (add / edit), submitting, 422 (under Month or Limit), 404 category (under Category), 409 ("Groceries already has a budget for November 2026. Edit that one instead."), server error / can't reach server, success (toast).

Delete budget modal: default, deleting, 404, server error / can't reach server, success.

### `/categories`

| State | What the user sees |
|---|---|
| Loading | Grey rows |
| Success | Alphabetical list (the API sorts by name). Actions: Rename, Delete |
| Empty | "No categories yet. Add one before adding transactions." + "Add category" |
| Server error | Page alert with "Try again" |
| Can't reach server | Page alert with "Try again" |

Category modal: default (add / rename), submitting, 422 (empty or over 50 characters, under Name), 409 duplicate (under Name: "A category with this name already exists"), 404 (rename of a deleted category), server error / can't reach server, success.

Delete category modal: default, deleting, **409 in use** ("Groceries still has transactions or budgets, so it can't be deleted. Move or delete them first."), 404, server error / can't reach server, success.

### `/import` (gap): validate, preview, then confirm

The file is sent twice. The first request only checks it and returns a preview. Nothing is saved. The second request, after the user clicks Confirm, sends the same file again; the server checks it again from scratch and saves the valid rows. The server never trusts the preview it sent earlier.

| State | What the user sees |
|---|---|
| Default | Drop zone + "Choose file", the expected columns, the limits (CSV only, 1 MB, 1,000 rows), a link to a sample CSV |
| File chosen | File name and size, "Check file" button |
| Validating | Spinner "Checking 48 rows…", buttons disabled |
| Preview, all rows valid | "48 rows ready to import" + the first 10 rows as they'll be saved (date, description, category, type, amount) + totals (income, expenses) + **Confirm import** / **Cancel** |
| Preview with row errors | "45 rows ready, 3 rows will be skipped" + error table: Row, Column, Problem (e.g. "Row 12, amount: must be more than 0", "Row 30, category: no category called 'Gym'", "Row 41, description: can't start with =") + **Import 45 rows** / **Cancel** / **Download rows with errors** |
| Preview, every row invalid | "None of the 48 rows can be imported" + error table + **Choose another file** (no confirm button) |
| Importing | Spinner "Importing 45 rows…" |
| Success | "45 transactions imported" + **View transactions** |
| Wrong file type | "Only .csv files can be imported. 'statement.xlsx' looks like an Excel file: save it as CSV first." |
| File too large | "This file is 3.4 MB. The limit is 1 MB (about 1,000 rows)." |
| Too many rows | "This file has 1,850 rows. The limit is 1,000: split it into smaller files." |
| Wrong columns | "The header row doesn't match. Expected: date, description, amount, type, category. Found: Date, Details, Debit, Credit." |
| Bad encoding | "This file isn't UTF-8 text. In Excel, use Save As → CSV UTF-8." |
| Server error | Alert with "Try again" |
| Can't reach server | Alert with "Try again" |

The file-level errors (type, size, rows, columns, encoding) reject the whole file before any row is checked, so they never show a preview.

## 4. User flows

Each step names the frame it lands on, so the prototype links can follow this list.

### 4.1 Add a transaction

1. On `/transactions – default`, click **Add transaction** → `Transaction modal – add` opens as an overlay.
2. Fill in: 14/11/2026, "Tesco Ranelagh", 64.35, Expense, Groceries. Click **Save**.
3. `Transaction modal – submitting` (`POST /transactions/` with `amount_cents: 6435`).
4. Success (201) → modal closes → `/transactions – default` with the new row and toast "Transaction added".
5. Branch, amount left at 0 → 422 → `Transaction modal – 422` (error under Amount). Fix it, Save again → step 4.
6. Branch, the category was deleted in another tab → 404 → `Transaction modal – 404 category`. Pick another, Save → step 4.
7. Branch, server error or no answer → `Transaction modal – server error`. "Try again" → step 3.

### 4.2 Edit and delete a transaction

1. On `/transactions – default`, click **Edit** on a row → `Transaction modal – edit` (filled in).
2. Change the amount, **Save** → `PUT /transactions/{id}` with all five fields → toast "Transaction saved".
3. Branch, the transaction was already deleted → 404 → `Transaction modal – 404 transaction` → **Close** → list reloads.
4. Click **Delete** on a row → `Delete transaction modal – default` → **Delete** → `DELETE /transactions/{id}` → modal closes, row gone, toast "Transaction deleted".
5. **Cancel** closes the modal and changes nothing.
6. Paging: on `/transactions – paginated`, **Next** shows rows 26 to 50 (same frame in the wireframe).

### 4.3 Manage categories

1. `/categories – empty` → **Add category** → `Category modal – add` → "Groceries" → **Save** → `POST /categories/` (201) → `/categories – default`.
2. Add "Groceries" again → 409 → `Category modal – 409 duplicate`. (Today "groceries" in lower case is accepted, because the database compares names letter for letter. Backend task 5.5 fixes that.)
3. **Rename** a row → `Category modal – rename` → `PUT /categories/{id}`.
4. **Delete** a category that has transactions → `Delete category modal – default` → **Delete** → 409 → `Delete category modal – 409 in use`. The only way out is **Close**.
5. **Delete** an unused category → 200 → row gone, toast.

### 4.4 Set a budget

1. `/budgets – empty` → **Set a budget** → `Budget modal – add` (month = the page's month).
2. Groceries, 2026-11, 400.00 → **Save** → `POST /budgets/` with `limit_cents: 40000` → `/budgets – default`, the bar shows spent so far.
3. Set Groceries for 2026-11 again → 409 → `Budget modal – 409 duplicate`, with a link "Edit the existing budget" that opens `Budget modal – edit`.
4. If there are no categories → `/budgets – no categories` → link to `/categories`.

### 4.5 Go over budget and see the alert

1. Eating out has a €150.00 budget for November and €128.60 spent (`/budgets – default`, bar in warning colour at 86%).
2. Add a transaction: "Pizza night", €42.80, Expense, Eating out (flow 4.1).
3. After the save, the page asks for the month's budget status (today: worked out in the browser; after task 5.3: `GET /budgets/status?month=2026-11`) and finds €171.40 spent against €150.00.
4. Toast (danger variant): "Eating out is now €21.40 over budget" with a **View budgets** link.
5. `/budgets – over budget`: the Eating out bar is red and says "€21.40 over". `/ – over budget` shows the same banner on the Overview.

### 4.6 Import a CSV: validate, preview, confirm

1. Nav → **Import** → `/import – default`.
2. Choose `bank-november.csv` → `/import – file chosen` → **Check file** → `/import – validating` (`POST /transactions/import/validate`, nothing saved).
3. Every row valid → `/import – preview` → **Confirm import** → `/import – importing` (`POST /transactions/import`, same file) → `/import – success` → **View transactions** → `/transactions – paginated` (the month now has 54 rows).
4. Some rows invalid → `/import – preview with errors` → **Import 45 rows** → `/import – importing` → `/import – success`. Or **Download rows with errors**, fix them, and start again at step 2.
5. Every row invalid → `/import – preview all invalid` → **Choose another file** → `/import – default`.
6. File-level problems go straight from `/import – validating` to one of: `/import – wrong file type`, `– file too large`, `– too many rows`, `– wrong columns`, `– bad encoding`. Each has **Choose another file** → `/import – default`.
7. **Cancel** on any preview → `/import – default`. Nothing was saved.

## 5. Backend tasks (gaps the UI needs)

### 5.1 CSV import, following the OWASP File Upload Cheat Sheet

Two endpoints, both `multipart/form-data` (FastAPI needs the `python-multipart` package):

- `POST /transactions/import/validate`: checks the file, saves nothing, returns a preview.
- `POST /transactions/import`: checks the same file again from scratch, saves the valid rows in **one database transaction** (all of them or none, if the database fails halfway), returns the count.

Suggested reply for both: `{"valid": 45, "rows": [first 10 valid rows], "errors": [{"row": 12, "column": "amount", "message": "must be more than 0"}], "imported": 0}` (`imported` is 0 for validate). File-level errors answer 400 or 413 with one sentence, like the other errors.

Upload rules:

- [ ] **Treat the file as untrusted.** Nothing from it is trusted until it passes the checks below: not the filename, not the content type, not the content.
- [ ] **Allowlist CSV only.** The extension must be `.csv`. The browser's `Content-Type` is only a hint (Windows sends `application/vnd.ms-excel` for CSV files), so it's never the deciding check. The deciding check is the content: it must decode as text and parse as CSV with the expected header.
- [ ] **Check everything on the server.** The front-end's `accept=".csv"` and size check are only there to help the user, because they're easy to get around.
- [ ] **Enforce the size limit while reading.** 1 MB. Read at most 1 MB + 1 byte, and reject with 413 if there's more, so a huge upload never ends up in memory.
- [ ] **Enforce the row limit.** At most 1,000 data rows, and at most 100 errors returned.
- [ ] **Encoding:** decode as UTF-8 (`utf-8-sig`, so Excel's byte-order mark is accepted). Reject anything else, and any NUL byte, with "bad encoding".
- [ ] **Parse in memory, never save or run it.** `io.StringIO` + Python's `csv` module. The file is never written to disk, never opened by another program, never executed. The original filename is only shown back to the user, as text.
- [ ] **Exact header:** `date,description,amount,type,category`, otherwise "wrong columns".
- [ ] **Validate every row with the Pydantic schema** (`TransactionCreate`), after turning `amount` into cents and `category` into an id. The rules match the form exactly, so a CSV can't save anything the form couldn't.
- [ ] **Guard against CSV formula injection.** A spreadsheet runs a cell that starts with `=`, `+`, `-`, `@`, tab or carriage return as a formula. On import, reject descriptions that start with one of these (a row error). On export (the "download rows with errors" file and any future export), put a `'` in front of any such cell, and quote every field.
- [ ] **Re-validate on confirm.** The confirm request gets the file again and runs every check again. It never accepts preview data from the browser.
- [ ] Tests for each rule: wrong extension, over 1 MB, 1,001 rows, wrong header, Latin-1 file, formula in a description, one bad row among good ones, all rows bad.

### 5.2 Budget alerts (Phase B, Observer)

When a transaction is saved, the Observer's budget checker finds categories that went over. The UI can learn about it in one of two ways:

- the `POST`/`PUT /transactions/` reply includes the alerts it triggered, e.g. `"alerts": [{"category": "Eating out", "over_by_cents": 2140}]`, **or**
- the page calls the budget status endpoint (5.3) after each save.

The toast and banner look the same either way.

### 5.3 Server-side budget status endpoint

- [ ] `GET /budgets/status?month=2026-11` returns one item per budget: `category_id`, `category_name`, `limit_cents`, `spent_cents`, `left_cents`, `percent_used`, `status` (`ok` under 80%, `warning` 80 to 100%, `over` above 100%).
- [ ] It replaces the adding-up in the browser (`frontend/src/summary.js`) for the Budgets page, the Overview bars and the over-budget alert. Phase C's library can do the maths.
- [ ] Tests: no transactions, exactly at the limit, over the limit, income not counted as spending.

### 5.4 Transaction pagination

- [ ] `GET /transactions/?limit=25&offset=0` (keep the month and category filters). Limit between 1 and 100.
- [ ] The UI needs the total to show "Showing 1 to 25 of 54" and the page numbers: either an `X-Total-Count` header or a reply shaped like `{"items": [...], "total": 54}`. The second changes the reply for every caller, so the front-end and tests change with it.

### 5.5 Case-insensitive category names

- [ ] "Groceries" and "groceries" should clash with 409. Compare names in lower case on create and rename (and in the CSV import's category lookup).

### 5.6 Smaller gaps (no task yet)

- `GET /categories/` doesn't say how many transactions or budgets use each category, so the UI only finds out from the 409 on delete.
- No "move all transactions from category A to B".
- No text search (`?q=tesco`), no type filter, no sort options.
- No undo after delete, so every delete asks first.
- No list of "months with data", so the month picker steps freely through any month.
- Budgets can't be copied from last month.
- CORS only allows `http://localhost:5173`. A hosted front-end needs the CORS change from the front-end hosting design.

## 6. Sample data for the wireframes (November 2026)

Categories: Eating out, Entertainment, Groceries, Rent, Salary, Transport, Utilities.

| Date | Description | Category | Type | Amount |
|---|---|---|---|---|
| 28/11/2026 | Salary, Acme Ltd | Salary | Income | €2,800.00 |
| 27/11/2026 | Pizza night | Eating out | Expense | €42.80 |
| 21/11/2026 | Electric Ireland | Utilities | Expense | €92.10 |
| 18/11/2026 | Leap card top-up | Transport | Expense | €30.00 |
| 14/11/2026 | Tesco Ranelagh | Groceries | Expense | €64.35 |
| 12/11/2026 | Cinema, Lighthouse | Entertainment | Expense | €24.00 |
| 08/11/2026 | Lidl Rathmines | Groceries | Expense | €48.90 |
| 06/11/2026 | Lunch with Sam | Eating out | Expense | €128.60 |
| 01/11/2026 | Rent, November | Rent | Expense | €1,250.00 |

For the 422 frames, type `0.00` as the amount (or leave Description empty).

The wireframes tell one story. **Default frames show November before "Pizza night"**: 8 transactions, Income €2,800.00, Expenses €1,637.95, Balance €1,162.05, Eating out at €128.60 of €150.00 (86%, warning). **Adding Pizza night** (flow 4.1 and 4.5) gives the full table above: Expenses €1,680.75, Balance €1,119.25, Eating out €21.40 over. The over-budget and "saved" frames use these numbers.

Budgets for 2026-11: Groceries €400.00 (spent €113.25, 28%), Eating out €150.00 (spent €171.40, over by €21.40), Transport €100.00 (spent €30.00, 30%), Entertainment €50.00 (spent €24.00, 48%).

Import sample: `bank-november.csv`, 48 rows, 3 invalid (rows 12, 30, 41 as above). After importing the 45 valid rows, November has 54 transactions; the paginated frame shows "Showing 1 to 25 of 54".

## 7. Components to build in Figma

| Component | Variants |
|---|---|
| Button | primary, secondary, danger, link × default, disabled, loading |
| Input | text, number (€), date, month, select, toggle × default, error (with message) |
| Table row | transaction, budget, category, import error |
| Alert / toast | success, warning, danger, info |
| Empty state | one layout, text and buttons swapped per screen |
| Modal | form, confirm × default, submitting, error |
| Budget bar | normal, warning, over |
| Nav bar | one variant per active tab |
| Pagination | one variant |
| Summary card | one layout, label and amount swapped |

## 8. Frame list

Named `route – state`, 1440 px wide.

- `/ – default`, `– loading`, `– empty`, `– over budget`, `– server error`, `– can't reach server`
- `/transactions – default`, `– loading`, `– paginated`, `– empty`, `– empty filter`, `– server error`, `– can't reach server`
- Overlays on `/transactions`: `Transaction modal – add`, `– edit`, `– submitting`, `– 422`, `– 404 category`, `– 404 transaction`, `– server error`; `Delete transaction modal – default`, `– 404`
- `/budgets – default`, `– loading`, `– empty`, `– no categories`, `– over budget`, `– server error`, `– can't reach server`
- Overlays on `/budgets`: `Budget modal – add`, `– edit`, `– 422`, `– 404 category`, `– 409 duplicate`, `– server error`; `Delete budget modal – default`
- `/categories – default`, `– loading`, `– empty`, `– server error`, `– can't reach server`
- Overlays on `/categories`: `Category modal – add`, `– rename`, `– 422`, `– 409 duplicate`, `– 404`; `Delete category modal – default`, `– 409 in use`
- `/import – default`, `– file chosen`, `– validating`, `– preview`, `– preview with errors`, `– preview all invalid`, `– importing`, `– success`, `– wrong file type`, `– file too large`, `– too many rows`, `– wrong columns`, `– bad encoding`, `– server error`, `– can't reach server` (all marked "gap: API not built")
