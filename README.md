# 🚀 DigiPass

DigiPass is a full-stack web application designed to modernize and automate hostel leave and market pass management systems.

It replaces traditional paper-based workflows with a secure, role-based, real-time digital platform that streamlines pass requests, approvals, and gate verification.

## ✨ Why DigiPass?
Traditional hostel pass systems are:
- Paper-based and inefficient
- Time-consuming for students and wardens
- Difficult to track and audit
- Prone to misuse and data inconsistency

DigiPass introduces a secure, transparent, and scalable digital alternative.

## 🔑 Key Features

### 🎨 Modern & Interactive UI
- **Animated Authentication Page:** Features a responsive, interactive digital ripple grid background that reacts to cursor movement.
- **Intuitive Dashboards:** Clean layouts with real-time feedback, detailed input placeholders, and robust error handling.

### 🔐 Role-Based Authentication
- Secure JWT-based login session management.
- Protected frontend routes and token-secured backend REST APIs.
- Supported roles:
    - 🎓 **Student:** Request and track pass approvals.
    - 🏢 **Warden:** Evaluate, approve, or reject incoming requests.
    - 🚪 **Guard:** Real-time checkpoint gate verification.
    - 🛠️ **Admin:** Manage institutional user databases.

---

### 📝 Digital Pass Management
- **Student Dashboard:** Apply for Market Pass or Leave Pass; select predefined courses (e.g., B.Tech CSE, IT) using an interactive UI card layout; monitor real-time approval status.
- **Warden Dashboard:** Clean interface to filter, view pending requests, track history, and single-click approve or reject passes.

---

### 🛠️ Administrative & User Control
- **Single User Creation:** Manually onboard individual students, wardens, or guards. Includes profile photo upload functionality for secure student identification.
- **Bulk Import (CSV Parsing):** Efficiently import hundreds of institutional users at once. Generates downloadable password sheets matching assigned IDs.
- **Partial Failure Resiliency:** Processes all valid accounts in a bulk upload batch while reporting clean error payloads for duplicates or corrupt structural entries.
- **Soft Delete Routine:** Preserves historical relational data logs and gate pass accountability by safely marking users inactive rather than hard-wiping records.
- **Administrative Password Overrides:** Dedicated manual control panel to update security credentials if a user forgets their password.

---

### 🚪 Smart Gate Verification
DigiPass enhances campus security through quick identification verification at institutional gates.
1. Guard input/scanning handles student identification tokens.
2. System extracts individual student keys.
3. Verification checks:
    * Pass status evaluates to **Approved**.
    * Current timestamp falls within the pass validity range.
    * The pass has not already been closed by a check-in.

If valid → ✅ **Access Granted** If invalid → ❌ **Access Denied**

---

## 🛠 Tech Stack

### Frontend
- **React.js** & Functional Components
- **React Router Dom** (Client-side routing)
- **Axios** (API Client)
- **Tailwind CSS** (Modern utility-first layout)
- **Context API** (Global state & Auth state management)
- **Vite** (Dev server & build)

### Backend
- **Python** & **FastAPI** (REST API)
- **SQLAlchemy 2.x** (ORM, layered behind a repository tier)
- **Pydantic v2** (Request/response validation)
- **PyJWT** (Stateless token authorization, HS256)
- **Bcrypt** (Secure password hashing)
- **zxing-cpp** & **Pillow** (ID-card barcode decoding)
- **Supabase Storage** (Optional cloud bucket for profile photos, with a local filesystem fallback)

### Database
- **PostgreSQL** (production) — **SQLite** works out of the box for local development

---

## 📂 Project Structure
```bash
DigiPass/
│
├── backend/                 # Python + FastAPI API
│   ├── app/
│   │   ├── main.py          # App factory, middleware, router registration
│   │   ├── core/            # Settings and security primitives
│   │   ├── dependencies/    # DB session + auth/role dependencies
│   │   ├── models/          # SQLAlchemy entities
│   │   ├── schemas/         # Pydantic request/response contracts
│   │   ├── repositories/    # All database queries
│   │   ├── services/        # Business rules
│   │   ├── routers/         # HTTP endpoints
│   │   └── utils/           # Timezone, barcode, storage, notifications
│   ├── tests/               # Unit, API and end-to-end tests
│   ├── docs/schema.sql      # Reference PostgreSQL DDL
│   ├── requirements.txt
│   └── README.md            # Architecture, API reference, business rules
│
├── frontend/                # React SPA Client
│   ├── src/
│   │   ├── components/      # UI Elements
│   │   ├── context/         # Global authentication states
│   │   ├── services/        # Axios API wrappers (api.js)
│   │   └── App.jsx
│
└── README.md
```

---
## ⚙️ Getting Started

### 1️⃣ Clone Repository
```bash
git clone https://github.com/Shogun585/DigiPass.git
cd DigiPass
```

### 2️⃣ Backend Setup (FastAPI)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

Create your environment file from the template and edit it:
```bash
cp .env.example .env
```

```
DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:5432/DATABASE"  # or the SQLite default
SECRET_KEY="your_super_secret_key"          # >= 32 random characters
CORS_ORIGINS="http://localhost:5173,https://localhost:5173"
DEFAULT_PASSWORD="password_for_new_accounts"
SUPABASE_URL="your_supabase_project_url"            # optional
SUPABASE_SERVICE_ROLE_KEY="your_service_role_key"   # optional
```

Confirm the database is reachable and matches what the app expects (read-only;
it never writes, alters or drops anything):
```bash
python check_database.py
```

Start the API:
```bash
uvicorn app.main:app --reload --port 8000
```
The API runs on http://localhost:8000 and its interactive documentation on http://localhost:8000/docs

Optional — create one demo account per role for local development:
```bash
python seed_dev_data.py
```

### 3️⃣ Frontend Setup
Open a separate terminal window, access the client workspace, and trigger assembly:
```bash
cd frontend
cp .env.example .env     # sets VITE_API_URL=http://localhost:8000
npm install
npm run dev
```
Frontend development engine targets: https://localhost:5173

> The Vite dev server serves over HTTPS (`@vitejs/plugin-basic-ssl`). Accept the
> self-signed certificate warning once. Browsers treat `http://localhost` as a
> trustworthy origin, so calls to the API are not blocked as mixed content.

### 4️⃣ Tests
```bash
cd backend
python -m pytest
```

---

## 🧪 Application Flow
1. Administrative Setup: Bulk uploads or appends user data via CSV schema records.

2. Pass Issuance: Student submits validated pass scopes targeting local schedules.

3. Auditing Verification: Warden updates pass state machines from pending configurations.

4. Gate Evaluation: Guard runs real-time queries asserting safety records and validating student identity via uploaded profile photos at campus exits.

---

## 🌱 Benefits

* Reduces manual paperwork footprint.

* Sharpens structural tracking and accountability data streams.

* Enhances multi-tier hostel edge security parameters.

* Eco-friendly digital log maintenance.
