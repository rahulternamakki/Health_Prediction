import re
from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
    field_validator,
)

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
