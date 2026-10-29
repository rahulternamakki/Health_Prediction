import json
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app import config

logger = logging.getLogger(__name__)

API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_INSTRUCTION = (
    "You are a clinical decision-support assistant used in a screening demo. "
    "Given an adult's age and three blood test values, estimate the most likely health risk. "
    "You do not diagnose.\n"
    "Reference guidance: fasting glucose 70-99 mg/dL is normal, 100-125 is the prediabetes range, "
    "126 or above is the diabetes range. Haemoglobin below roughly 12 g/dL suggests possible "
    "anaemia and above roughly 17.5 g/dL is high; sex is not provided, so be conservative. "
    "Total cholesterol below 200 mg/dL is desirable, 200-239 is borderline high, 240 or above is high.\n"
    "Respond with one JSON object with exactly these keys: \"risk_level\" (one of \"Low\", \"Moderate\", \"High\"), "
    "\"possible_condition\" (maximum 15 words), \"advice\" (maximum 35 words, and it must recommend confirming with a doctor). "
    "Output JSON only."
)


class AIServiceError(Exception):
    pass


class AIPrediction(BaseModel):
    risk_level: Literal["Low", "Moderate", "High"]
    possible_condition: str = Field(min_length=1, max_length=150)
    advice: str = Field(min_length=1, max_length=400)

    @property
    def remarks(self) -> str:
        return f"{self.possible_condition.rstrip('.')}. {self.advice}"


def build_prompt(age: int, glucose: float, haemoglobin: float, cholesterol: float) -> str:
    return (
        f"Patient age: {age} years. Glucose: {glucose:.1f} mg/dL (fasting status unknown). "
        f"Haemoglobin: {haemoglobin:.1f} g/dL. Total cholesterol: {cholesterol:.1f} mg/dL."
    )


def _call_groq(prompt: str) -> str:
    if not config.GROQ_API_KEY:
        raise AIServiceError("API key is not configured")
    body = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
    }
    try:
        response = httpx.post(
            API_URL,
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=config.AI_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise AIServiceError(f"Request failed: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise AIServiceError(f"AI API returned status {response.status_code}")
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIServiceError("Unexpected AI API response shape") from exc


def parse_prediction(text: str) -> AIPrediction:
    try:
        return AIPrediction.model_validate(json.loads(text))
    except (ValueError, TypeError) as exc:
        raise AIServiceError("AI response was not in the expected format") from exc


def predict_health_risk(age: int, glucose: float, haemoglobin: float, cholesterol: float) -> AIPrediction:
    text = _call_groq(build_prompt(age, glucose, haemoglobin, cholesterol))
    return parse_prediction(text)
