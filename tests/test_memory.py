"""Testes de memoria persistente (SQLite) e checkpointer LangGraph."""

from __future__ import annotations

import json
import sqlite3

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.sqlite import SqliteSaver

from mentoria.agent import run_agent
from mentoria.graph import build_graph
from mentoria.memory import StudentMemory
from mentoria.schemas import AgentRequest, CEFRLevel, RequestType
from mentoria.tools.dictionary import DictionaryResult


def _fake_model() -> FakeListChatModel:
    responses = [
        {"intent": "flashcards", "theme": "travel"},
        {
            "vocab": [
                {"term": "luggage", "translation": "bagagem"},
                {"term": "passport", "translation": "passaporte"},
            ]
        },
        {
            "examples": {
                "luggage": "My luggage is heavy.",
                "passport": "Show your passport, please.",
            }
        },
    ]
    return FakeListChatModel(responses=[json.dumps(r) for r in responses])


def _fake_lookup(word: str) -> DictionaryResult | None:
    return DictionaryResult(word=word, phonetic=None, part_of_speech="noun")


def test_studentmemory_registra_e_recupera():
    mem = StudentMemory(":memory:")
    mem.record_session("s1", "flashcards", "travel", "r1")
    mem.record_terms("s1", ["luggage", "passport"])
    mem.record_terms("s1", ["luggage"])  # incrementa times_seen

    profile = mem.get_profile("s1")
    assert profile["recent_themes"] == ["travel"]
    assert profile["sessions"] == 1
    assert "luggage" in profile["known_terms"]
    # luggage foi visto 2x -> aparece antes de passport
    assert profile["known_terms"][0] == "luggage"


def test_agente_persiste_sessao_e_termos():
    mem = StudentMemory(":memory:")
    run_agent(
        AgentRequest(message="quero aprender viagens", level=CEFRLevel.B1, student_id="aluno42"),
        model=_fake_model(),
        dictionary_lookup=_fake_lookup,
        memory=mem,
    )
    profile = mem.get_profile("aluno42")
    assert profile["sessions"] == 1
    assert profile["recent_themes"] == ["travel"]
    assert set(profile["known_terms"]) == {"luggage", "passport"}


def test_agente_anonimo_nao_persiste():
    mem = StudentMemory(":memory:")
    run_agent(
        AgentRequest(message="quero aprender viagens", level=CEFRLevel.B1),
        model=_fake_model(),
        dictionary_lookup=_fake_lookup,
        memory=mem,
    )
    # sem student_id, nada e gravado
    assert mem.get_profile("aluno42")["sessions"] == 0


def test_checkpointer_sqlite_salva_estado():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()

    graph = build_graph(
        model=_fake_model(),
        dictionary_lookup=_fake_lookup,
        memory=StudentMemory(":memory:"),
        checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "aluno42"}}
    graph.invoke(
        {
            "message": "quero aprender viagens",
            "level": CEFRLevel.B1,
            "student_id": "aluno42",
            "run_id": "run-1",
            "errors": [],
        },
        config=config,
    )

    snapshot = graph.get_state(config)
    assert snapshot.values.get("report") is not None
    assert snapshot.values["report"].request_type == RequestType.FLASHCARDS
