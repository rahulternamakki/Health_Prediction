from datetime import date, timedelta
import pytest
from pydantic import ValidationError

from app.schemas import PatientInput, PatientRead

VALID = {
    "full_name": "Test Patient",
    "date_of_birth": "15/08/1995",
    "email": "test.patient@example.com",
    "glucose": 92.0,
    "haemoglobin": 14.2,
    "cholesterol": 178.0,
}


@pytest.mark.parametrize(
    "invalid_email",
    [
        "abc",
        "a@",
        "@b.com",
        "a b@c.com",
        "",
    ],
)
def test_invalid_email(invalid_email):
    payload = {**VALID, "email": invalid_email}
    with pytest.raises(ValidationError):
        PatientInput(**payload)


@pytest.mark.parametrize(
    "invalid_dob",
    [
        "1995-08-15",
        "15-08-1995",
        "5/8/1995",
        "31/02/2000",
        "15/13/1990",
        "00/01/1990",
        (date.today() + timedelta(days=1)).strftime("%d/%m/%Y"),
        "01/01/1800",
        "",
        "abc",
    ],
)
def test_invalid_date_of_birth(invalid_dob):
    payload = {**VALID, "date_of_birth": invalid_dob}
    with pytest.raises(ValidationError):
        PatientInput(**payload)


@pytest.mark.parametrize(
    "invalid_value",
    [
        "abc",
        "",
        None,
        -5,
        0,
        19.9,
        600.1,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_glucose(invalid_value):
    payload = {**VALID, "glucose": invalid_value}
    with pytest.raises(ValidationError):
        PatientInput(**payload)


@pytest.mark.parametrize(
    "invalid_value",
    [
        "abc",
        "",
        None,
        -5,
        0,
        2.9,
        25.1,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_haemoglobin(invalid_value):
    payload = {**VALID, "haemoglobin": invalid_value}
    with pytest.raises(ValidationError):
        PatientInput(**payload)


@pytest.mark.parametrize(
    "invalid_value",
    [
        "abc",
        "",
        None,
        -5,
        0,
        49.9,
        600.1,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_cholesterol(invalid_value):
    payload = {**VALID, "cholesterol": invalid_value}
    with pytest.raises(ValidationError):
        PatientInput(**payload)


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "A",
        "Test123",
        "<script>",
        "   ",
        "A" * 101,
    ],
)
def test_invalid_full_name(invalid_name):
    payload = {**VALID, "full_name": invalid_name}
    with pytest.raises(ValidationError):
        PatientInput(**payload)


def test_valid_payload_accepted():
    patient = PatientInput(**VALID)
    assert patient.full_name == "Test Patient"
    assert patient.date_of_birth == date(1995, 8, 15)
    assert patient.email == "test.patient@example.com"
    assert patient.glucose == 92.0
    assert patient.haemoglobin == 14.2
    assert patient.cholesterol == 178.0


def test_dob_today_accepted():
    today = date.today()
    payload = {**VALID, "date_of_birth": today.strftime("%d/%m/%Y")}
    patient = PatientInput(**payload)
    assert patient.date_of_birth == today


def test_dob_120_years_ago_accepted():
    today = date.today()
    try:
        max_past_dob = date(today.year - 120, today.month, today.day)
    except ValueError:
        max_past_dob = date(today.year - 120, today.month, today.day - 1)
    payload = {**VALID, "date_of_birth": max_past_dob.strftime("%d/%m/%Y")}
    patient = PatientInput(**payload)
    assert patient.date_of_birth == max_past_dob


def test_email_lowercased():
    payload = {**VALID, "email": "Test.Patient@Example.COM"}
    patient = PatientInput(**payload)
    assert patient.email == "test.patient@example.com"


def test_name_whitespace_collapsed():
    payload = {**VALID, "full_name": "  Anne-Marie   O'Neil  "}
    patient = PatientInput(**payload)
    assert patient.full_name == "Anne-Marie O'Neil"


@pytest.mark.parametrize("glucose", [20.0, 600.0])
@pytest.mark.parametrize("haemoglobin", [3.0, 25.0])
@pytest.mark.parametrize("cholesterol", [50.0, 600.0])
def test_boundary_blood_values_accepted(glucose, haemoglobin, cholesterol):
    payload = {
        **VALID,
        "glucose": glucose,
        "haemoglobin": haemoglobin,
        "cholesterol": cholesterol,
    }
    patient = PatientInput(**payload)
    assert patient.glucose == glucose
    assert patient.haemoglobin == haemoglobin
    assert patient.cholesterol == cholesterol


def test_patient_read_serialization():
    data = {
        "id": 1,
        "full_name": "Test Patient",
        "date_of_birth": date(1995, 8, 15),
        "email": "test.patient@example.com",
        "glucose": 92.0,
        "haemoglobin": 14.2,
        "cholesterol": 178.0,
        "risk_level": "Low",
        "remarks": "Healthy profile.",
    }
    read_model = PatientRead.model_validate(data)
    dumped = read_model.model_dump(mode="json")
    assert dumped["date_of_birth"] == "15/08/1995"
    assert dumped["id"] == 1
    assert dumped["full_name"] == "Test Patient"
    assert dumped["risk_level"] == "Low"
