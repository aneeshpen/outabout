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
