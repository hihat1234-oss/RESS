# RESS Starter API

A working starter scaffold for **Real Estate Signal System (RESS)**.

This MVP does six things:
- creates listings
- ingests listing-level signal events
- calculates a market-relative demand score
- derives momentum and price pressure
- benchmarks each listing against segmented comparable inventory
- generates plain-English recommendations

## Stack
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL or SQLite
- Alembic

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the docs at:

```bash
http://127.0.0.1:8000/docs
```

## Database

By default, the app will run with SQLite if no `.env` is present.

For PostgreSQL, set:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ress
```

## Core API flow

### 1. Create a listing

```bash
curl -X POST http://127.0.0.1:8000/listings \
  -H "Content-Type: application/json" \
  -d '{
    "id": "listing_123",
    "address": "123 Main St, Nashville, TN",
    "mls_id": "MLS-456",
    "status": "active",
    "property_type": "single_family",
    "city": "Nashville",
    "state": "TN",
    "zip_code": "37215",
    "list_price": 650000,
    "bedrooms": 4,
    "bathrooms": 3,
    "sqft": 2800
  }'
```

### 2. Post signal events

```bash
curl -X POST http://127.0.0.1:8000/signals/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "events": [
      {"id": "sig_1", "listing_id": "listing_123", "signal_type": "view", "signal_value": 120, "source": "portal"},
      {"id": "sig_2", "listing_id": "listing_123", "signal_type": "save", "signal_value": 11, "source": "portal"},
      {"id": "sig_3", "listing_id": "listing_123", "signal_type": "showing_request", "signal_value": 4, "source": "showing_service"},
      {"id": "sig_4", "listing_id": "listing_123", "signal_type": "return_visitor", "signal_value": 19, "source": "portal"}
    ]
  }'
```

### 3. Recalculate score

```bash
curl -X POST http://127.0.0.1:8000/listings/listing_123/recalculate
```

### 4. Generate recommendations

```bash
curl -X POST http://127.0.0.1:8000/listings/listing_123/recommendations/generate
```

### 5. Read output

```bash
curl http://127.0.0.1:8000/listings/listing_123/scores
curl http://127.0.0.1:8000/listings/listing_123/recommendations
```

## What changed in this version

Scoring cohorts are now segmented by:
- property type
- ZIP code when available
- city/state fallback when ZIP is missing
- price band
- bedroom / bathroom similarity
- square footage range

That makes the benchmark logic less blunt. A condo should not be scored against a suburban single-family home, and a Green Hills listing should not be treated like generic statewide inventory unless the data is thin.

## Notes

This is still a narrow rules-based prototype.
That is correct for this stage.

The next serious upgrades are:
- add pending and sold comp behavior
- add seasonality and days-on-market weighting
- add tenancy, auth, and event provenance
- add background jobs for recalculation
- plug in MLS and portal feeds


## Deploy to Render

### 1. Push to GitHub

The project now includes:
- `.gitignore`
- `render.yaml`
- `Procfile`

From the project root:

```bash
git init
git add .
git commit -m "Initial RESS starter"
git branch -M main
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

### 2. Deploy on Render

Option A: dashboard
- create a new Web Service from your GitHub repo
- build command: `pip install -r requirements.txt`
- start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- add `DATABASE_URL` from your Render Postgres instance

Option B: Blueprint
- keep `render.yaml` in the repo
- in Render, choose **New Blueprint Instance**
- point it at the repo
- Render will create both the web service and Postgres database

### 3. Verify the deploy

Open:

```bash
https://YOUR-SERVICE.onrender.com/health
https://YOUR-SERVICE.onrender.com/docs
```

### 4. Important note

This scaffold still creates tables at startup via `Base.metadata.create_all(bind=engine)`.
That is acceptable for a private prototype.
For a cleaner production path, switch to Alembic migrations and remove automatic table creation from `app/main.py`.


## API authentication

All API endpoints except `/health` require an API key in the `x-api-key` header.

Example:

```bash
curl -X GET http://localhost:8000/listings/some-id \
  -H "x-api-key: replace-with-a-long-random-secret"
```

Set the key in your environment:

```env
API_KEY=replace-with-a-long-random-secret
```

In Swagger UI, click **Authorize** and paste the API key value.


## Recent additions

- Soft deletion for organizations and listings
- API key revocation endpoint
- Per-organization usage logs and usage summary

### New endpoints

- `DELETE /listings/{listing_id}`
- `DELETE /auth/organizations/{organization_id}`
- `POST /auth/api-keys/{api_key_id}/revoke`
- `GET /auth/organizations/{organization_id}/usage-logs`
- `GET /auth/organizations/{organization_id}/usage-summary`
