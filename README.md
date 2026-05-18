# NCA Backend

A FastAPI backend for collecting and querying app analytics — sessions, screen views, HTTP performance, crashes, and device usage.

- **Framework:** FastAPI (Python 3.11)
- **Database:** PostgreSQL 15
- **Migrations:** Alembic
- **Auth:** JWT (bearer) for user accounts; SHA-256 hashed app tokens for ingestion clients
- **Container:** Docker Compose (app + db + pgAdmin)

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Quick start (Docker — recommended)](#quick-start-docker--recommended)
3. [Local Python setup (no Docker)](#local-python-setup-no-docker)
4. [Environment variables](#environment-variables)
5. [Database migrations](#database-migrations)
6. [Verifying the setup](#verifying-the-setup)
7. [Connecting pgAdmin to the database](#connecting-pgadmin-to-the-database)
8. [API reference](#api-reference)
9. [Project structure](#project-structure)
10. [Common tasks](#common-tasks)
11. [Troubleshooting](#troubleshooting)
12. [Known caveats](#known-caveats)

---

## Prerequisites

You need **one** of the two setups below installed on your machine.

### For the Docker path (easiest)
- **Docker Desktop** 4.x or newer — https://www.docker.com/products/docker-desktop/
  - Make sure Docker Desktop is running before you run any `docker compose` command.
- `git` — to clone the repo.

That's it. You do **not** need Python or PostgreSQL on your host.

### For the local Python path
- **Python 3.11** specifically (the Dockerfile pins 3.11; other versions may work but aren't tested).
  - macOS: `brew install python@3.11`
  - Ubuntu: `sudo apt install python3.11 python3.11-venv`
  - Windows: https://www.python.org/downloads/
- **PostgreSQL 15** running somewhere your app can reach (you can still use the dockerized Postgres for this — see below).
- `git`.
- On macOS, you may need `libpq` if installing `psycopg2-binary` fails: `brew install libpq`.

---

## Quick start (Docker — recommended)

```bash
# 1. Clone
git clone https://github.com/igitonga/nca_backend.git
cd nca_backend

# 2. Create your .env (copy the example, then edit the secret)
cp .env.example .env
# IMPORTANT: open .env and change SECRET_KEY to a long random string.
# Quick way to generate one:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# 3. Build and start everything (app, Postgres, pgAdmin)
docker compose up --build

# 4. In a second terminal, apply the database schema
docker compose exec app alembic upgrade head
```

You should now have:

| Service  | URL                            | Notes                                          |
|----------|--------------------------------|------------------------------------------------|
| API      | http://localhost:8000          | `GET /` returns a welcome JSON blob            |
| Swagger  | http://localhost:8000/docs     | Interactive API explorer                       |
| ReDoc    | http://localhost:8000/redoc    | Alternative API docs                           |
| pgAdmin  | http://localhost:5050          | Login with `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` from `.env` |
| Postgres | `localhost:5432`               | Available to host tools too (psql, DBeaver, …) |

To **stop** everything: `Ctrl-C` in the compose terminal, then `docker compose down`.
To wipe the database volume and start fresh: `docker compose down -v`.

---

## Local Python setup (no Docker)

Use this if you prefer running the app process directly on your machine (faster hot-reload, easier debugger attachment). You can still run **Postgres in Docker** while running the app on your host — that's the easiest hybrid.

```bash
# 1. Clone and enter
git clone https://github.com/igitonga/nca_backend.git
cd nca_backend

# 2. Create and activate a virtualenv
python3.11 -m venv .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows PowerShell

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure env
cp .env.example .env
# Edit .env:
#  - set SECRET_KEY to a random string (see Quick start)
#  - set POSTGRES_HOST=localhost (instead of `db`) when running outside Docker
```

Now start Postgres (pick **one** option):

**Option A — Postgres via Docker (recommended):**
```bash
docker compose up -d db
```
This starts only the Postgres service on `localhost:5432` with the credentials from `.env`.

**Option B — Postgres installed on your host:**
Create a database named `nca` (or whatever you set in `POSTGRES_DB`) and a user matching `POSTGRES_USER` / `POSTGRES_PASSWORD`.

Then apply the schema and run the app:

```bash
alembic upgrade head
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs.

---

## Environment variables

All variables live in `.env` (copy from `.env.example`). The app loads them via `python-dotenv`.

| Variable                       | Purpose                                                    | Example                  |
|--------------------------------|------------------------------------------------------------|--------------------------|
| `POSTGRES_DB`                  | Database name                                              | `nca`                    |
| `POSTGRES_USER`                | DB username                                                | `postgres`               |
| `POSTGRES_PASSWORD`            | DB password                                                | `postgres`               |
| `POSTGRES_HOST`                | DB hostname. **`db` for Docker, `localhost` for local Python.** | `db` / `localhost`   |
| `POSTGRES_PORT`                | DB port                                                    | `5432`                   |
| `PGADMIN_EMAIL`                | Login email for pgAdmin web UI                             | `admin@example.com`      |
| `PGADMIN_PASSWORD`             | Login password for pgAdmin                                 | `password`               |
| `SECRET_KEY`                   | **REQUIRED** — JWT signing key. App will refuse to start if missing. Use a long random string. | `<random 48 bytes>` |
| `ALGORITHM`                    | JWT algorithm (default `HS256`)                            | `HS256`                  |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | JWT lifetime in minutes (default `60`)                     | `3600`                   |
| `ENVIRONMENT`                  | Free-form environment tag                                  | `development`            |

> **Never commit `.env`.** It's already in `.gitignore` and `.dockerignore`.

---

## Database migrations

Migrations live in [alembic/versions/](alembic/versions/) and run via Alembic.

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back the latest migration
alembic downgrade -1

# Show current revision
alembic current

# Show full history
alembic history --verbose

# Create a new migration (after changing a model)
alembic revision --autogenerate -m "describe your change"
```

When running **inside Docker**, prefix each command with `docker compose exec app ` — for example: `docker compose exec app alembic upgrade head`.

Current migration chain:

1. `001_create_users_table` — `users` table
2. `002_create_app_tokens_table` — `app_tokens` and `metric_events` tables
3. `003_remove_user_id_from_app_tokens` — drops `user_id` FK from `app_tokens`
4. `004_add_role_to_users` — adds `role String NOT NULL DEFAULT 'admin'` to `users`

---

## Verifying the setup

After the app is up and migrations are applied:

```bash
# 1. Root health check
curl http://localhost:8000/
# -> {"message":"Welcome to my backend"}

# 2. Register a user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","username":"dev","password":"hunter2"}'

# 3. Log in to get a JWT
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"hunter2"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
echo "JWT: $TOKEN"

# 4. Mint an app token (unauthenticated by design)
APP_TOKEN_ID=$(curl -s -X POST http://localhost:8000/app-tokens \
  -H "Content-Type: application/json" \
  -d '{"label":"my first app"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['token_id'])")
echo "App token id: $APP_TOKEN_ID"

# 5. Query metrics (requires JWT + the app_token_id from step 4)
curl "http://localhost:8000/metrics/summary?app_token_id=$APP_TOKEN_ID&time_range_days=30" \
  -H "Authorization: Bearer $TOKEN"
```

If all five succeed, the stack is wired correctly.

---

## Connecting pgAdmin to the database

`docker compose up` starts a pgAdmin instance at **http://localhost:5050**, but the Postgres server connection inside pgAdmin is **not pre-configured** — you need to register it once. The `nca` database itself is auto-created by the Postgres container on first start (driven by `POSTGRES_DB` in `.env`), so as soon as the server connection is wired, the database appears.

### One-time setup

1. **Wait for the stack to be healthy.** Run `docker compose ps` and confirm the `db` container shows `(healthy)`. If it's still `(starting)`, give it a few seconds — `alembic` and pgAdmin will both fail to connect until the healthcheck passes.

2. **Open pgAdmin in your browser:** http://localhost:5050

3. **Log in** with the values of `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` from your `.env`. With the defaults from `.env.example`:
   - Email: `admin@example.com`
   - Password: `password`

4. **Register the Postgres server.** In the left sidebar:
   - Right-click **Servers** → **Register** → **Server...**
   - **General** tab:
     - *Name:* anything memorable, e.g. `nca local`
   - **Connection** tab:
     - *Host name/address:* **`db`** ← the docker-compose service name. pgAdmin and Postgres are on the same internal Docker network (`app-network`), and that's the hostname pgAdmin uses to reach the DB.
       > Do **not** put `localhost` here. From pgAdmin's perspective (inside its own container), `localhost` is itself, not Postgres.
     - *Port:* `5432`
     - *Maintenance database:* `postgres`
     - *Username:* value of `POSTGRES_USER` (default `postgres`)
     - *Password:* value of `POSTGRES_PASSWORD` (default `postgres`)
     - *Save password?* tick it for convenience (dev only).
   - Click **Save**.

5. **Verify in the tree.** Expand the new server node in the sidebar:
   - `Servers → nca local → Databases` — you should see your DB (default name `nca`).
   - `nca → Schemas → public → Tables` — after you've run `alembic upgrade head`, this lists `users`, `app_tokens`, `metric_events`, and `alembic_version`. Before migrations, it's empty.

### Running queries

Right-click the `nca` database → **Query Tool** opens a SQL editor. Try:

```sql
SELECT id, email, username, role, created_at FROM users;
SELECT id, label, created_at FROM app_tokens;
SELECT event_type, COUNT(*) FROM metric_events GROUP BY event_type;
```

### Manually creating a database (rarely needed)

The Postgres container auto-creates `POSTGRES_DB` on first startup, so you almost never need to. If you do want a second DB for some reason:

- **In pgAdmin:** right-click **Databases** under your registered server → **Create** → **Database...**, fill in a name, click **Save**.
- **From your host shell:**
  ```bash
  PGPASSWORD=postgres psql -h localhost -U postgres -c "CREATE DATABASE my_other_db;"
  ```

### Connecting other tools (DBeaver, TablePlus, psql) from your host

The Postgres container publishes port 5432 to your host, so external tools can use:

- **Host:** `localhost`
- **Port:** `5432`
- **Database:** `nca` (or whatever `POSTGRES_DB` is)
- **Username / password:** from `.env`

> The hostname mismatch is intentional: external tools running **on your host** use `localhost`, because that's where the published port lives. pgAdmin (which itself runs **inside** a Docker container) uses `db`, because that's the Docker-network hostname for the Postgres service. Same database, two different network paths.

### pgAdmin troubleshooting

- **"Unable to connect to server: could not translate host name..."** — you probably typed `localhost` for *Host name/address*. Change it to `db`.
- **"Connection refused"** — Postgres isn't healthy yet. `docker compose ps` should show `db` as `(healthy)`. Wait, or check `docker compose logs db`.
- **Server registered but database list is empty** — Postgres is up, but the `POSTGRES_DB` value from `.env` was empty or wrong when the container first started. Easiest fix: `docker compose down -v` (destroys data!) then `docker compose up` so the DB is re-initialized with the current `.env`.
- **pgAdmin forgets your server after a restart** — it shouldn't; pgAdmin state lives in the `pgadmin_data` Docker volume. If you ran `docker compose down -v`, that volume was removed and you'll need to re-register.

---

## API reference

All endpoints return JSON. Errors come back as `{"detail": "..."}` with the appropriate 4xx/5xx status.

### Auth (public)

| Method | Path             | Body                                              | Returns                                                  |
|--------|------------------|---------------------------------------------------|----------------------------------------------------------|
| POST   | `/auth/register` | `{ email, username, password }`                   | The created user (currently includes the hashed password — see *Known caveats*) |
| POST   | `/auth/login`    | `{ email, password }`                             | `{ access_token, token_type, expiry }`                   |

### App tokens (public)

| Method | Path           | Body              | Returns                                                  |
|--------|----------------|-------------------|----------------------------------------------------------|
| POST   | `/app-tokens`  | `{ label }`       | `{ token, token_id, label, created_at }` — `token` is shown **once**; store it. |

> The raw token is returned only on creation. Only the SHA-256 hash is persisted.

### Metrics (JWT required)

All metric endpoints require a `Bearer <jwt>` header and a `?app_token_id=<id>` query parameter.

| Method | Path                                | Notable query params                                                       |
|--------|-------------------------------------|----------------------------------------------------------------------------|
| GET    | `/metrics/summary`                  | `time_range_days` (1-365), `include_trends`                                |
| GET    | `/metrics/screens`                  | `limit` (1-50), `time_range_days`, `method` = `join`\|`direct`             |
| GET    | `/metrics/http`                     | `time_range_days` (1-90), `include_timeline`, `interval_hours`             |
| GET    | `/metrics/crashes`                  | `time_range_days` (1-365)                                                  |
| GET    | `/metrics/devices`                  | `limit` (1-100), `offset`, `time_range_days`, `sort_by`, `sort_order`      |
| DELETE | `/metrics/session/{session_id}`     | Admin-gated (currently always 403 — see *Known caveats*)                   |

The interactive Swagger UI at `/docs` has the full parameter list and lets you try every endpoint.

---

## Project structure

```
.
├── alembic/                  Alembic config + migration scripts
│   ├── env.py
│   └── versions/             001..004
├── alembic.ini
├── app/
│   ├── api.py                FastAPI app (entry point — `uvicorn app.api:app`)
│   ├── db/database.py        Engine, SessionLocal, Base, get_db dependency
│   ├── models/               SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── appToken.py
│   │   └── metricEvent.py
│   ├── schemas/              Pydantic request/response schemas
│   ├── routers/              FastAPI routers (auth, app tokens, metrics)
│   ├── services/             Business logic layer (queries, aggregations)
│   └── utils/                Auth helpers (JWT, password hashing, current user)
├── docker-compose.yml        app + db + pgAdmin
├── Dockerfile                Python 3.11-slim image for the app
├── requirements.txt
├── .env.example              Copy to `.env` and customize
└── README.md
```

---

## Common tasks

**Watch app logs:** `docker compose logs -f app`
**Open a shell inside the app container:** `docker compose exec app bash`
**Run psql against the dockerized DB from your host:**
```bash
PGPASSWORD=postgres psql -h localhost -U postgres -d nca
```
**Connect pgAdmin to the dockerized DB:** see [Connecting pgAdmin to the database](#connecting-pgadmin-to-the-database) for the full walkthrough.

**Reset the database (destroys data):**
```bash
docker compose down -v
docker compose up -d db
docker compose exec app alembic upgrade head
```

**Format / lint:** no formatter or linter is wired into the project yet.

**Tests:** there are no tests yet.

---

## Troubleshooting

**`SECRET_KEY environment variable is required` at startup**
Your `.env` is missing `SECRET_KEY` or you forgot to copy `.env.example`. Set a value and restart.

**`could not translate host name "db" to address`**
You're running the app on your host (not in Docker) but `POSTGRES_HOST=db` in `.env`. Change it to `localhost` (or whatever your DB host actually is).

**`relation "users" does not exist`**
You haven't applied migrations. Run `alembic upgrade head` (or `docker compose exec app alembic upgrade head`).

**`psycopg2` install fails on macOS**
Install Postgres client libs: `brew install libpq` and re-run `pip install -r requirements.txt`. If it still fails, try `pip install psycopg2-binary` separately.

**Port 8000 / 5432 / 5050 already in use**
Stop whatever else is using them, or edit the `ports:` mappings in `docker-compose.yml` to a free host port (e.g. `"8001:8000"`).

**Docker mounts the wrong code (changes not reflected)**
The `app:` service mounts `./app` into the container. If you change files **outside** the `app/` directory (like Alembic), rebuild: `docker compose up --build`.

**`alembic upgrade head` says "Can't locate revision identified by..."**
Your DB may be at a revision newer than the codebase, or someone deleted a migration file. Inspect: `alembic current` and `alembic history`. As a last resort against a dev DB: `docker compose down -v` then re-run.

---

## Known caveats

These are deliberate trade-offs in the current state — flagging so you don't get surprised.

- **`POST /app-tokens` is unauthenticated.** Anyone who can reach the API can mint app tokens. Acceptable for early dev; you'll want to gate this before exposing the API publicly.
- **`POST /auth/register` returns the hashed password** in its response body. Change `response_model` to `UserResponse` before going to prod.
- **`require_admin_role` always returns 403.** The `role` column now exists (migration `004`, default `'admin'`), but the dependency hasn't been re-wired to actually consult it. So `DELETE /metrics/session/{id}` is functionally disabled.
- **Metric endpoints expect Postgres.** They use `attributes->>'x'` JSON accessors via JSONB — they will not work against SQLite.
- **No tests, linter, or CI** are configured yet.
- **`get_metrics_summary?include_trends=true`** returns a `"trends": null` placeholder; the underlying service method is not implemented.

If anything in this README is wrong or unclear when you try it, please open an issue (or a PR) — we want the setup path to stay under 10 minutes.
