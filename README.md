# Minakshi Polymers API

FastAPI + PostgreSQL backend with JWT-based registration and login.

## Setup

1. Create the database (psql or pgAdmin):
   ```sql
   CREATE DATABASE minakshi_polymers;
   ```
2. Copy `.env.example` to `.env` and set `DATABASE_URL` to your Postgres username/password, plus a long random `JWT_SECRET_KEY`.
3. Install and run:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
4. Open http://127.0.0.1:8000/docs. Tables are created automatically on startup.

## Endpoints

| Method | Path                    | Auth   | Body |
|--------|-------------------------|--------|------|
| POST   | `/api/v1/auth/register` | –      | `full_name`, `email`, `phone` (optional), `password` (8–72 chars) |
| POST   | `/api/v1/auth/login`    | –      | `email`, `password` → returns `access_token` + user |
| GET    | `/api/v1/auth/me`       | Bearer | – |
| GET    | `/health`               | –      | – |

## Structure

```
app/
  main.py            app factory, router registration, table creation
  core/config.py     settings loaded from .env
  core/security.py   bcrypt hashing, JWT create/decode
  db/session.py      engine, session, Base, get_db dependency
  models/user.py     users table
  schemas/user.py    request/response models
  api/deps.py        get_current_user dependency
  api/routes/auth.py register / login / me
```
