# Backend Architectural Notes & Interview Cheat Sheet

Each file has a single, distinct responsibility. Here is a one-sentence summary for each file to prepare for technical interviews:

### Application Modules (`backend/app/`)

- **`config.py`**: Loads and manages environment configuration variables (`GROQ_API_KEY`, `GROQ_MODEL`, `DATABASE_URL`, `AI_TIMEOUT_SECONDS`) with sensible defaults using `python-dotenv`.
- **`database.py`**: Initializes the SQLAlchemy 2.0 database engine and declarative `Base`, supplying the `get_db()` generator used for request-scoped database sessions.
- **`models.py`**: Defines the `Patient` SQLAlchemy ORM entity with typed columns, unique email index, default UTC timestamps, and table constraints.
- **`utils.py`**: Provides pure helper functions, specifically calculating exact patient age in calendar years from date of birth.
- **`schemas.py`**: Implements Pydantic v2 schemas (`PatientInput` and `PatientRead`) that enforce strict data validation, name cleaning, `dd/mm/yyyy` calendar date parsing, age boundaries, and physiological blood metric limits.
- **`ai_service.py`**: Manages outbound HTTP calls to the Groq Chat Completions API with strict 20-second timeouts, zero PII transmission (only age and blood metrics), and validated structured JSON parsing.
- **`crud.py`**: Encapsulates all database query and persistence operations (create, get by ID, get by email, search/paginate, update, delete) using SQLAlchemy 2.0 ORM expressions.
- **`routes.py`**: Implements synchronous FastAPI route handlers for all patient CRUD operations and manual prediction re-runs, coordinating validation, AI predictions, conflict detection, and fallback handling.
- **`main.py`**: Instantiates the FastAPI application, mounts the `/patients` router, runs lifespan table initialization, and exposes the root `/health` liveness probe.

### Test Suite (`backend/tests/`)

- **`conftest.py`**: Configures isolated in-memory SQLite test databases per test function with FastAPI dependency overrides and an autouse mock for external AI calls.
- **`test_models.py`**: Tests database schema constraints, default column assignments, and UTC timestamp population on the `Patient` model.
- **`test_validation.py`**: Exercises 60+ test cases verifying validation rules for names, dates, email formats, and plausible blood metric limits.
- **`test_ai_service.py`**: Tests prompt construction without PII, JSON response schema validation, timeout handling, and error mapping without hitting external APIs.
- **`test_patients_api.py`**: Verifies all HTTP status codes (200, 201, 204, 404, 409, 422, 502), search filtering, pagination, AI failure fallback, SQL injection safety, and database integrity error rollbacks.
