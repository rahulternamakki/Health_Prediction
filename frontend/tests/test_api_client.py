import pytest
import requests

from api_client import (
    ApiError,
    create_patient,
    delete_patient,
    extract_error_message,
    get_patient,
    list_patients,
    rerun_prediction,
    update_patient,
)


class MockResponse:
    def __init__(self, status_code: int, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        if self._json_data is None:
            raise ValueError("No JSON")
        return self._json_data


def test_200_returns_json(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, **kwargs: MockResponse(200, json_data={"id": 1, "full_name": "Alice"}),
    )
    result = get_patient(1)
    assert result == {"id": 1, "full_name": "Alice"}


def test_204_returns_none(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, **kwargs: MockResponse(204),
    )
    result = delete_patient(1)
    assert result is None


def test_422_list_detail_formatting(monkeypatch):
    validation_detail = [
        {"loc": ["body", "email"], "msg": "Value error, Invalid email format"},
        {"loc": ["body", "date_of_birth"], "msg": "Value error, Date of birth must be in dd/mm/yyyy format"},
    ]
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, **kwargs: MockResponse(422, json_data={"detail": validation_detail}),
    )
    with pytest.raises(ApiError) as exc_info:
        create_patient({})
    assert exc_info.value.status_code == 422
    assert "Email: Invalid email format" in exc_info.value.message
    assert "Date of birth: Date of birth must be in dd/mm/yyyy format" in exc_info.value.message


def test_409_string_detail_passed_through(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, **kwargs: MockResponse(
            409, json_data={"detail": "A patient with this email already exists"}
        ),
    )
    with pytest.raises(ApiError) as exc_info:
        create_patient({})
    assert exc_info.value.status_code == 409
    assert exc_info.value.message == "A patient with this email already exists"


def test_404_not_found_handling(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, **kwargs: MockResponse(404, json_data={"detail": "Patient not found"}),
    )
    with pytest.raises(ApiError) as exc_info:
        get_patient(999)
    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "Patient not found"


def test_connection_error_becomes_api_error(monkeypatch):
    def raise_conn_error(*args, **kwargs):
        raise requests.ConnectionError("Connection refused")

    monkeypatch.setattr(requests, "request", raise_conn_error)
    with pytest.raises(ApiError) as exc_info:
        list_patients()
    assert "Cannot reach the backend service" in exc_info.value.message
    assert exc_info.value.status_code is None


def test_timeout_error_becomes_api_error(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("Read timed out")

    monkeypatch.setattr(requests, "request", raise_timeout)
    with pytest.raises(ApiError) as exc_info:
        list_patients()
    assert "Cannot reach the backend service" in exc_info.value.message
    assert exc_info.value.status_code is None


def test_non_json_error_body_does_not_crash(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, **kwargs: MockResponse(500, json_data=ValueError("Bad JSON"), text="Internal Error"),
    )
    with pytest.raises(ApiError) as exc_info:
        list_patients()
    assert exc_info.value.status_code == 500
    assert exc_info.value.message == "Unexpected response from the server."


def test_list_patients_sends_search_query_parameter(monkeypatch):
    captured_kwargs = {}

    def mock_req(method, url, **kwargs):
        captured_kwargs.update(kwargs)
        return MockResponse(200, json_data=[])

    monkeypatch.setattr(requests, "request", mock_req)
    list_patients(search="alice")
    assert captured_kwargs["params"] == {"search": "alice"}

    list_patients(search="")
    assert captured_kwargs["params"] is None


def test_crud_wrapper_endpoints(monkeypatch):
    calls = []

    def mock_req(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if method == "DELETE":
            return MockResponse(204)
        return MockResponse(200, json_data={"status": "ok"})

    monkeypatch.setattr(requests, "request", mock_req)

    create_patient({"name": "Test"})
    assert calls[-1][0] == "POST"
    assert calls[-1][1].endswith("/patients")
    assert calls[-1][2]["json"] == {"name": "Test"}

    update_patient(42, {"name": "Updated"})
    assert calls[-1][0] == "PUT"
    assert calls[-1][1].endswith("/patients/42")
    assert calls[-1][2]["json"] == {"name": "Updated"}

    rerun_prediction(42)
    assert calls[-1][0] == "POST"
    assert calls[-1][1].endswith("/patients/42/predict")

    delete_patient(42)
    assert calls[-1][0] == "DELETE"
    assert calls[-1][1].endswith("/patients/42")


def test_extract_error_message_fallback():
    mock_resp = MockResponse(400, json_data={"other_key": 123})
    assert extract_error_message(mock_resp) == "The request could not be completed."
