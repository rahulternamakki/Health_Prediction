from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app import ai_service, crud, database
from app.main import app as main_app
from app.main import lifespan
from app.routes import FALLBACK_REMARKS
from app.utils import calculate_age

VALID_PAYLOAD = {
    "full_name": "Test Patient",
    "date_of_birth": "15/08/1995",
    "email": "test.patient@example.com",
    "glucose": 92.0,
    "haemoglobin": 14.2,
    "cholesterol": 178.0,
}

INVALID_PAYLOADS = [
    {**VALID_PAYLOAD, "email": "abc"},
    {**VALID_PAYLOAD, "email": "a@"},
    {**VALID_PAYLOAD, "email": "@b.com"},
    {**VALID_PAYLOAD, "email": "a b@c.com"},
    {**VALID_PAYLOAD, "email": ""},
    {**VALID_PAYLOAD, "date_of_birth": "1995-08-15"},
    {**VALID_PAYLOAD, "date_of_birth": "15-08-1995"},
    {**VALID_PAYLOAD, "date_of_birth": "5/8/1995"},
    {**VALID_PAYLOAD, "date_of_birth": "31/02/2000"},
    {**VALID_PAYLOAD, "date_of_birth": "15/13/1990"},
    {**VALID_PAYLOAD, "date_of_birth": "00/01/1990"},
    {**VALID_PAYLOAD, "date_of_birth": (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")},
    {**VALID_PAYLOAD, "date_of_birth": "01/01/1800"},
    {**VALID_PAYLOAD, "date_of_birth": ""},
    {**VALID_PAYLOAD, "date_of_birth": "abc"},
    {**VALID_PAYLOAD, "glucose": "abc"},
    {**VALID_PAYLOAD, "glucose": 19.9},
    {**VALID_PAYLOAD, "glucose": 600.1},
    {**VALID_PAYLOAD, "haemoglobin": "abc"},
    {**VALID_PAYLOAD, "haemoglobin": 2.9},
    {**VALID_PAYLOAD, "haemoglobin": 25.1},
    {**VALID_PAYLOAD, "cholesterol": "abc"},
    {**VALID_PAYLOAD, "cholesterol": 49.9},
    {**VALID_PAYLOAD, "cholesterol": 600.1},
    {**VALID_PAYLOAD, "full_name": ""},
    {**VALID_PAYLOAD, "full_name": "A"},
    {**VALID_PAYLOAD, "full_name": "Test123"},
    {**VALID_PAYLOAD, "full_name": "<script>"},
    {**VALID_PAYLOAD, "full_name": "   "},
    {**VALID_PAYLOAD, "full_name": "A" * 101},
]


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_patient_valid(client, fake_ai):
    payload = {**VALID_PAYLOAD, "email": "Test.Patient@Example.COM"}
    response = client.post("/patients", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["full_name"] == "Test Patient"
    assert data["date_of_birth"] == "15/08/1995"
    assert data["email"] == "test.patient@example.com"  # lowercase
    assert data["risk_level"] == "Low"
    assert data["remarks"] != ""

    assert len(fake_ai) == 1
    expected_age = calculate_age(date(1995, 8, 15))
    assert fake_ai[0] == (expected_age, 92.0, 14.2, 178.0)


@pytest.mark.parametrize("invalid_payload", INVALID_PAYLOADS)
def test_create_patient_invalid_cases(client, invalid_payload):
    response = client.post("/patients", json=invalid_payload)
    assert response.status_code == 422
    list_resp = client.get("/patients")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


def test_create_patient_duplicate_email(client):
    res1 = client.post("/patients", json=VALID_PAYLOAD)
    assert res1.status_code == 201

    payload_upper = {**VALID_PAYLOAD, "full_name": "Another Name", "email": "TEST.PATIENT@EXAMPLE.COM"}
    res2 = client.post("/patients", json=payload_upper)
    assert res2.status_code == 409
    assert res2.json()["detail"] == "A patient with this email already exists"


def test_create_patient_ai_failure(client, monkeypatch):
    def failing_predict(*args, **kwargs):
        raise ai_service.AIServiceError("Groq service timeout")

    monkeypatch.setattr(ai_service, "predict_health_risk", failing_predict)

    res = client.post("/patients", json=VALID_PAYLOAD)
    assert res.status_code == 201
    data = res.json()
    assert data["risk_level"] == "Pending"
    assert data["remarks"] == FALLBACK_REMARKS


def test_read_patients_list_and_search(client):
    assert client.get("/patients").json() == []

    p1 = {**VALID_PAYLOAD, "full_name": "Alice Smith", "email": "alice@clinic.com"}
    p2 = {**VALID_PAYLOAD, "full_name": "Bob Jones", "email": "bob@hospital.com"}

    res1 = client.post("/patients", json=p1)
    res2 = client.post("/patients", json=p2)
    id1 = res1.json()["id"]
    id2 = res2.json()["id"]

    all_patients = client.get("/patients").json()
    assert len(all_patients) == 2
    assert all_patients[0]["id"] == id2  # newest first
    assert all_patients[1]["id"] == id1

    # Search by part of name
    res_name = client.get("/patients", params={"search": "Alice"}).json()
    assert len(res_name) == 1
    assert res_name[0]["full_name"] == "Alice Smith"

    # Search by part of email
    res_email = client.get("/patients", params={"search": "HOSPITAL"}).json()
    assert len(res_email) == 1
    assert res_email[0]["email"] == "bob@hospital.com"

    # Search with no match
    res_none = client.get("/patients", params={"search": "nonexistent"}).json()
    assert res_none == []


def test_read_patients_pagination_validation(client):
    assert client.get("/patients", params={"limit": 0}).status_code == 422
    assert client.get("/patients", params={"limit": 101}).status_code == 422
    assert client.get("/patients", params={"skip": -1}).status_code == 422


def test_get_patient_by_id(client):
    created = client.post("/patients", json=VALID_PAYLOAD).json()
    patient_id = created["id"]

    res_ok = client.get(f"/patients/{patient_id}")
    assert res_ok.status_code == 200
    assert res_ok.json()["id"] == patient_id

    assert client.get("/patients/999999").status_code == 404
    assert client.get("/patients/invalid-id").status_code == 422


def test_update_patient_name_only_no_ai_rerun(client, fake_ai):
    created = client.post("/patients", json=VALID_PAYLOAD).json()
    patient_id = created["id"]
    initial_calls = len(fake_ai)

    update_payload = {**VALID_PAYLOAD, "full_name": "Updated Name"}
    res = client.put(f"/patients/{patient_id}", json=update_payload)
    assert res.status_code == 200
    assert res.json()["full_name"] == "Updated Name"
    assert len(fake_ai) == initial_calls
    assert res.json()["remarks"] == created["remarks"]


def test_update_patient_glucose_triggers_ai(client, fake_ai):
    created = client.post("/patients", json=VALID_PAYLOAD).json()
    patient_id = created["id"]
    initial_calls = len(fake_ai)

    update_payload = {**VALID_PAYLOAD, "glucose": 150.0}
    res = client.put(f"/patients/{patient_id}", json=update_payload)
    assert res.status_code == 200
    assert len(fake_ai) == initial_calls + 1
    assert fake_ai[-1][1] == 150.0


def test_update_patient_dob_triggers_ai(client, fake_ai):
    created = client.post("/patients", json=VALID_PAYLOAD).json()
    patient_id = created["id"]
    initial_calls = len(fake_ai)

    update_payload = {**VALID_PAYLOAD, "date_of_birth": "10/10/1980"}
    res = client.put(f"/patients/{patient_id}", json=update_payload)
    assert res.status_code == 200
    assert len(fake_ai) == initial_calls + 1
    expected_new_age = calculate_age(date(1980, 10, 10))
    assert fake_ai[-1][0] == expected_new_age


def test_update_patient_pending_record_triggers_ai(client, fake_ai, monkeypatch):
    # Create with failing AI
    monkeypatch.setattr(
        ai_service,
        "predict_health_risk",
        lambda *args, **kwargs: (_ for _ in ()).throw(ai_service.AIServiceError("err")),
    )
    created = client.post("/patients", json=VALID_PAYLOAD).json()
    assert created["risk_level"] == "Pending"

    # Restore working fake AI
    calls = []

    def working_predict(age, glucose, haemoglobin, cholesterol):
        calls.append((age, glucose, haemoglobin, cholesterol))
        return ai_service.AIPrediction(
            risk_level="Low",
            possible_condition="Healthy indicators",
            advice="Consult a doctor.",
        )

    monkeypatch.setattr(ai_service, "predict_health_risk", working_predict)

    # Update only the name
    update_payload = {**VALID_PAYLOAD, "full_name": "New Name Only"}
    res = client.put(f"/patients/{created['id']}", json=update_payload)
    assert res.status_code == 200
    assert res.json()["risk_level"] == "Low"
    assert len(calls) == 1


def test_update_patient_not_found_and_invalid(client):
    assert client.put("/patients/999999", json=VALID_PAYLOAD).status_code == 404

    created = client.post("/patients", json=VALID_PAYLOAD).json()
    bad_payload = {**VALID_PAYLOAD, "email": "invalid-email"}
    assert client.put(f"/patients/{created['id']}", json=bad_payload).status_code == 422

    # Verify stored record unchanged
    stored = client.get(f"/patients/{created['id']}").json()
    assert stored["email"] == VALID_PAYLOAD["email"]


def test_update_patient_email_conflict(client):
    client.post("/patients", json={**VALID_PAYLOAD, "email": "p1@clinic.com"})
    p2 = client.post("/patients", json={**VALID_PAYLOAD, "email": "p2@clinic.com"}).json()

    # Changing p2 email to p1's email -> 409
    res_conflict = client.put(f"/patients/{p2['id']}", json={**VALID_PAYLOAD, "email": "p1@clinic.com"})
    assert res_conflict.status_code == 409

    # Keeping own email -> 200
    res_own = client.put(f"/patients/{p2['id']}", json={**VALID_PAYLOAD, "email": "p2@clinic.com"})
    assert res_own.status_code == 200


def test_delete_patient(client):
    p1 = client.post("/patients", json={**VALID_PAYLOAD, "email": "p1@clinic.com"}).json()
    p2 = client.post("/patients", json={**VALID_PAYLOAD, "email": "p2@clinic.com"}).json()

    del_res = client.delete(f"/patients/{p1['id']}")
    assert del_res.status_code == 204

    assert client.get(f"/patients/{p1['id']}").status_code == 404
    assert client.delete(f"/patients/{p1['id']}").status_code == 404

    # Other record untouched
    assert client.get(f"/patients/{p2['id']}").status_code == 200


def test_predict_endpoint_success_and_failure(client, monkeypatch):
    # Create with pending
    monkeypatch.setattr(
        ai_service,
        "predict_health_risk",
        lambda *args, **kwargs: (_ for _ in ()).throw(ai_service.AIServiceError("err")),
    )
    created = client.post("/patients", json=VALID_PAYLOAD).json()
    assert created["risk_level"] == "Pending"

    # Working predict call
    monkeypatch.setattr(
        ai_service,
        "predict_health_risk",
        lambda *args, **kwargs: ai_service.AIPrediction(
            risk_level="Low",
            possible_condition="Normal",
            advice="Consult doctor.",
        ),
    )
    res_pred = client.post(f"/patients/{created['id']}/predict")
    assert res_pred.status_code == 200
    assert res_pred.json()["risk_level"] == "Low"

    # Failing predict call -> 502
    monkeypatch.setattr(
        ai_service,
        "predict_health_risk",
        lambda *args, **kwargs: (_ for _ in ()).throw(ai_service.AIServiceError("timeout")),
    )
    res_fail = client.post(f"/patients/{created['id']}/predict")
    assert res_fail.status_code == 502
    assert res_fail.json()["detail"] == "AI service is unavailable. Please try again later."

    # Unknown id -> 404
    assert client.post("/patients/999999/predict").status_code == 404


def test_sql_injection_search(client):
    client.post("/patients", json=VALID_PAYLOAD)
    res = client.get("/patients", params={"search": "' OR 1=1 --"})
    assert res.status_code == 200
    assert res.json() == []

    all_recs = client.get("/patients").json()
    assert len(all_recs) == 1


def test_persistence_across_reads(client):
    client.post("/patients", json=VALID_PAYLOAD)
    first_read = client.get("/patients").json()
    assert len(first_read) == 1
    second_read = client.get("/patients").json()
    assert len(second_read) == 1
    assert first_read == second_read


def test_manual_edge_cases_clean_json_errors(client):
    # DOB 31/02/2000
    res = client.post("/patients", json={**VALID_PAYLOAD, "date_of_birth": "31/02/2000"})
    assert res.status_code == 422
    assert "Date of birth is not a valid calendar date" in res.text

    # glucose "abc"
    res = client.post("/patients", json={**VALID_PAYLOAD, "glucose": "abc"})
    assert res.status_code == 422
    assert "Input should be a valid number" in res.text

    # empty body
    res = client.post("/patients", json={})
    assert res.status_code == 422

    # id 999999
    res = client.get("/patients/999999")
    assert res.status_code == 404
    assert res.json() == {"detail": "Patient not found"}

    # limit=1000
    res = client.get("/patients?limit=1000")
    assert res.status_code == 422


def test_create_patient_integrity_error_handled(client, monkeypatch):
    def mock_create(*args, **kwargs):
        raise IntegrityError("mock_statement", {}, Exception("unique constraint violation"))

    monkeypatch.setattr(crud, "create_patient", mock_create)
    res = client.post("/patients", json=VALID_PAYLOAD)
    assert res.status_code == 409
    assert res.json()["detail"] == "A patient with this email already exists"


def test_update_patient_integrity_error_handled(client, monkeypatch):
    created = client.post("/patients", json=VALID_PAYLOAD).json()

    def mock_update(*args, **kwargs):
        raise IntegrityError("mock_statement", {}, Exception("unique constraint violation"))

    monkeypatch.setattr(crud, "update_patient", mock_update)
    res = client.put(f"/patients/{created['id']}", json=VALID_PAYLOAD)
    assert res.status_code == 409
    assert res.json()["detail"] == "A patient with this email already exists"


@pytest.mark.anyio
async def test_app_lifespan(monkeypatch):
    from unittest.mock import MagicMock

    mock_create_all = MagicMock()
    monkeypatch.setattr(database.Base.metadata, "create_all", mock_create_all)
    async with lifespan(main_app):
        pass
    assert mock_create_all.called


def test_database_get_db(monkeypatch):
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    mock_session_local = MagicMock(return_value=mock_session)
    monkeypatch.setattr(database, "SessionLocal", mock_session_local)

    gen = database.get_db()
    db = next(gen)
    assert db is mock_session
    try:
        next(gen)
    except StopIteration:
        pass
    mock_session.close.assert_called_once()

