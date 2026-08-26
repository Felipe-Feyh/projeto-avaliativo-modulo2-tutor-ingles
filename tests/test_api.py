"""Testes da API FastAPI (ponto de integracao low-code)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from mentoria.api import app, get_overrides
from mentoria.memory import StudentMemory
from mentoria.observability import AuditLog

client = TestClient(app)


def _overrides() -> dict:
    model = FakeListChatModel(
        responses=[
            json.dumps({"intent": "flashcards", "theme": "travel"}),
            json.dumps({"vocab": [{"term": "luggage", "translation": "bagagem"}]}),
            json.dumps({"examples": {"luggage": "My luggage is heavy."}}),
        ]
    )
    return {
        "model": model,
        "dictionary_lookup": lambda w: None,
        "memory": StudentMemory(":memory:"),
        "audit": AuditLog(),
    }


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ask_flashcards():
    app.dependency_overrides[get_overrides] = _overrides
    try:
        resp = client.post("/ask", json={"message": "viagens", "level": "B1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_type"] == "flashcards"
        assert len(data["flashcards"]) == 1
        assert data["flashcards"][0]["translation"] == "bagagem"
    finally:
        app.dependency_overrides.clear()


def test_ask_validacao_422():
    resp = client.post("/ask", json={"level": "B1"})  # falta message
    assert resp.status_code == 422


def test_ask_exige_api_key_quando_configurada(monkeypatch):
    monkeypatch.setattr(
        "mentoria.api.get_settings",
        lambda: SimpleNamespace(mentoria_api_key="secret", discord_webhook_url=""),
    )
    app.dependency_overrides[get_overrides] = _overrides
    try:
        sem_chave = client.post("/ask", json={"message": "viagens", "level": "B1"})
        assert sem_chave.status_code == 401

        com_chave = client.post(
            "/ask",
            json={"message": "viagens", "level": "B1"},
            headers={"X-API-Key": "secret"},
        )
        assert com_chave.status_code == 200
    finally:
        app.dependency_overrides.clear()
