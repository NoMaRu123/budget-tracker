# budget-tracker

A budget and spending tracker, built as a SaaS app for the Cloud Application Development module at the National College of Ireland (2026). Work in progress.

## Stack

- Backend: FastAPI (Python), SQLAlchemy, SQLite
- Front-end: React with Vite
- Infrastructure: Terraform on AWS EC2
- Tests: pytest

## Project layout

```
backend/    ReST API: routes, database models, validation, tests
frontend/   React app that calls the API
infra/      Terraform files that create the AWS server and start the app
.github/    GitHub Actions workflows: CI (lint + tests), deploy and destroy
```

## Run it locally

Backend, in one terminal from the project root:

```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
cd backend
uvicorn main:app --reload
```

Front-end, in a second terminal:

```
cd frontend
npm install
npx vite
```

The app runs at http://localhost:5173 and the API docs at http://localhost:8000/docs.

## Tests

```
cd backend
pytest
```
