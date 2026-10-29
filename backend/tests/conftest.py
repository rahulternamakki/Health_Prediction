import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ai_service, models  # noqa: F401
from app.database import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    calls = []

    def fake_predict(age, glucose, haemoglobin, cholesterol):
        calls.append((age, glucose, haemoglobin, cholesterol))
        return ai_service.AIPrediction(
            risk_level="Low",
            possible_condition="No significant risk indicators",
            advice="Maintain a healthy lifestyle and confirm with a doctor.",
        )

    monkeypatch.setattr(ai_service, "predict_health_risk", fake_predict)
    return calls
