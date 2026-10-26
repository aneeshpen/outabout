# DigiPass Backend (FastAPI)

The DigiPass REST API. It replaces the previous Node.js + Express backend and
serves the **unchanged** React frontend in `../frontend`.

---

## 1. Architecture

Each request travels through the same four layers. Nothing skips a layer: a
router never runs a query, and a repository never decides a business rule.

```
HTTP request
    │
    ▼
routers/        Declare the URL, method, request/response schema and the
                role required. Parse input, call one service, return.
    │
    ▼
services/       The business rules: "a market pass must start and end on the
                same day", "a student who is checked out may not apply again".
                Raises HTTPException for every rule violation.
    │
    ▼
repositories/   Every SQLAlchemy query in the project lives here, expressed in
                domain terms ("find the approved pass covering this date").
    │
    ▼
models/         SQLAlchemy entities mapped onto the existing PostgreSQL tables.
```

Supporting packages:

| Package | Responsibility |
| --- | --- |
| `core/config.py` | Every setting, read from the environment / `.env`. No credential is hard-coded. |
| `core/security.py` | bcrypt password hashing and HS256 JWT creation/validation. |
| `dependencies/database.py` | Engine, session factory and the `get_db` dependency (opens and always closes a session). |
| `dependencies/auth.py` | `get_current_user` and `require_roles(...)` - the FastAPI equivalent of the old Express middleware. |
| `schemas/` | Pydantic request/response contracts. `UserPublic` has no `password` field, so the hash cannot leak. |
| `utils/` | Timezone helpers, barcode decoding, photo storage, parent notifications. |

### Why each layer exists

* **Routers** are the only place that knows about HTTP. That makes the rules
  below them testable without a web request.
* **Schemas** are the contract. Because the router declares
  `response_model=UserPublic`, a password hash physically cannot reach the
  client even if a service hands back a full ORM row.
* **Services** hold the rules. Changing "late return" from 9 PM to 10 PM is a
  one-line change in one file, not a hunt through route handlers.
* **Repositories** isolate the database. Moving from SQLite to PostgreSQL, or
  rewriting a query for performance, touches nothing above them.
* **Dependencies** make authorisation declarative: a router says
  `Depends(require_warden)` and an unauthorised request never reaches the
  service.

### Mapping from the old Express backend

| Express | FastAPI |
| --- | --- |
| `app.use('/pass', passesRouter)` | `app.include_router(passes.router)` with `prefix="/pass"` |
| `getCurrentUser` middleware | `Depends(get_current_user)` |
| `requireRole(['warden'])` middleware | `Depends(require_warden)` |
| `zod` schema + `validate()` middleware | Pydantic request models (FastAPI validates before the handler runs) |
| `res.status(403).json({detail})` | `raise HTTPException(status_code=403, detail=...)` |
| Prisma `findFirst({where, orderBy, include})` | Repository method using `select(...)` + `selectinload(...)` |
| `bcrypt` / `jsonwebtoken` | `bcrypt` / `PyJWT` (same algorithms, interchangeable hashes and tokens) |

---

## 2. Requirements

* Python 3.11+ (developed and tested on 3.12)
* A database: PostgreSQL in production, SQLite out of the box for local work

---

## 3. Setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

cp .env.example .env          # then edit .env
```

### Configuration (`.env`)

| Variable | Meaning |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@host:5432/db` in production; defaults to `sqlite:///./digipass.db`. |
| `CREATE_TABLES_ON_STARTUP` | Emits `CREATE TABLE IF NOT EXISTS` on boot. Never drops or alters anything. |
| `SECRET_KEY` | JWT signing key. Use the **same value the old backend used** if existing tokens must stay valid. At least 32 random characters. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime (default 20, matching the previous backend). |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins. The Vite dev server runs over HTTPS, so include the `https://` form. |
| `DEFAULT_PASSWORD` | Password given to users created through the admin console or CSV import. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_BUCKET` | Optional. When set, student photos go to the Supabase bucket and the guard screen gets a short-lived signed URL. When empty, photos are written to `backend/uploads/` and served from `/uploads`. |

`.env` is git-ignored. Never commit real credentials.

---

## 4. Running

```bash
uvicorn app.main:app --reload --port 8000
```

* API: <http://localhost:8000>
* Interactive docs: <http://localhost:8000/docs>

Optional, for local development only - creates one demo account per role
(purely additive; it never deletes or overwrites a row):

```bash
python seed_dev_data.py
```

---

## 5. Database

The SQLAlchemy models map onto the **existing** DigiPass schema, including the
five PostgreSQL enum types (`Role`, `PassType`, `PassStatus`, `LogAction`,
`StudentStatus`). Pointing `DATABASE_URL` at the current production database
therefore needs no migration and no data change.

### Verify a database before trusting it

After pointing `DATABASE_URL` at a real instance, run:

```bash
python check_database.py
# or, without editing .env first:
python check_database.py --url "postgresql+psycopg2://user:pass@host:5432/db"
```

It is strictly read-only - it connects, reads the system catalogs, counts rows
and loads one object through the ORM. It never creates, alters, drops or
writes anything. It reports missing tables and columns, enum types whose
values do not match the application (the failure mode that silently breaks
writes - for example a database still carrying `checked in` instead of
`checked_in`), existing row counts, and whether the configuration is still on
placeholder values. Exit code 0 means the backend can run against it.

Once it passes you can set `CREATE_TABLES_ON_STARTUP=false`, since the schema
is already in place.

`docs/schema.sql` is the reference DDL for provisioning a fresh PostgreSQL
database. The application never executes it.

| Table | Purpose |
| --- | --- |
| `users` | Students, wardens, guards and admins. `is_active=false` is the soft delete. |
| `leave_pass` | One row per market / leave pass request. |
| `logs` | Gate scans: one row per check-out / check-in. |

Timestamps are stored naive in UTC and always serialised with an explicit `Z`,
so the browser renders gate scan times correctly in IST.

---

## 6. API

All endpoints except `POST /login/` require `Authorization: Bearer <token>`.

### Login

| Method | Path | Role | Body / Notes |
| --- | --- | --- | --- |
| POST | `/login/` | - | `{"username", "password"}` (JSON). Returns `{access_token, token_type, user}`. |

### Passes

| Method | Path | Role | Notes |
| --- | --- | --- | --- |
| POST | `/pass/` | student | `{pass_type, leave_start, leave_end}` |
| GET | `/pass/my_pass` | student | Own history, newest first, with the latest gate scan |
| POST | `/pass/convert` | student | `{leave_end}` - turns the latest market pass into a leave pass |
| POST | `/pass/extend/{pass_id}` | student | `{new_leave_end}` |
| GET | `/pass/pending` | warden | Approval queue, with applicant contact details |
| GET | `/pass/all` | warden | Every pass |
| PUT | `/pass/status/{pass_id}` | warden | `{pass_status, remark}` |
| PUT | `/pass/remark/{pass_id}` | warden, admin | `{remark}` |
| GET | `/pass/late-returns` | warden, admin | Today's market passes checked in at/after 9 PM IST |
| GET | `/pass/logs?page=&limit=` | warden, admin | Latest scan per pass in the last 24 h, paginated |

### Verification (gate)

| Method | Path | Role | Notes |
| --- | --- | --- | --- |
| GET | `/verify/manual/{college_id}` | guard | Used by both the manual entry and the in-browser scanner |
| POST | `/verify/scan` | guard | `multipart/form-data` image of an ID card barcode |
| POST | `/verify/checkout/{pass_id}` | guard | Records the student leaving |
| POST | `/verify/checkin/{pass_id}` | guard | Records the student returning |

### Admin

| Method | Path | Role | Notes |
| --- | --- | --- | --- |
| POST | `/admin/users` | admin | `multipart/form-data`, optional `photo` |
| POST | `/admin/users/bulk` | admin | CSV with `id,first_name,last_name[,role,contact_details,parent_email,parents_phone]` |
| DELETE | `/admin/users/{id}` | admin | Soft delete (keeps the pass history) |
| PUT | `/admin/users/{id}/password` | admin | `{new_password}` |
| POST | `/user/` | admin | JSON create with an explicit password |
| DELETE | `/user/{id}` | admin | Hard delete; admin accounts are protected |

---

## 7. Business rules

A student may apply for a pass only when **all** of these hold:

1. No other request of theirs is `pending`.
2. The gate logs do not show them currently out of the hostel.
3. They have no approved, still-valid pass that has never been used.
4. A market pass starts and ends on the same day.

Other rules:

* A leave pass can be extended only while it is `pending` or `approved`, has
  not expired, has not been checked back in, and only to a later date. An
  extension resets the pass to `pending`.
* The gate accepts a pass only when it is `approved`, today falls inside its
  date range, and the student is not already checked back in.
* A student cannot be checked out twice, or checked in without checking out.
* A "late return" is a market pass whose check-in scan happened at or after
  21:00 IST.

---

## 8. Tests

```bash
python -m pytest            # whole suite
python -m pytest -v         # per-test names
```

Every test builds its own throwaway SQLite database, so no real data is
touched. The suite covers unit-level rules, every API endpoint (including the
authorisation matrix), and end-to-end journeys for all four roles.
