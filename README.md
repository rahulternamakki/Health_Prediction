# Health Prediction & Clinical Risk Records Manager

A modern, production-grade clinical screening aid and patient record management system built with **FastAPI**, **Streamlit**, **Supabase (PostgreSQL)**, and **Groq Cloud AI**.

The application manages patient demographics and blood test panels (glucose, haemoglobin, cholesterol). Upon submission, patient biometric data is analyzed via an external clinical decision-support AI model to compute a risk classification (`Low`, `Moderate`, `High`) and actionable remarks stored directly in the database.

> [!IMPORTANT]
> **Medical Disclaimer:** This system is an investigational screening aid and technical demonstration. It does not provide medical diagnoses or treatment plans. All clinical indications must be verified by a qualified physician.

---

## 1. System Architecture & Data Flow

```mermaid
flowchart TD
    User([Clinician / User]) <-->|Browser| UI[Streamlit Frontend<br/>:8501]
    UI <-->|HTTP / REST JSON<br/>requests| API[FastAPI Backend<br/>:8000]
    API <-->|SQLAlchemy 2.0 ORM<br/>psycopg2| DB[(Supabase PostgreSQL<br/>patients table)]
    API <-->|REST Chat Completions<br/>httpx / Zero PII| AI[Groq Cloud AI<br/>openai/gpt-oss-120b]
```

### End-to-End Processing Lifecycle
1. **Intake & Client Delivery:** User enters demographic info and blood test values into the Streamlit UI.
2. **Strict Server-Side Validation:** The FastAPI backend validates all fields via **Pydantic v2** models (valid calendar `dd/mm/yyyy`, past dates, 0–120 age range, valid email, and physiological blood metric plausibility bounds).
3. **Privacy-Preserving AI Call:** The patient's exact calendar age is calculated from date of birth. **Only age and the three blood metrics are transmitted to Groq AI**. Patient name, email, and date of birth **never leave the local system**.
4. **Fault-Tolerant Persistence:** If the external AI service times out or fails, the patient record is safely saved with `risk_level = "Pending"` and a fallback remark. Data is never lost due to external service downtime.
5. **Interactive UI Review:** Records are presented in an interactive table with summary metric tiles, risk badges, search filtering, full remarks inspection, edit forms, prediction re-runs, and deletion dialogs.

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Backend Framework** | FastAPI (Python 3.11+) | Asynchronous ASGI runtime, automatic Pydantic v2 validation, self-documenting OpenAPI Swagger docs at `/docs`. |
| **Frontend Framework** | Streamlit | Pure Python responsive single-page web UI, native dataframes with row selection, modal dialogs, and custom styling. |
| **Database** | Supabase (PostgreSQL 15+) | Managed cloud PostgreSQL database with relational integrity, foreign keys, unique indexes, and ACID compliance. |
| **ORM / Data Access** | SQLAlchemy 2.0 | Type-safe declarative mapping (`Mapped`, `mapped_column`), parameterized statements preventing SQL injection. |
| **External AI** | Groq API (`openai/gpt-oss-120b`) | Ultra-fast low-latency inference, deterministic structured JSON output mode, OpenAI-compatible endpoint. |
| **HTTP Clients** | `httpx` (Backend), `requests` (Frontend) | Explicit timeout management (20s AI timeout, 35s frontend timeout) preventing thread starvation. |
| **Testing & Quality** | `pytest`, `pytest-cov`, `ruff` | 138 backend tests (99% coverage), 11 frontend tests, zero lint warnings. |

---

## 3. Clinical Assumptions & Plausibility Bounds

- **Measurement Units:**
  - Glucose: `mg/dL`
  - Haemoglobin: `g/dL`
  - Total Cholesterol: `mg/dL`
- **Missing Parameters:** Patient biological sex and fasting state are deliberately not collected (fixed brief fields). The system instruction directs the AI model to assume fasting state is unknown and adopt conservative reference bands for haemoglobin.
- **Plausibility Bounds vs. Normal Ranges:**
  - Glucose: 20.0 to 600.0 mg/dL (Normal fasting: 70–99 mg/dL)
  - Haemoglobin: 3.0 to 25.0 g/dL (Normal reference: ~12.0–17.5 g/dL)
  - Total Cholesterol: 50.0 to 600.0 mg/dL (Desirable: <200 mg/dL)
  *(Bounds reject obvious typographical anomalies without rejecting critically abnormal clinical readings).*

---

## 4. Getting Started & Setup

### Prerequisites
- Python 3.11, 3.12, or 3.13 installed
- Git installed
- A free Groq Cloud API Key from [console.groq.com](https://console.groq.com)
- A Supabase project database connection URI

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd AI_job2
```

### Step 2: Configure Environment (`backend/.env`)
Copy `backend/.env.example` to `backend/.env`:
```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your real keys:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres
AI_TIMEOUT_SECONDS=20
```

> [!NOTE]
> **Supabase Password Encoding:** If your database password contains special characters like `@` or `:`, URL-encode them (e.g. `@` becomes `%40`). For in-memory offline testing or fallback, `DATABASE_URL=sqlite:///./data/patients.db` is also supported.

### Step 3: Setup Virtual Environments & Dependencies

**Backend:**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
cd ..
```

**Frontend:**
```powershell
cd frontend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

---

## 5. Running the Application

Open two separate terminal windows:

### Terminal 1: Start Backend (FastAPI)
```powershell
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload
```
- API Base: `http://127.0.0.1:8000`
- Interactive Swagger Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Terminal 2: Start Frontend (Streamlit)
```powershell
cd frontend
.\.venv\Scripts\activate
streamlit run app.py
```
- The browser will automatically open: [http://localhost:8501](http://localhost:8501)

---

## 6. Automated Testing & Code Quality

### Backend Test Suite (99% Coverage)
```powershell
cd backend
.\.venv\Scripts\pytest.exe --cov=app --cov-report=term-missing
```

Coverage Report:
```text
Name                Stmts   Miss  Cover   Missing
-------------------------------------------------
app\__init__.py         0      0   100%
app\ai_service.py      42      0   100%
app\config.py           7      0   100%
app\crud.py            36      0   100%
app\database.py        17      2    88%   9-10
app\main.py            16      0   100%
app\models.py          19      0   100%
app\routes.py          79      0   100%
app\schemas.py         59      0   100%
app\utils.py            4      0   100%
-------------------------------------------------
TOTAL                 279      2    99%
======================= 138 passed in 7.06s =======================
```

### Frontend Test Suite
```powershell
cd frontend
.\.venv\Scripts\pytest.exe -q
```
```text
...........
11 passed in 0.46s
```

### Static Analysis (Ruff)
```powershell
cd backend
.\.venv\Scripts\ruff.exe check .
```
```text
All checks passed!
```

---

## 7. API Specification

| Method | Path | Summary | Success Status | Errors |
|---|---|---|---|---|
| `GET` | `/health` | Application liveness probe | `200 {"status":"ok"}` | - |
| `POST` | `/patients` | Create patient + run AI prediction | `201 Created` | `409` (duplicate email), `422` (validation) |
| `GET` | `/patients` | Search & paginate patients | `200 OK` (list) | `422` (bad query parameter) |
| `GET` | `/patients/{id}` | Retrieve patient record by ID | `200 OK` | `404` (not found) |
| `PUT` | `/patients/{id}` | Replace record (re-predicts if metrics change) | `200 OK` | `404`, `409`, `422` |
| `DELETE` | `/patients/{id}` | Remove patient record | `204 No Content` | `404` (not found) |
| `POST` | `/patients/{id}/predict` | Re-run AI analysis for patient | `200 OK` | `404`, `502` (AI unreachable) |

### Request Payload (`POST /patients`, `PUT /patients/{id}`)
```json
{
  "full_name": "Eleanor Vance",
  "date_of_birth": "14/06/1982",
  "email": "eleanor.vance@clinic.org",
  "glucose": 105.0,
  "haemoglobin": 13.8,
  "cholesterol": 210.0
}
```

### Response Payload (`200 OK` / `201 Created`)
```json
{
  "id": 1,
  "full_name": "Eleanor Vance",
  "date_of_birth": "14/06/1982",
  "email": "eleanor.vance@clinic.org",
  "glucose": 105.0,
  "haemoglobin": 13.8,
  "cholesterol": 210.0,
  "risk_level": "Moderate",
  "remarks": "Borderline fasting glucose and cholesterol levels. Schedule routine follow-up with a doctor to evaluate metabolic cardiovascular health.",
  "created_at": "2026-10-29T21:45:00.000000Z",
  "updated_at": "2026-10-29T21:45:00.000000Z"
}
```

---

## 8. Data Validation Rules

| Field | Rules Enforced | User-Facing Error Message |
|---|---|---|
| `full_name` | 2 to 100 characters; letters, spaces, dots, hyphens, and apostrophes only. Collapses redundant spaces. | *"Name may contain only letters, spaces, dots, apostrophes and hyphens"* |
| `date_of_birth` | Strict `dd/mm/yyyy` format matching. Real calendar date validation (rejects 31/02/2000). Future dates prohibited. Maximum age capped at 120. | *"Date of birth must be in dd/mm/yyyy format"*, *"Date of birth is not a valid calendar date"*, *"Date of birth cannot be in the future"*, *"Date of birth is too far in the past"* |
| `email` | RFC-compliant email, lowercased, unique across the database. | Standard Pydantic email error; *"A patient with this email already exists"* (`409 Conflict`) |
| `glucose` | Floating point number: 20.0 to 600.0 mg/dL. No `NaN` or `inf`. | *"Input should be less than or equal to 600"* |
| `haemoglobin` | Floating point number: 3.0 to 25.0 g/dL. No `NaN` or `inf`. | *"Input should be less than or equal to 25"* |
| `cholesterol` | Floating point number: 50.0 to 600.0 mg/dL. No `NaN` or `inf`. | *"Input should be less than or equal to 600"* |

---

## 9. Security & Privacy Architecture

- **Zero PII Exposure to AI:** The AI prompt receives:
  `"Patient age: 42 years. Glucose: 105.0 mg/dL (fasting status unknown). Haemoglobin: 13.8 g/dL. Total cholesterol: 210.0 mg/dL."`
  Name, email, and exact date of birth never leave the application layer.
- **SQL Injection Prevention:** 100% of queries use the SQLAlchemy 2.0 ORM with bound parameters. Zero raw string SQL concatenation.
- **Strict Network Timeouts:** Outbound calls to Groq API enforce a 20-second timeout; Streamlit client enforces a 35-second timeout.
- **Secure Secret Handling:** API keys and database credentials reside strictly in `backend/.env` (git-ignored). Keys are passed in HTTP headers, never logged, and never returned in API responses.
- **Zero Raw HTML Injection:** User-supplied strings are rendered purely via native Streamlit components (`st.write`, `st.dataframe`, `st.metric`).

---

## 10. Known Limitations & Trade-Offs

1. **No Authentication / Access Control:** Anyone with access to the local port can perform CRUD actions. Role-based access control (RBAC) was excluded to keep scope aligned with the technical brief.
2. **Cloud Database Connectivity:** Requires active internet access to reach the managed Supabase instance (though SQLite fallback is supported for local environments).
3. **No Database Migration Tooling:** Database tables are initialized using SQLAlchemy `Base.metadata.create_all()`. Production deployments would utilize Alembic for migrations.
4. **Stochastic Nature of AI:** While temperature is configured low (`0.2`), natural language advice may vary slightly between runs.
5. **Missing Clinical Variables:** Lack of biological sex, smoking status, and fasting glucose limits precision of the clinical risk estimation.

---

## 11. Planned Future Improvements

- **Authentication & RBAC:** Implement JWT bearer authentication with clinician and auditor roles.
- **Alembic Migrations:** Formal migration tracking for evolving patient database schemas.
- **Asynchronous Task Queue:** Delegate AI predictions to Celery / Redis or background worker threads to decouple user ingestion from external AI latency.
- **Audit Logging:** Tamper-evident ledger recording who viewed or modified patient records.
- **Reference Ranges by Demographic:** Age- and sex-adjusted physiological reference bands.

---

## 12. Interview Preparation & Demo Script

### Code Reading Order
`config.py` &rarr; `database.py` &rarr; `models.py` &rarr; `utils.py` &rarr; `schemas.py` &rarr; `ai_service.py` &rarr; `crud.py` &rarr; `routes.py` &rarr; `main.py` &rarr; `api_client.py` &rarr; `app.py` &rarr; `tests/`

### 5-Minute Technical Demo Script
1. **Architecture in One Sentence:** *"The application is a decoupled FastAPI and Streamlit system backed by Supabase PostgreSQL, where demographic and blood test data is securely screened via Groq Cloud AI with zero PII exposure."*
2. **Add a Normal Record:** Input a healthy patient (Glucose 92, Haemoglobin 14.2, Cholesterol 175); demonstrate fast AI response assigning `Low Risk` with routine follow-up advice.
3. **Trigger Validation Errors:** Enter DOB `31/02/2000` and email `invalid_email` to showcase user-friendly error formatting and input preservation.
4. **Edit Blood Metric:** Change Glucose to `185` and Cholesterol to `260`; observe dynamic AI re-calculation upgrading the patient to `High Risk`.
5. **Delete Confirmation Dialog:** Open delete dialog; demonstrate that "Cancel" does nothing, while "Confirm" triggers removal.
6. **Show Swagger API (`/docs`):** Highlight automatic OpenAPI generation and typed schema enforcement.
7. **Run Test Suites:** Run `pytest --cov=app` in backend (99% coverage) and `pytest -q` in frontend.
8. **Demonstrate AI Resilience:** Explain that if Groq API is unavailable, records are preserved with `risk_level: Pending` and can be re-run at any time.

---

## 13. License

Developed as an engineering assignment and technical interview submission. All rights reserved.
