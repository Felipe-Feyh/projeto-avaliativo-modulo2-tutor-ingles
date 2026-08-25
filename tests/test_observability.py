"""Testes de observabilidade: logs estruturados + trilha de auditoria."""

from __future__ import annotations

import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from structlog.testing import capture_logs

from mentoria.agent import run_agent
from mentoria.memory import StudentMemory
from mentoria.observability import AuditLog, configure_logging
from mentoria.schemas import AgentRequest, CEFRLevel
from mentoria.tools.dictionary import DictionaryResult


def _fake_model() -> FakeListChatModel:
    responses = [
        {"intent": "flashcards", "theme": "travel"},
        {"vocab": [{"term": "luggage", "translation": "bagagem"}]},
        {"examples": {"luggage": "My luggage is heavy."}},
    ]
    return FakeListChatModel(responses=[json.dumps(r) for r in responses])


def _fake_lookup(word: str) -> DictionaryResult | None:
    return DictionaryResult(word=word, phonetic="/x/", part_of_speech="noun")


def test_dois_sinais_correlacionados_por_run_id():
    audit = AuditLog()  # em memoria
    # Garante que a configuracao do structlog ja rodou antes de capturar,
    # para que capture_logs nao seja sobrescrito pela primeira configuracao.
    configure_logging()
    with capture_logs() as logs:
        run_agent(
            AgentRequest(message="viagens", level=CEFRLevel.B1),
            model=_fake_model(),
            dictionary_lookup=_fake_lookup,
            memory=StudentMemory(":memory:"),
            audit=audit,
        )

    # Sinal 2 (auditoria): varios nodes registrados, mesmo run_id, com latencia
    assert len(audit.records) >= 5
    run_ids = {r["run_id"] for r in audit.records}
    assert len(run_ids) == 1
    run_id = run_ids.pop()
    assert all("latency_ms" in r and r["status"] == "ok" for r in audit.records)

    # Reconstrucao da execucao por run_id
    nodes_seen = [r["node"] for r in audit.by_run(run_id)]
    assert "classify_intent" in nodes_seen
    assert "generate_vocabulary" in nodes_seen
    assert "build_report" in nodes_seen

    # Sinal 1 (logs estruturados): correlacionados pelo mesmo run_id
    node_logs = [e for e in logs if e.get("event") == "node.completed"]
    assert node_logs
    assert all(e["run_id"] == run_id for e in node_logs)


def test_auditlog_persiste_jsonl(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(str(path))
    audit.record(run_id="r1", node="a", status="ok", latency_ms=1.0)
    audit.record(run_id="r1", node="b", status="ok", latency_ms=2.0)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["run_id"] == "r1"
    assert "ts" in first
    assert len(audit.by_run("r1")) == 2
