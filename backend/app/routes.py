import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import ai_service, crud
from app.database import get_db
from app.schemas import PatientInput, PatientRead
from app.utils import calculate_age

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["patients"])
DbSession = Annotated[Session, Depends(get_db)]
FALLBACK_REMARKS = "AI prediction unavailable. Select the record and choose Re-run prediction."


def get_prediction(dob, glucose: float, haemoglobin: float, cholesterol: float) -> tuple[str, str]:
    try:
        result = ai_service.predict_health_risk(calculate_age(dob), glucose, haemoglobin, cholesterol)
    except ai_service.AIServiceError as exc:
        logger.warning("AI prediction failed: %s", exc)
        return "Pending", FALLBACK_REMARKS
    return result.risk_level, result.remarks


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PatientRead)
def create_patient(data: PatientInput, db: DbSession):
    if crud.get_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this email already exists",
        )

    risk_level, remarks = get_prediction(
        data.date_of_birth, data.glucose, data.haemoglobin, data.cholesterol
    )

    try:
        return crud.create_patient(db, data, risk_level, remarks)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this email already exists",
        )


@router.get("", response_model=list[PatientRead])
def list_patients(
    db: DbSession,
    search: str | None = Query(None, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    return crud.list_patients(db, search=search, skip=skip, limit=limit)


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: int, db: DbSession):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.put("/{patient_id}", response_model=PatientRead)
def update_patient(patient_id: int, data: PatientInput, db: DbSession):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    existing_email_owner = crud.get_by_email(db, data.email)
    if existing_email_owner and existing_email_owner.id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this email already exists",
        )

    inputs_changed = (
        patient.date_of_birth != data.date_of_birth
        or patient.glucose != data.glucose
        or patient.haemoglobin != data.haemoglobin
        or patient.cholesterol != data.cholesterol
    )

    if inputs_changed or patient.risk_level == "Pending":
        risk_level, remarks = get_prediction(
            data.date_of_birth, data.glucose, data.haemoglobin, data.cholesterol
        )
    else:
        risk_level, remarks = patient.risk_level, patient.remarks

    try:
        return crud.update_patient(db, patient, data, risk_level, remarks)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this email already exists",
        )


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: int, db: DbSession):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    crud.delete_patient(db, patient)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{patient_id}/predict", response_model=PatientRead)
def rerun_prediction(patient_id: int, db: DbSession):
    patient = crud.get_patient(db, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    try:
        age = calculate_age(patient.date_of_birth)
        prediction = ai_service.predict_health_risk(
            age, patient.glucose, patient.haemoglobin, patient.cholesterol
        )
    except ai_service.AIServiceError as exc:
        logger.warning("Manual AI prediction failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service is unavailable. Please try again later.",
        )

    patient.risk_level = prediction.risk_level
    patient.remarks = prediction.remarks
    db.commit()
    db.refresh(patient)
    return patient
