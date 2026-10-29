from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Patient
from app.utils import calculate_age


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_insert_and_read_patient(db_session):
    patient = Patient(
        full_name="Patient Alpha",
        date_of_birth=date(1990, 5, 20),
        email="patient.alpha@clinic.test",
        glucose=95.0,
        haemoglobin=14.5,
        cholesterol=180.0,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    assert patient.id is not None
    assert patient.full_name == "Patient Alpha"
    assert patient.date_of_birth == date(1990, 5, 20)
    assert patient.email == "patient.alpha@clinic.test"
    assert patient.glucose == 95.0
    assert patient.haemoglobin == 14.5
    assert patient.cholesterol == 180.0
    assert patient.risk_level == "Pending"
    assert patient.remarks is None
    assert patient.created_at is not None
    assert patient.updated_at is not None

    stmt = select(Patient).where(Patient.email == "patient.alpha@clinic.test")
    retrieved = db_session.scalar(stmt)
    assert retrieved is not None
    assert retrieved.id == patient.id
    assert retrieved.full_name == "Patient Alpha"


def test_unique_email_constraint(db_session):
    patient1 = Patient(
        full_name="Patient One",
        date_of_birth=date(1985, 3, 10),
        email="duplicate@clinic.test",
        glucose=90.0,
        haemoglobin=13.0,
        cholesterol=170.0,
    )
    patient2 = Patient(
        full_name="Patient Two",
        date_of_birth=date(1992, 7, 15),
        email="duplicate@clinic.test",
        glucose=110.0,
        haemoglobin=15.0,
        cholesterol=200.0,
    )
    db_session.add(patient1)
    db_session.commit()

    db_session.add(patient2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_calculate_age_birthday_passed():
    dob = date(1990, 3, 15)
    today = date(2026, 10, 20)
    assert calculate_age(dob, today=today) == 36


def test_calculate_age_birthday_not_reached():
    dob = date(1990, 12, 25)
    today = date(2026, 10, 20)
    assert calculate_age(dob, today=today) == 35


def test_calculate_age_birthday_today():
    dob = date(1990, 10, 20)
    today = date(2026, 10, 20)
    assert calculate_age(dob, today=today) == 36
