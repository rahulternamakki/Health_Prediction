import json
import httpx
import pytest

from app import ai_service, config
from app.ai_service import (
    AIPrediction,
    AIServiceError,
    _call_groq,
    build_prompt,
    parse_prediction,
    predict_health_risk,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, raw_text=None):
        self.status_code = status_code
        self._payload = payload
        self._raw_text = raw_text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    @property
    def text(self):
        return self._raw_text or ""


def test_build_prompt():
    prompt = build_prompt(age=45, glucose=105.45, haemoglobin=13.82, cholesterol=210.67)
    assert "Patient age: 45 years." in prompt
    assert "Glucose: 105.5 mg/dL" in prompt
    assert "Haemoglobin: 13.8 g/dL" in prompt
    assert "Total cholesterol: 210.7 mg/dL" in prompt


def test_parse_prediction_valid():
    raw_json = json.dumps({
        "risk_level": "Moderate",
        "possible_condition": "Borderline elevated glucose.",
        "advice": "Consult a physician for follow-up testing.",
    })
    prediction = parse_prediction(raw_json)
    assert isinstance(prediction, AIPrediction)
    assert prediction.risk_level == "Moderate"
    assert prediction.possible_condition == "Borderline elevated glucose."
    assert prediction.advice == "Consult a physician for follow-up testing."
    assert prediction.remarks == "Borderline elevated glucose. Consult a physician for follow-up testing."


def test_parse_prediction_no_trailing_dot():
    raw_json = json.dumps({
        "risk_level": "Low",
        "possible_condition": "Normal blood markers",
        "advice": "Maintain healthy lifestyle and see a doctor.",
    })
    prediction = parse_prediction(raw_json)
    assert prediction.remarks == "Normal blood markers. Maintain healthy lifestyle and see a doctor."


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not-a-json",
        json.dumps(["item1", "item2"]),
        json.dumps({"risk_level": "Low"}),
        json.dumps({
            "risk_level": "Critical",
            "possible_condition": "Valid",
            "advice": "Valid advice.",
        }),
        "",
        json.dumps({
            "risk_level": "High",
            "possible_condition": "Valid condition",
            "advice": "A" * 401,
        }),
    ],
)
def test_parse_prediction_invalid(invalid_input):
    with pytest.raises(AIServiceError):
        parse_prediction(invalid_input)


def test_call_groq_success(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(config, "GROQ_MODEL", "llama-3.3-70b-versatile")

    recorded_kwargs = {}

    def fake_post(url, headers, json, timeout):
        recorded_kwargs["url"] = url
        recorded_kwargs["headers"] = headers
        recorded_kwargs["json"] = json
        recorded_kwargs["timeout"] = timeout
        return FakeResponse(
            status_code=200,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": '{"risk_level":"Low","possible_condition":"None","advice":"Confirm with a doctor."}'
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)

    result = _call_groq("Sample prompt")
    assert '{"risk_level":"Low"' in result
    assert recorded_kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert recorded_kwargs["json"]["model"] == "llama-3.3-70b-versatile"
    assert recorded_kwargs["json"]["response_format"] == {"type": "json_object"}


def test_call_groq_missing_api_key(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "")

    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)

    with pytest.raises(AIServiceError) as exc_info:
        _call_groq("Prompt")

    assert "API key is not configured" in str(exc_info.value)
    assert not called


@pytest.mark.parametrize("status_code", [400, 401, 429, 500])
def test_call_groq_non_200(monkeypatch, status_code):
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")

    def fake_post(*args, **kwargs):
        return FakeResponse(status_code=status_code, payload={"error": "fail"})

    monkeypatch.setattr(ai_service.httpx, "post", fake_post)

    with pytest.raises(AIServiceError) as exc_info:
        _call_groq("Prompt")
    assert f"AI API returned status {status_code}" in str(exc_info.value)
    assert "test-key" not in str(exc_info.value)


def test_call_groq_network_errors(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")

    def fake_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(ai_service.httpx, "post", fake_timeout)
    with pytest.raises(AIServiceError) as exc_info:
        _call_groq("Prompt")
    assert "Request failed: TimeoutException" in str(exc_info.value)
    assert "test-key" not in str(exc_info.value)

    def fake_connect_err(*args, **kwargs):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(ai_service.httpx, "post", fake_connect_err)
    with pytest.raises(AIServiceError) as exc_info:
        _call_groq("Prompt")
    assert "Request failed: ConnectError" in str(exc_info.value)
    assert "test-key" not in str(exc_info.value)


def test_call_groq_bad_response_shape(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")

    # 200 with empty choices
    monkeypatch.setattr(
        ai_service.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(status_code=200, payload={"choices": []}),
    )
    with pytest.raises(AIServiceError) as exc_info:
        _call_groq("Prompt")
    assert "Unexpected AI API response shape" in str(exc_info.value)

    # 200 with non-JSON body
    monkeypatch.setattr(
        ai_service.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(status_code=200, payload=None),
    )
    with pytest.raises(AIServiceError) as exc_info:
        _call_groq("Prompt")
    assert "Unexpected AI API response shape" in str(exc_info.value)


def test_predict_health_risk_end_to_end(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")

    response_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "risk_level": "High",
                        "possible_condition": "Suspected type 2 diabetes",
                        "advice": "Please consult a medical doctor promptly for formal laboratory evaluation.",
                    })
                }
            }
        ]
    }

    monkeypatch.setattr(
        ai_service.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(status_code=200, payload=response_payload),
    )

    pred = predict_health_risk(55, 185.0, 13.5, 230.0)
    assert pred.risk_level == "High"
    assert pred.possible_condition == "Suspected type 2 diabetes"
    assert "consult a medical doctor" in pred.advice
    assert (
        pred.remarks
        == "Suspected type 2 diabetes. Please consult a medical doctor promptly for formal laboratory evaluation."
    )
