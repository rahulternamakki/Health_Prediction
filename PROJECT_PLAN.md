# Health Prediction App: Engineering Plan

FastAPI (backend) + Streamlit (frontend) + Supabase PostgreSQL (storage) + Groq API (external AI).
Purpose: interview assignment. Every line must be explainable by the developer.

---

## 0. How to use this file with Antigravity

1. Create the project folder, put this file in its root as `PROJECT_PLAN.md`, and open the folder as the workspace in Antigravity.
2. Work **one phase at a time**. Paste the "Agent prompt" at the start of each phase.
3. Review the agent's plan and every diff before accepting. Do not accept code you cannot explain.
4. After each phase: run the "Verify" commands, then commit using the suggested message.
5. Do not start the next phase until the current phase's "Definition of done" is fully ticked.

### Standing rules for the AI agent (paste once at the start)

```
Read PROJECT_PLAN.md fully before writing code. Follow it exactly.
- Implement only the phase I name. Do not add features, files, or dependencies not listed in the plan.
- Use Pydantic v2 APIs (field_validator, model_config, ConfigDict) and SQLAlchemy 2.0 style (select(), db.scalars, Mapped/mapped_column). No v1 syntax.
- Keep code simple and readable: small functions, clear names, type hints.
- Comments only where the reason is not obvious. No decorative comments, no emojis, no banner comments.
- No placeholder data, no example names, no "John Doe", no lorem ipsum, no TODO left behind, no commented-out code, no unused imports.
- Never log or print the API key, patient name, email, or date of birth.
- After implementing, run the Verify commands from the plan and show me the output.
- If the plan and the code ever conflict, stop and tell me instead of guessing.
```

---

## 1. Project summary

**What we build:** a patient records manager. The user stores a patient's name, date of birth, email, and three blood values (glucose, haemoglobin, cholesterol). When valid data is saved, the backend calls an external AI API, which returns a possible health risk. The result is stored in the **Remarks** field and shown in the UI.

**In scope:** CRUD, validation, persistent storage, AI integration, tests, basic security, simple clean UI.

**Out of scope (do not build):** login/authentication, multiple users or roles, Docker, cloud deployment, migrations tooling, caching, background jobs, charts, file upload, PDF reports.

**Why no login:** the brief does not ask for it. Mention it in the interview as a known limitation and a next step.

---

## 2. Requirement traceability

| # | Requirement from the brief | Where it is solved | Where it is tested |
|---|---|---|---|
| R1 | Fields: name, DOB, email, glucose, haemoglobin, cholesterol, remarks | Phase 2 (model), Phase 3 (schemas) | Phase 2, 3, 5 |
| R2 | CRUD (create, read, update, delete) | Phase 5 | Phase 5, 9 |
| R3 | Simple, clean UI, easy navigation | Phase 7, 8 | Phase 9 (manual checklist) |
| R4 | Validation: email format, DOB not in future, DOB as dd/mm/yyyy, numeric blood values | Phase 3 (server), Phase 7 (shows errors) | Phase 3, 7 |
| R5 | Persistent storage | Phase 2 (Supabase PostgreSQL / SQLite fallback) | Phase 2, 9 (restart test) |
| R6 | Call external AI/health API with valid data | Phase 4 | Phase 4 (mocked), Phase 9 (live) |
| R7 | Show prediction in Remarks | Phase 5 (stored), Phase 7 (displayed) | Phase 5, 9 |
| R8 | Testing and safety | Phase 3 to 9, Section 10 | Phase 6, 9 |

---

## 3. Technology and key decisions

| Area | Choice | Reason (be ready to explain) |
|---|---|---|
| Language | Python 3.11+ | Required by the brief; modern type hints (`str \| None`) |
| Backend | FastAPI + Uvicorn | Required; automatic validation, automatic docs at `/docs` |
| Validation | Pydantic v2 | Built into FastAPI; one place for all rules |
| Database | Supabase (PostgreSQL) via SQLAlchemy 2.0 ORM | Managed cloud PostgreSQL via Supabase, ORM prevents SQL injection, SQLite for rapid unit tests |
| Frontend | Streamlit | Required; fast to build in pure Python |
| HTTP (backend to AI) | `httpx` | Simple, supports timeouts |
| HTTP (frontend to backend) | `requests` | Simple, widely known |
| External AI | Groq API (`chat/completions` REST) | Ultra-fast inference, OpenAI-compatible JSON mode, free tier via Groq Console |
| Config | `.env` + `python-dotenv` | Keeps secrets out of code |
| Tests | `pytest` + `pytest-cov` | Standard |

### Decision log

1. **Sync routes (`def`, not `async def`).** FastAPI runs sync routes in a thread pool, so the blocking AI call does not freeze the server. SQLAlchemy sync sessions and `httpx.post` are simpler to explain than async.
2. **Server-side validation is the single source of truth.** The frontend does not duplicate rules; it displays the backend's error messages. This avoids two validators drifting apart.
3. **DOB is accepted and returned as `dd/mm/yyyy` strings by the API; stored as a real `DATE` in the DB.** Display format is a presentation concern; storage should be a proper date.
4. **Only age + three blood values are sent to the AI.** Name, email, and DOB never leave the system (privacy).
5. **If the AI call fails, the record is still saved** with `risk_level = "Pending"` and a fallback remark. The user can press "Re-run prediction". Data is never lost because a third-party service is down.
6. **PUT for update (full replace)** with the same schema as create. Simple and consistent.
7. **On update, the AI is re-run only if DOB or a blood value changed (or the record is still Pending).** Changing a name or email does not need a new prediction.
8. **Email is stored lowercase and is unique.** Prevents duplicate patients differing only by case.
9. **No CORS middleware.** Streamlit calls the backend from the Streamlit server (Python), not from the browser, so CORS does not apply.
10. **AI provider call is isolated in one function (`_call_groq`).** To switch provider, change only that function.
11. **Model name is configurable** (`GROQ_MODEL` in `.env`) because model names change over time. Defaults to `llama-3.3-70b-versatile`.
12. **Blood value limits are plausibility bounds, not normal ranges.** They reject typos (e.g. glucose 9000) without rejecting genuinely abnormal results.

### Assumptions to state in the README

- Units: glucose mg/dL, haemoglobin g/dL, total cholesterol mg/dL.
- Glucose fasting status and patient sex are not collected (the brief lists fixed fields). The AI is told fasting status is unknown and to be conservative about haemoglobin.
- The prediction is a screening aid, not a diagnosis.

---

## 4. Architecture and data flow

```
 Browser
    |
    v
 Streamlit UI (port 8501)  --requests-->  FastAPI (port 8000)
                                              |         |
                                              |         +--httpx--> Groq API (external)
                                              v
                                       Supabase PostgreSQL (DATABASE_URL)
```

**Create flow:**
1. UI sends JSON to `POST /patients`.
2. Pydantic validates. Invalid input returns `422` with field messages.
3. Duplicate email check. Duplicate returns `409`.
4. Age is calculated from DOB. Age + 3 values go to the AI service.
5. AI result (or fallback) is saved with the record in one insert.
6. API returns `201` with the full record including `remarks`.

---

## 5. Folder structure

```
health-predictor/
├── PROJECT_PLAN.md
├── README.md
├── .gitignore
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # app creation, startup, router include
│   │   ├── config.py        # reads environment variables
│   │   ├── database.py      # engine, session, Base, get_db
│   │   ├── models.py        # Patient table
│   │   ├── schemas.py       # request/response models + validation
│   │   ├── utils.py         # calculate_age
│   │   ├── crud.py          # database operations only
│   │   ├── ai_service.py    # external AI call + response parsing
│   │   └── routes.py        # /patients endpoints
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_models.py
│   │   ├── test_validation.py
│   │   ├── test_ai_service.py
│   │   └── test_patients_api.py
│   ├── data/                # created at runtime, git-ignored
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
└── frontend/
    ├── app.py               # Streamlit UI
    ├── api_client.py        # all HTTP calls to the backend
    ├── styles.py            # custom CSS string (Phase 8)
    ├── tests/
    │   └── test_api_client.py
    ├── .streamlit/config.toml
    ├── pytest.ini
    └── requirements.txt
```

Each file has one job. Be able to say that job in one sentence.

---

## 6. Data model: table `patients`

| Column | Type | Rules |
|---|---|---|
| `id` | Integer, primary key | auto |
| `full_name` | String(100) | required |
| `date_of_birth` | Date | required |
| `email` | String(254) | required, unique, indexed, stored lowercase |
| `glucose` | Float | required |
| `haemoglobin` | Float | required |
| `cholesterol` | Float | required |
| `risk_level` | String(20) | `Low`, `Moderate`, `High`, or `Pending` (default `Pending`) |
| `remarks` | Text | nullable; AI-generated text |
| `created_at` | DateTime | default now (UTC) |
| `updated_at` | DateTime | default now, updated on change |

---

## 7. API contract

| Method | Path | Purpose | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | Service check | 200 `{"status":"ok"}` | |
| POST | `/patients` | Create + AI prediction | 201 record | 409 duplicate email, 422 invalid |
| GET | `/patients?search=&skip=&limit=` | List (newest first), search by name or email | 200 list | 422 bad query |
| GET | `/patients/{id}` | Read one | 200 record | 404 |
| PUT | `/patients/{id}` | Update (full replace) | 200 record | 404, 409, 422 |
| DELETE | `/patients/{id}` | Delete | 204 | 404 |
| POST | `/patients/{id}/predict` | Re-run AI prediction | 200 record | 404, 502 AI unavailable |

Query limits: `skip >= 0`, `1 <= limit <= 100` (default 100), `search` max 100 chars.

**Create/update request body**

```json
{
  "full_name": "string",
  "date_of_birth": "dd/mm/yyyy",
  "email": "string",
  "glucose": 0.0,
  "haemoglobin": 0.0,
  "cholesterol": 0.0
}
```

**Record response** adds `id`, `risk_level`, `remarks`, and returns `date_of_birth` as `dd/mm/yyyy`.

---

## 8. Validation rules

| Field | Rule | Error message (user-facing) |
|---|---|---|
| `full_name` | Trimmed, 2 to 100 chars, only letters, spaces, `.`, `'`, `-`; extra internal spaces collapsed | "Name may contain only letters, spaces, dots, apostrophes and hyphens" |
| `date_of_birth` | Must match `dd/mm/yyyy` exactly (two digits, two digits, four digits) | "Date of birth must be in dd/mm/yyyy format" |
| | Must be a real calendar date (rejects 31/02/2000, 15/13/1990) | "Date of birth is not a valid calendar date" |
| | Not in the future | "Date of birth cannot be in the future" |
| | Age not more than 120 | "Date of birth is too far in the past" |
| `email` | Valid email format (`EmailStr`), lowercased | default Pydantic email message |
| `email` | Unique | "A patient with this email already exists" (409) |
| `glucose` | Number, 20 to 600 (mg/dL), no NaN/inf | Pydantic range message |
| `haemoglobin` | Number, 3 to 25 (g/dL), no NaN/inf | Pydantic range message |
| `cholesterol` | Number, 50 to 600 (mg/dL), no NaN/inf | Pydantic range message |

---

## 9. AI integration design

**Provider:** Groq API, REST (OpenAI-compatible chat completions).
**Endpoint:** `POST https://api.groq.com/openai/v1/chat/completions`
**Auth:** header `Authorization: Bearer <key>` (header, never in the URL, so it does not appear in logs).
**Key:** free key from Groq Console (`https://console.groq.com`). Keep it only in `backend/.env`.

**Request body shape**

```json
{
  "model": "<model>",
  "messages": [
    { "role": "system", "content": "<system instruction>" },
    { "role": "user", "content": "<patient values>" }
  ],
  "temperature": 0.2,
  "max_tokens": 1024,
  "response_format": { "type": "json_object" }
}
```

**Response shape we read:** `choices[0].message.content`.

**System instruction (text to use):**

```
You are a clinical decision-support assistant used in a screening demo. Given an adult's age and three blood test values, estimate the most likely health risk. You do not diagnose.
Reference guidance: fasting glucose 70-99 mg/dL is normal, 100-125 is the prediabetes range, 126 or above is the diabetes range. Haemoglobin below roughly 12 g/dL suggests possible anaemia and above roughly 17.5 g/dL is high; sex is not provided, so be conservative. Total cholesterol below 200 mg/dL is desirable, 200-239 is borderline high, 240 or above is high.
Respond with one JSON object with exactly these keys: "risk_level" (one of "Low", "Moderate", "High"), "possible_condition" (maximum 15 words), "advice" (maximum 35 words, and it must recommend confirming with a doctor). Output JSON only.
```

**User message built by our code:**
`Patient age: {age} years. Glucose: {glucose:.1f} mg/dL (fasting status unknown). Haemoglobin: {haemoglobin:.1f} g/dL. Total cholesterol: {cholesterol:.1f} mg/dL.`

Only numbers formatted by our code go into the prompt. No free text from the user ever reaches the prompt, so prompt injection is not possible through this path.

**Never trust the AI output.** Parse the JSON, validate it with a Pydantic model (`risk_level` must be one of three values, text lengths capped), and only then store it. Anything else is treated as an AI failure.

**Stored `remarks`:** `"{possible_condition without trailing dot}. {advice}"`.

**Failure handling:** missing key, timeout, non-200 status, blocked/empty response, malformed JSON, or invalid fields all raise `AIServiceError`. The route catches it, saves the record with `risk_level="Pending"` and remarks `"AI prediction unavailable. Select the record and choose Re-run prediction."`.

---

## 10. Security and safety checklist

Tick each item before submission.

**Secrets**
- [ ] API key only in `backend/.env`; `.env` is in `.gitignore`; `.env.example` has no real key.
- [ ] Key sent in a header, never logged, never returned by any endpoint, never in the frontend.
- [ ] Run `git log -p | grep -i "AIza"` (or your key prefix) before pushing; result must be empty.

**Input and database**
- [ ] All input validated by Pydantic before use.
- [ ] Only SQLAlchemy ORM queries; no string-built SQL.
- [ ] Query parameters bounded (`limit <= 100`, `skip >= 0`, `search` max length).
- [ ] Unique email enforced at the DB level and checked in code; `IntegrityError` handled with rollback and `409`.

**Privacy**
- [ ] Only age + blood values go to the AI. Name, email, DOB are never sent.
- [ ] Logs contain patient `id` and event names only.
- [ ] Use fictional data for the demo. Free-tier AI services may use submitted data to improve their products, so never enter real patient data.

**External calls**
- [ ] Timeout on every outbound HTTP call (backend to AI: 20 s; frontend to backend: 35 s).
- [ ] AI response validated and length-capped before storing.
- [ ] AI failure never crashes the request and never loses user data.

**Output**
- [ ] Streamlit displays user text with `st.write` / `st.dataframe`, never raw HTML. If custom HTML is ever used, escape user values with `html.escape`.
- [ ] Error messages shown to the user do not contain stack traces or internals.

**Network**
- [ ] Backend runs on `127.0.0.1` for the demo.

**Medical safety**
- [ ] UI shows a permanent disclaimer: "Screening aid only. Not a medical diagnosis. Consult a qualified doctor."
- [ ] Every AI remark includes advice to confirm with a doctor (enforced by the system instruction).

**Dependencies**
- [ ] `pip freeze` output saved to requirements so versions are pinned.
- [ ] Optional: `pip install pip-audit` then `pip-audit` for known vulnerabilities.

---

## Phase 0: Requirements and design (no code)

**Goal:** understand the problem before building.

**Tasks**
1. Read the brief and this plan fully.
2. Check you can explain Sections 2 to 9 aloud without reading.
3. Decide your own words for the three biggest decisions: why server-side validation, why the record is saved even if AI fails, why only age and values go to the AI.

**Definition of done**
- [x] You can draw the architecture diagram from memory.
- [x] You can list the 7 API endpoints and what each does.

---

## Phase 1: Environment and project setup

**Goal:** a clean, reproducible workspace, and proof that the AI API key works **before** writing any app code.

**Agent prompt**
```
Implement Phase 1 of PROJECT_PLAN.md only: folder structure (empty files where needed), virtual environments, requirements files, .gitignore, .env.example, pytest.ini files, git init. Do not write application logic yet.
```

**Tasks**
1. Create the folder structure from Section 5.
2. Create a virtual environment per side.
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. `backend/requirements.txt`:
   ```
   fastapi
   uvicorn[standard]
   sqlalchemy
   pydantic[email]
   httpx
   python-dotenv
   psycopg2-binary
   ```
   `backend/requirements-dev.txt`:
   ```
   -r requirements.txt
   pytest
   pytest-cov
   ```
   `frontend/requirements.txt`:
   ```
   streamlit
   requests
   pytest
   ```
   Install, then run `pip freeze > requirements.lock.txt` in each folder and keep it for exact versions.
4. `.gitignore` must include: `.venv/`, `__pycache__/`, `.env`, `backend/data/`, `*.db`, `.pytest_cache/`, `.coverage`, `htmlcov/`.
5. `backend/.env.example`:
   ```
   GROQ_API_KEY=your_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   DATABASE_URL=postgresql+psycopg2://postgres:[YOUR-PASSWORD]@[YOUR-SUBDOMAIN].pooler.supabase.com:6543/postgres
   AI_TIMEOUT_SECONDS=20
   ```
   Copy it to `backend/.env` and put your real key and Supabase database URL there.
6. `backend/pytest.ini` and `frontend/pytest.ini`:
   ```
   [pytest]
   pythonpath = .
   testpaths = tests
   ```
7. **Prove the key and model work** (replace the key; on Windows PowerShell use `curl.exe`, not `curl`):
   ```
   curl "https://api.groq.com/openai/v1/models" -H "Authorization: Bearer YOUR_KEY"
   ```
   This lists the models your key can use. Confirm the model in `GROQ_MODEL` appears in the list; if not, pick a current model from the list (e.g. `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`) and update `.env.example` and `.env`. Then test generation:
   ```
   curl "https://api.groq.com/openai/v1/chat/completions" -H "Authorization: Bearer YOUR_KEY" -H "Content-Type: application/json" -d "{\"model\":\"llama-3.3-70b-versatile\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word ok\"}]}"
   ```
8. `git init`, make the first commit.

**Pitfalls**
- Do not paste the real key into any file other than `.env`.
- If curl returns 401/403, the key is wrong or invalid; fix this now, not later.
- If you hit quota or availability problems, only `_call_groq` in Phase 4 needs to change to use another model or provider.

**Verify**
- `python --version` shows 3.11 or higher.
- `pytest --version` works in both venvs.
- The generation curl returns a JSON containing `choices`.
- `git status` does not list `.env`.

**Definition of done**
- [x] Structure matches Section 5.
- [x] Dependencies installed and locked.
- [ ] API key confirmed working with a valid model name.
- [x] `.env` ignored by git.

**Commit:** `chore: project setup, dependencies, env template`

---

## Phase 2: Database layer

**Goal:** persistent storage with the `patients` table.

**Agent prompt**
```
Implement Phase 2 of PROJECT_PLAN.md only: config.py, database.py, models.py, utils.py (calculate_age), and the Patient table, plus tests/test_models.py. No routes yet.
```

**Files and content**

`config.py`
```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/patients.db")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "20"))
```

`database.py`
```python
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app import config

if config.DATABASE_URL.startswith("sqlite"):
    Path("data").mkdir(exist_ok=True)
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(config.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
`check_same_thread=False` is used when running with SQLite (e.g. tests or local fallback) because FastAPI handles requests across worker threads.

`models.py`: the `Patient` class as in Section 6, using `Mapped[...]` and `mapped_column(...)`. Use `datetime.now(timezone.utc)` for timestamps (not the deprecated `utcnow`). `risk_level` default is `"Pending"`.

`utils.py`
```python
from datetime import date


def calculate_age(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
```

**Tests (`test_models.py`)**
- Using an in-memory SQLite engine (`sqlite://` with `StaticPool`): insert one patient, read it back, fields equal.
- Insert two patients with the same email: second commit raises `IntegrityError`.
- `calculate_age` cases: birthday already passed this year, birthday not yet reached, birthday today.

**Pitfalls**
- Run everything from inside `backend/` so `data/` and imports resolve correctly.
- The table is created at app startup (Phase 5), not at import time, so importing modules never touches the real database file.

**Verify** (from `backend/`): `pytest -q`

**Definition of done**
- [x] Model matches Section 6 exactly.
- [x] Unique email enforced by the database.
- [x] Tests pass.

**Commit:** `feat: database layer and patient model`

---

## Phase 3: Schemas and validation

**Goal:** all input rules in one place, fully tested **before** any route exists.

**Agent prompt**
```
Implement Phase 3 of PROJECT_PLAN.md only: schemas.py with PatientInput and PatientRead, and tests/test_validation.py. Follow Section 8 exactly. No routes yet.
```

**`schemas.py` design**

```python
import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from app.utils import calculate_age

DOB_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
DOB_FORMAT = "%d/%m/%Y"
MAX_AGE_YEARS = 120


class PatientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=100)
    date_of_birth: date
    email: EmailStr
    glucose: float = Field(ge=20, le=600, allow_inf_nan=False)
    haemoglobin: float = Field(ge=3, le=25, allow_inf_nan=False)
    cholesterol: float = Field(ge=50, le=600, allow_inf_nan=False)

    @field_validator("full_name")
    @classmethod
    def check_name(cls, value: str) -> str:
        allowed_symbols = " .'-"
        if not any(c.isalpha() for c in value) or not all(c.isalpha() or c in allowed_symbols for c in value):
            raise ValueError("Name may contain only letters, spaces, dots, apostrophes and hyphens")
        return " ".join(value.split())

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_dob(cls, value):
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or not DOB_PATTERN.match(value.strip()):
            raise ValueError("Date of birth must be in dd/mm/yyyy format")
        try:
            return datetime.strptime(value.strip(), DOB_FORMAT).date()
        except ValueError:
            raise ValueError("Date of birth is not a valid calendar date")

    @field_validator("date_of_birth")
    @classmethod
    def check_dob_range(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        if calculate_age(value) > MAX_AGE_YEARS:
            raise ValueError("Date of birth is too far in the past")
        return value

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    date_of_birth: date
    email: str
    glucose: float
    haemoglobin: float
    cholesterol: float
    risk_level: str
    remarks: str | None

    @field_serializer("date_of_birth")
    def serialize_dob(self, value: date) -> str:
        return value.strftime(DOB_FORMAT)
```

How it works (you must be able to explain this):
- The `mode="before"` validator runs first and converts the `dd/mm/yyyy` string to a `date`. Without it, Pydantic would also accept `1990-01-01`, which the brief does not allow.
- The second validator (after) receives a real `date` and checks the range.
- `float` fields reject text such as `"abc"` automatically; `Field(ge, le)` enforces ranges.

**Tests (`test_validation.py`)** use `PatientInput(**payload)` directly with `pytest.raises(ValidationError)`.

Valid payload used as the base (keep as a module constant):
```python
VALID = {
    "full_name": "Test Patient",
    "date_of_birth": "15/08/1995",
    "email": "test.patient@example.com",
    "glucose": 92.0,
    "haemoglobin": 14.2,
    "cholesterol": 178.0,
}
```

Parametrised invalid cases (each one changes a single field of `VALID`):

| Field | Invalid values |
|---|---|
| `email` | `"abc"`, `"a@"`, `"@b.com"`, `"a b@c.com"`, `""` |
| `date_of_birth` | `"1995-08-15"`, `"15-08-1995"`, `"5/8/1995"`, `"31/02/2000"`, `"15/13/1990"`, `"00/01/1990"`, tomorrow's date, `"01/01/1800"`, `""`, `"abc"` |
| `glucose` / `haemoglobin` / `cholesterol` | `"abc"`, `""`, `None`, `-5`, `0`, below min, above max, `float("nan")`, `float("inf")` |
| `full_name` | `""`, `"A"`, `"Test123"`, `"<script>"`, `"   "`, 101 characters |

Valid cases to also test:
- DOB today is accepted; DOB exactly 120 years ago is accepted.
- Email `"Test.Patient@Example.COM"` is stored as `"test.patient@example.com"`.
- Name `"  Anne-Marie   O'Neil  "` becomes `"Anne-Marie O'Neil"`.
- Boundary values accepted: glucose 20 and 600, haemoglobin 3 and 25, cholesterol 50 and 600.
- `PatientRead` serialises `date(1995, 8, 15)` as `"15/08/1995"`.
- Tomorrow's date for the future test is computed with `date.today() + timedelta(days=1)` formatted `%d/%m/%Y`, never hard-coded.

**Pitfalls**
- `EmailStr` needs the `email-validator` package; it comes from `pydantic[email]`.
- A validator must raise `ValueError` (Pydantic wraps it); do not raise `HTTPException` inside schemas.

**Verify:** `pytest -q tests/test_validation.py`

**Definition of done**
- [x] Every row in Section 8 has at least one failing-input test and one passing-input test.
- [x] No test depends on today's date being a particular day.

**Commit:** `feat: input schemas and validation with tests`

---

## Phase 4: AI service

**Goal:** an isolated, tested module that turns (age, 3 values) into a validated prediction, or raises `AIServiceError`.

**Agent prompt**
```
Implement Phase 4 of PROJECT_PLAN.md only: ai_service.py and tests/test_ai_service.py. Follow Section 9 exactly. The tests must not make real network calls.
```

**`ai_service.py` design**

```python
import json
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app import config

logger = logging.getLogger(__name__)

API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_INSTRUCTION = "..."  # exact text from Section 9


class AIServiceError(Exception):
    pass


class AIPrediction(BaseModel):
    risk_level: Literal["Low", "Moderate", "High"]
    possible_condition: str = Field(min_length=1, max_length=150)
    advice: str = Field(min_length=1, max_length=400)

    @property
    def remarks(self) -> str:
        return f"{self.possible_condition.rstrip('.')}. {self.advice}"


def build_prompt(age: int, glucose: float, haemoglobin: float, cholesterol: float) -> str:
    return (
        f"Patient age: {age} years. Glucose: {glucose:.1f} mg/dL (fasting status unknown). "
        f"Haemoglobin: {haemoglobin:.1f} g/dL. Total cholesterol: {cholesterol:.1f} mg/dL."
    )


def _call_groq(prompt: str) -> str:
    if not config.GROQ_API_KEY:
        raise AIServiceError("API key is not configured")
    body = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(
            API_URL,
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=config.AI_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise AIServiceError(f"Request failed: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise AIServiceError(f"AI API returned status {response.status_code}")
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIServiceError("Unexpected AI API response shape") from exc


def parse_prediction(text: str) -> AIPrediction:
    try:
        return AIPrediction.model_validate(json.loads(text))
    except (ValueError, TypeError) as exc:
        raise AIServiceError("AI response was not in the expected format") from exc


def predict_health_risk(age: int, glucose: float, haemoglobin: float, cholesterol: float) -> AIPrediction:
    text = _call_groq(build_prompt(age, glucose, haemoglobin, cholesterol))
    return parse_prediction(text)
```

(`ValidationError` from Pydantic and `json.JSONDecodeError` are both `ValueError` subclasses, so `except ValueError` covers both; remove the unused `ValidationError` import if you rely on that.)

The exception message deliberately contains only the exception class name or the status code, never the URL, headers, or body, so nothing sensitive can leak into logs.

**Tests (`test_ai_service.py`)** monkeypatch `ai_service.httpx.post` with a fake and set the key with `monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")`:

```python
class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload
```

Cases:
1. `build_prompt` contains the age and all three values, formatted with one decimal.
2. `parse_prediction` with valid JSON returns an `AIPrediction`; `.remarks` joins condition and advice and does not double the full stop.
3. `parse_prediction` raises `AIServiceError` for: not JSON, JSON list, missing key, `risk_level` `"Critical"`, empty text, over-length advice.
4. `_call_groq` success: fake 200 response with `choices[0].message.content` -> returns the text; also verify the request used header `Authorization: Bearer <key>`, the model from config, and `response_format`.
5. `_call_groq` raises `AIServiceError` for: empty API key (and `httpx.post` is not called), status 400/401/429/500, `httpx.TimeoutException`, `httpx.ConnectError`, 200 with empty `choices`, 200 with non-JSON body.
6. `predict_health_risk` end to end with a fake 200 response -> correct `AIPrediction`.
7. The error message of a failed call does not contain the API key (assert `"test-key" not in str(exc)`).

**Pitfalls**
- Tests must never use the real key or hit the network. Patch `httpx.post` on the module under test.
- If real calls later return truncated JSON, raise `maxOutputTokens`; do not loosen validation.

**Verify:** `pytest -q tests/test_ai_service.py`

**Definition of done**
- [ ] No network access in tests (turn Wi-Fi off, tests still pass).
- [ ] Every failure path ends in `AIServiceError`, never another exception type.
- [ ] You can explain each function in one sentence.

**Commit:** `feat: AI service with response validation and tests`

---

## Phase 5: CRUD layer and API routes

**Goal:** the complete working backend.

**Agent prompt**
```
Implement Phase 5 of PROJECT_PLAN.md only: crud.py, routes.py, main.py, conftest.py, and tests/test_patients_api.py. Follow Section 7 and decisions 5, 7 and 8 exactly. Routes must be sync def.
```

**`crud.py`** (database only, no HTTP, no AI):
- `get_patient(db, patient_id)` -> `db.get(Patient, patient_id)`
- `get_by_email(db, email)` -> `db.scalar(select(Patient).where(Patient.email == email))`
- `list_patients(db, search, skip, limit)` -> newest first (`order_by(Patient.id.desc())`); if `search`, filter `or_(full_name.ilike(pattern), email.ilike(pattern))` with `pattern = f"%{search.strip()}%"`; then `offset(skip).limit(limit)`.
- `create_patient(db, data, risk_level, remarks)` -> add, commit, refresh, return.
- `update_patient(db, patient, data, risk_level, remarks)` -> assign fields, commit, refresh.
- `delete_patient(db, patient)` -> delete, commit.

**`routes.py`** (HTTP only; calls crud and ai_service):

```python
router = APIRouter(prefix="/patients", tags=["patients"])
FALLBACK_REMARKS = "AI prediction unavailable. Select the record and choose Re-run prediction."


def get_prediction(dob, glucose, haemoglobin, cholesterol) -> tuple[str, str]:
    try:
        result = ai_service.predict_health_risk(calculate_age(dob), glucose, haemoglobin, cholesterol)
    except ai_service.AIServiceError as exc:
        logger.warning("AI prediction failed: %s", exc)
        return "Pending", FALLBACK_REMARKS
    return result.risk_level, result.remarks
```

Call it as `ai_service.predict_health_risk(...)` (module attribute), **not** `from ai_service import predict_health_risk`, so tests can replace it in one place.

Endpoint logic:
- `POST ""` (status 201): reject duplicate email with 409 -> `get_prediction` -> `crud.create_patient`; wrap in `try/except IntegrityError` -> `db.rollback()` -> 409 (covers a race between the check and the insert).
- `GET ""`: query params `search: str | None = Query(None, max_length=100)`, `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=100)`.
- `GET "/{patient_id}"`: 404 if missing.
- `PUT "/{patient_id}"`: 404 if missing; if another record owns the new email -> 409; `inputs_changed = any of (DOB, glucose, haemoglobin, cholesterol) differ` ; if `inputs_changed or patient.risk_level == "Pending"` -> `get_prediction`, else keep the existing `risk_level` and `remarks`; save; `IntegrityError` -> rollback -> 409.
- `DELETE "/{patient_id}"` (204): 404 if missing.
- `POST "/{patient_id}/predict"`: 404 if missing; call `ai_service.predict_health_risk` directly; on `AIServiceError` raise `HTTPException(502, "AI service is unavailable. Please try again later.")`; on success save and return the record.

All route functions use `response_model=PatientRead` (list endpoint: `list[PatientRead]`).

**`main.py`**
```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers the table before create_all)
from app.database import Base, engine
from app.routes import router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Health Prediction API", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

**`tests/conftest.py`**
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ai_service, models  # noqa: F401
from app.database import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield TestClient(fastapi_app)  # not used with "with", so the startup hook does not touch the real DB
    fastapi_app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    calls = []

    def fake_predict(age, glucose, haemoglobin, cholesterol):
        calls.append((age, glucose, haemoglobin, cholesterol))
        return ai_service.AIPrediction(
            risk_level="Low",
            possible_condition="No significant risk indicators",
            advice="Maintain a healthy lifestyle and confirm with a doctor.",
        )

    monkeypatch.setattr(ai_service, "predict_health_risk", fake_predict)
    return calls
```

**Tests (`test_patients_api.py`)**

Create
- Valid payload -> 201; response has `id`, `risk_level == "Low"`, non-empty `remarks`, DOB returned as `dd/mm/yyyy`, email lowercase.
- Fake AI was called exactly once, with the computed age and the three values, and **without** name/email (the fake only receives four arguments, which proves it).
- Every invalid case from Phase 3 (one parametrised test through the API) -> 422 and no record is created (`GET /patients` returns empty).
- Duplicate email (including different letter case) -> 409.
- AI failure (monkeypatch to raise `AIServiceError`) -> still 201, `risk_level == "Pending"`, remarks equal the fallback text.

Read
- List empty -> `[]`; after two creates -> two items, newest first.
- Search by part of name and by part of email (case-insensitive); search with no match -> `[]`.
- `limit=0`, `limit=101`, `skip=-1` -> 422.
- Get existing -> 200; get unknown id -> 404; non-integer id -> 422.

Update
- Change only the name -> 200, AI not called again (calls list length unchanged), remarks unchanged.
- Change glucose -> AI called again.
- Change DOB -> AI called again.
- Update unknown id -> 404; invalid body -> 422 and the stored record is unchanged.
- Change email to another patient's email -> 409; to its own email -> 200.
- Pending record updated (name only) -> AI called again and becomes non-Pending.

Delete
- Delete -> 204; then get -> 404; delete again -> 404; other records untouched.

Predict endpoint
- Pending record + working AI -> 200, becomes `Low`.
- AI raising `AIServiceError` -> 502 with the generic message (no internals), record unchanged.
- Unknown id -> 404.

Other
- `GET /health` -> 200.
- SQL injection string as search (`"' OR 1=1 --"`) -> 200, empty list, table still intact.
- Persistence: records are in the DB after the request (read through a second `GET`).

**Pitfalls**
- Use `@router.post("")` with prefix `/patients`; the frontend calls `/patients` (no trailing slash). A mismatch causes a 307 redirect.
- `TestClient(app)` used as a context manager (`with`) would run the startup hook against the real database file. Do not use `with` in these tests.
- Never call `db.commit()` inside crud read functions.
- Return the ORM object; `PatientRead` (with `from_attributes=True`) converts it.

**Verify (from `backend/`)**
```
pytest -q
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/docs` and try every endpoint by hand with the real AI (this is the first live AI test).

**Definition of done**
- [ ] All 7 endpoints behave as in Section 7.
- [ ] Live call through `/docs` fills `remarks` from Groq.
- [ ] Stop the server, start it again: records are still there (persistence).
- [ ] Temporarily blank the API key in `.env`, restart, create a record: saved as `Pending`, no crash. Restore the key.

**Commit:** `feat: CRUD API with AI prediction and tests`

---

## Phase 6: Backend hardening and review

**Goal:** prove the backend is solid before touching the UI.

**Tasks**
1. Run `pytest --cov=app --cov-report=term-missing`. Target 85% or more of `app/`. Read the "missing" lines; add tests for meaningful gaps (not for trivial lines).
2. Walk through Section 10 and tick every backend item.
3. Try these manually in `/docs` and confirm clean errors (no stack traces): DOB `31/02/2000`, glucose `"abc"`, empty body, id `999999`, `limit=1000`.
4. Search the code: no `print(` calls, no hard-coded keys, no `TODO`, no unused imports (`pip install ruff`, then `ruff check .`).
5. Read your own code top to bottom once and write one sentence per file in a notes file (used for interview prep).

**Definition of done**
- [ ] All tests pass; coverage target met.
- [ ] Section 10 backend items ticked.
- [ ] `ruff check .` reports nothing.

**Commit:** `chore: backend review, coverage and lint fixes`

---

## Phase 7: Frontend (Streamlit), functional first

**Goal:** a working, simple UI for all CRUD operations. Looks come in Phase 8; get behaviour right first.

**Agent prompt**
```
Implement Phase 7 of PROJECT_PLAN.md only: frontend/api_client.py, frontend/tests/test_api_client.py, frontend/app.py, frontend/.streamlit/config.toml. Keep the UI plain and functional; styling comes in Phase 8. No HTML injection with user data.
```

**`api_client.py`** (the only file that talks HTTP):
```python
import os

import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
TIMEOUT_SECONDS = 35  # longer than the backend's AI timeout


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def extract_error_message(response) -> str:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return "Unexpected response from the server."
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):  # validation errors from FastAPI
        messages = []
        for item in detail:
            field = str(item["loc"][-1]).replace("_", " ").capitalize()
            text = item["msg"].removeprefix("Value error, ")
            messages.append(f"{field}: {text}")
        return "\n".join(messages)
    return "The request could not be completed."


def _request(method: str, path: str, **kwargs):
    try:
        response = requests.request(method, f"{BACKEND_URL}{path}", timeout=TIMEOUT_SECONDS, **kwargs)
    except requests.RequestException:
        raise ApiError("Cannot reach the backend service. Make sure it is running.")
    if response.status_code >= 400:
        raise ApiError(extract_error_message(response), response.status_code)
    return None if response.status_code == 204 else response.json()
```
Plus thin wrappers: `list_patients(search="")`, `get_patient(id)`, `create_patient(payload)`, `update_patient(id, payload)`, `delete_patient(id)`, `rerun_prediction(id)`.

**`tests/test_api_client.py`** (monkeypatch `requests.request` with fakes):
- 204 returns `None`; 200 returns JSON.
- 422 list detail becomes readable lines, with the `"Value error, "` prefix removed.
- 409 string detail is passed through; 404 works.
- `requests.ConnectionError` and `requests.Timeout` become `ApiError` with the "cannot reach" message.
- Non-JSON error body does not crash.
- `list_patients` sends `search` as a query parameter.

**`app.py` specification**

1. `st.set_page_config(page_title="Health Risk Records", layout="wide")` must be the **first** Streamlit call.
2. Sidebar navigation (`st.radio`): **Records**, **Add patient**.
3. A permanent disclaimer on every page: "Screening aid only. Not a medical diagnosis. Consult a qualified doctor."
4. Wrap all API calls in `try/except ApiError` and show `st.error(error.message)`. Never show raw exceptions.
5. Show `st.spinner("Analysing blood values...")` around create, update, and re-run calls (the AI call takes seconds).

**Add patient page**
- `st.form` with: Full name (text), Date of birth (text, placeholder `dd/mm/yyyy`), Email (text), Glucose (mg/dL), Haemoglobin (g/dL), Cholesterol (mg/dL) as `st.number_input(value=None, min_value=..., max_value=..., step=0.1, format="%.1f")` so no fake default values appear.
- On submit: check nothing is empty (message "Please fill in all fields"), then call `create_patient`. The backend does all real validation.
- On validation error: show the backend's messages and **keep what the user typed**. Do not use `clear_on_submit=True`, because it clears the form even when validation fails.
- On success: show the returned risk level and remarks; if `risk_level == "Pending"` show a warning that the AI was unavailable and the record was saved. Then reset the form by incrementing a `form_nonce` in `st.session_state` and using it in the widget keys.

**Records page**
- Search box (name or email) -> `list_patients(search)`.
- Three summary numbers: total patients, High risk count, Pending count (computed from the loaded list).
- Table via `st.dataframe(df, on_select="rerun", selection_mode="single-row", hide_index=True)` with columns: Name, Date of birth, Email, Glucose, Haemoglobin, Cholesterol, Risk, Remarks. Read the selection from `event.selection.rows`.
- Empty state text when no records ("No patient records yet. Use Add patient to create one.").
- When a row is selected, show a detail section with the full remarks (the table truncates long text) and three buttons: **Edit**, **Re-run prediction**, **Delete**.
- **Edit:** store `edit_id` in `st.session_state`, show a form pre-filled with the record (DOB string as returned), submit calls `update_patient`, then clear `edit_id`.
- **Delete:** use `@st.dialog("Confirm delete")` with the patient's name, a Confirm button and a Cancel button. Only Confirm calls `delete_patient`.
- **Re-run prediction:** calls `rerun_prediction`, then refreshes.
- After any change, call `st.rerun()` so the table reflects the database.

**Streamlit facts to remember**
- Streamlit re-runs the whole script on every interaction. Anything that must survive a re-run lives in `st.session_state`.
- Do not cache API data with `st.cache_data`; the table must always show the current database state.
- Use a recent Streamlit version; `st.dialog` and dataframe row selection exist in current releases. If your installed version lacks them, upgrade rather than rewriting.

**`.streamlit/config.toml`** (basic theme, refined in Phase 8):
```toml
[theme]
base = "light"
primaryColor = "#2563EB"
```

**Run (two terminals)**
```
cd backend  && uvicorn app.main:app --reload
cd frontend && streamlit run app.py
```

**Verify:** `pytest -q` in `frontend/`, then run through the manual checklist in Phase 9, section A.

**Definition of done**
- [ ] Create, read, search, edit, delete, re-run all work from the UI.
- [ ] Backend validation messages appear next to a clear heading; entered values are kept after an error.
- [ ] Backend stopped -> friendly "cannot reach" message, no crash.
- [ ] `test_api_client.py` passes.

**Commit:** `feat: Streamlit frontend with full CRUD`

---

## Phase 8: UI polish (design)

**Goal:** a premium look **without** breaking behaviour or safety.

**Agent prompt**
```
Implement Phase 8 of PROJECT_PLAN.md only: create frontend/styles.py with a CSS string and apply it in app.py, update .streamlit/config.toml, and restyle the layout to match the design reference I provide. Do not change behaviour or API calls. Never insert user-provided text into HTML.
```

**Tasks**
1. Generate the design in Stitch AI using the prompt provided separately. Export or screenshot the screens.
2. Move colours, fonts and spacing into `.streamlit/config.toml` (`primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `font`).
3. Put the extra CSS in `styles.py` and inject once with `st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)`. **The CSS is a fixed string from our code; user data is never placed inside it.**
4. Use `st.container(border=True)`, `st.columns`, `st.metric`, and `st.tabs` to build cards, stat tiles, and sections.
5. Risk shown as a coloured label via a small mapping, for example `{"Low": "green", "Moderate": "orange", "High": "red", "Pending": "gray"}` using `st.badge` or a styled text label. If custom HTML is used for a badge, the badge text must come from this fixed mapping, never from raw API text.
6. Check text contrast is readable (dark text on light surfaces, no light-grey-on-white).

**Be realistic:** Streamlit can reproduce the layout, colour system, cards, spacing, and typography, but not every pixel of a free-form design. Prefer simplifying the design to fighting the framework.

**Definition of done**
- [ ] All Phase 7 behaviour still works (re-run the manual checklist).
- [ ] No `unsafe_allow_html` call contains user-provided data.
- [ ] Looks consistent on a laptop screen and a narrow window.

**Commit:** `style: apply visual design to the UI`

---

## Phase 9: Integration test and final review

### A. Manual end-to-end checklist (run with the real AI)

Use fictional data only.

| # | Action | Expected |
|---|---|---|
| 1 | Open the app with an empty database | Empty-state message |
| 2 | Add a patient with normal values | Saved; remark and Low risk shown |
| 3 | Add a patient with high glucose (e.g. 180) and high cholesterol (e.g. 260) | Moderate/High risk with sensible remark |
| 4 | Add a patient with low haemoglobin (e.g. 8) | Remark mentions possible anaemia and a doctor |
| 5 | Email `abc` | Clear email error; form values kept |
| 6 | DOB `2030-01-01`, `1/1/1990`, `31/02/2000` | dd/mm/yyyy or invalid-date error |
| 7 | DOB tomorrow | "cannot be in the future" |
| 8 | Glucose cannot be typed as text; try `9999` | Range error |
| 9 | Leave a field empty | "Please fill in all fields" |
| 10 | Add the same email twice | "already exists" error |
| 11 | Search by part of a name, then by part of an email | Table filters |
| 12 | Edit only the name | Saved; remark unchanged (no new AI call) |
| 13 | Edit glucose | Saved; remark and risk updated |
| 14 | Delete (Cancel first, then Confirm) | Cancel does nothing; Confirm removes it |
| 15 | Stop the backend, click anything | "Cannot reach the backend" message |
| 16 | Blank the API key, restart backend, add a patient | Saved as Pending with warning; restore key; Re-run prediction fixes it |
| 17 | Restart both apps | Records still present |
| 18 | Enter `<b>test</b>` and `' OR 1=1 --` in the name | Rejected by name validation; nothing breaks |

### B. Final automated run
```
cd backend  && pytest --cov=app
cd frontend && pytest -q
```

### C. Security and cleanup pass
- [ ] Section 10 fully ticked.
- [ ] `git ls-files` shows no `.env`, no `.db`, no `__pycache__`.
- [ ] Search the whole repo for: `TODO`, `FIXME`, `example`, `John`, `Jane`, `lorem`, `foo`, `bar`, `print(`, emojis in code, commented-out code. Remove or justify each hit (test data using `example.com` is fine).
- [ ] Names are consistent (British `haemoglobin` everywhere, `glucose`, `cholesterol`).
- [ ] No unused functions, files or dependencies.

**Commit:** `test: end-to-end verification and cleanup`

---

## Phase 10: Documentation and interview preparation

**README.md** must contain: what the app does; screenshots; tech stack; assumptions (units, no sex/fasting data); setup (venv, install, `.env`), how to get the Groq key; how to configure Supabase DATABASE_URL; run commands for both servers; how to run tests; API endpoint table; validation rules; security notes; known limitations; possible improvements.

**Known limitations to state honestly**
- No authentication or user roles.
- Cloud database connection requires internet access; local in-memory SQLite used for test isolation.
- No database migrations tool; schema changes need the DB table recreated in development.
- AI output is a screening hint, not medical advice; model output can vary between calls.
- Sex and fasting status are not collected, which limits the accuracy of interpretation.

**Possible improvements to mention:** authentication, Alembic migrations, retry with backoff for the AI call, rate limiting, audit log, pagination in the UI, per-test-type reference ranges by sex and age, encrypted storage for sensitive data.

### Code reading order for revision
`config.py` -> `database.py` -> `models.py` -> `utils.py` -> `schemas.py` -> `ai_service.py` -> `crud.py` -> `routes.py` -> `main.py` -> `api_client.py` -> `app.py` -> tests.

### 5-minute demo script
1. Show architecture in one sentence (UI -> API -> DB, API -> AI).
2. Add a valid patient; show the remark appearing.
3. Show two validation errors (bad email, future DOB).
4. Edit glucose; show the remark change.
5. Delete with confirmation.
6. Open `/docs`; show one endpoint.
7. Run `pytest`; show it passing.
8. Mention the AI-down behaviour (Pending + Re-run).

### Likely interview questions (prepare your own answers)

| Question | Key points |
|---|---|
| Why FastAPI? | Type-hint based validation, automatic docs, fast to build, async-capable |
| Why validate on the server when the UI could do it? | The UI can be bypassed; API is the trust boundary; one source of truth |
| How does the DOB validation work? | Before-validator parses the string, after-validator checks the range |
| Why `check_same_thread=False`? | Required when using SQLite (e.g. tests or local fallback) across worker threads; not needed for PostgreSQL |
| What is `get_db` / dependency injection? | Opens a session per request and always closes it; also easy to override in tests |
| How do you prevent SQL injection? | ORM with bound parameters; no string-built SQL |
| Why is the record saved if the AI fails? | Do not lose user data because a third party is down; status Pending + retry |
| Why sync routes? | Blocking AI call runs in the thread pool; simpler than async for this size |
| What goes to the AI and why? | Only age and 3 values; no personal identifiers |
| How do you stop bad AI output from reaching the DB? | Parse JSON, validate with a Pydantic model, fixed risk values, length caps |
| How did you test without calling the real AI? | Monkeypatched the function; also mocked `httpx.post` for the service tests |
| What happens on a duplicate email? | App-level check returns 409; DB unique constraint is the safety net |
| Where is the API key and how is it protected? | `.env`, git-ignored, sent in a header, never logged |
| Why PUT, not PATCH? | Simple full replace with the same schema |
| How would you scale this? | Auth, migrations, background task for AI, caching, containers |
| What are the weaknesses of this project? | See known limitations (be honest, it scores well) |

### Live-change drills (practise these)
1. **Add a new blood field (e.g. triglycerides).** Touch: `models.py`, `schemas.py` (field + range), `ai_service.py` (`build_prompt` + system instruction), `routes.py` (`inputs_changed`, calls to `get_prediction`), `app.py` (form + table), tests.
2. **Change a validation range** (e.g. glucose max): one line in `schemas.py` plus its boundary test.
3. **Add a filter by risk level:** a query parameter in `routes.py`, a `where` clause in `crud.py`, a selectbox in `app.py`, one test.
4. **Switch AI provider:** rewrite only `_call_groq` (URL, auth header, body, response path) and its tests.
5. **Change the date format** (e.g. `yyyy-mm-dd`): `DOB_PATTERN`, `DOB_FORMAT`, messages, tests, UI placeholder.

**Commit:** `docs: README and project notes`

---

## 11. Final submission checklist

- [ ] All 11 phases done with their Definition of done ticked.
- [ ] Tests green in backend and frontend.
- [ ] Live AI works with your own key; no key in the repository.
- [ ] README complete with run instructions.
- [ ] No generic AI artefacts, placeholder names, or leftover comments.
- [ ] You can explain every file, every function, and every decision in Section 3 without notes.
- [ ] A short demo run-through rehearsed at least twice.
