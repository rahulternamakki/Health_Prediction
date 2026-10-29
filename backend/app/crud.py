from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Patient
from app.schemas import PatientInput


def get_patient(db: Session, patient_id: int) -> Patient | None:
    return db.get(Patient, patient_id)


def get_by_email(db: Session, email: str) -> Patient | None:
    return db.scalar(select(Patient).where(Patient.email == email))


def list_patients(db: Session, search: str | None = None, skip: int = 0, limit: int = 100) -> list[Patient]:
    query = select(Patient).order_by(Patient.id.desc())
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Patient.full_name.ilike(pattern), Patient.email.ilike(pattern)))
    query = query.offset(skip).limit(limit)
    return list(db.scalars(query).all())


def create_patient(db: Session, data: PatientInput, risk_level: str, remarks: str | None) -> Patient:
    patient = Patient(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        email=data.email,
        glucose=data.glucose,
        haemoglobin=data.haemoglobin,
        cholesterol=data.cholesterol,
        risk_level=risk_level,
        remarks=remarks,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(
    db: Session, patient: Patient, data: PatientInput, risk_level: str, remarks: str | None
) -> Patient:
    patient.full_name = data.full_name
    patient.date_of_birth = data.date_of_birth
    patient.email = data.email
    patient.glucose = data.glucose
    patient.haemoglobin = data.haemoglobin
    patient.cholesterol = data.cholesterol
    patient.risk_level = risk_level
    patient.remarks = remarks
    db.commit()
    db.refresh(patient)
    return patient


def delete_patient(db: Session, patient: Patient) -> None:
    db.delete(patient)
    db.commit()
