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
    except Exception:
        return "Unexpected response from the server."
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):  # validation errors from FastAPI
        messages = []
        for item in detail:
            field = str(item.get("loc", ["Unknown"])[-1]).replace("_", " ").capitalize()
            msg = item.get("msg", "")
            text = msg.removeprefix("Value error, ")
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


def list_patients(search: str = ""):
    params = {"search": search} if search else None
    return _request("GET", "/patients", params=params)


def get_patient(patient_id: int):
    return _request("GET", f"/patients/{patient_id}")


def create_patient(payload: dict):
    return _request("POST", "/patients", json=payload)


def update_patient(patient_id: int, payload: dict):
    return _request("PUT", f"/patients/{patient_id}", json=payload)


def delete_patient(patient_id: int):
    return _request("DELETE", f"/patients/{patient_id}")


def rerun_prediction(patient_id: int):
    return _request("POST", f"/patients/{patient_id}/predict")
