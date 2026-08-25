"""Testes do fluxo LangGraph usando um chat model fake (offline).

As respostas do modelo sao pre-programadas em JSON, na ordem em que os
nodes chamam o LLM. Isso permite exercitar todo o grafo sem credenciais.
"""

from __future__ import annotations

import json

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from mentoria.agent import run_agent
from mentoria.schemas import AgentRequest, CEFRLevel, RequestType
from mentoria.tools.dictionary import DictionaryResult


def _fake(responses: list[dict]) -> FakeListChatModel:
    return FakeListChatModel(responses=[json.dumps(r) for r in responses])


def _fake_lookup(word: str) -> DictionaryResult | None:
    """Lookup offline deterministico para os testes do grafo."""
    table = {
        "boarding pass": DictionaryResult(
            word="boarding pass", phonetic=None, part_of_speech="noun"
        ),
        "luggage": DictionaryResult(word="luggage", phonetic="/ˈlʌɡɪdʒ/", part_of_speech="noun"),
    }
    return table.get(word)


def test_fluxo_flashcards():
    model = _fake(
        [
            {"intent": "flashcards", "theme": "travel"},
            {
                "vocab": [
                    {"term": "boarding pass", "translation": "cartao de embarque"},
                    {"term": "luggage", "translation": "bagagem"},
                ]
            },
            {
                "examples": {
                    "boarding pass": "Please show your boarding pass at the gate.",
                    "luggage": "I lost my luggage at the airport.",
                }
            },
        ]
    )
    report = run_agent(
        AgentRequest(message="quero aprender sobre viagens", level=CEFRLevel.B1),
        model=model,
        dictionary_lookup=_fake_lookup,
    )

    assert report.request_type == RequestType.FLASHCARDS
    assert report.theme == "travel"
    assert len(report.flashcards) == 2
    terms = {c.term for c in report.flashcards}
    assert terms == {"boarding pass", "luggage"}
    card = next(c for c in report.flashcards if c.term == "luggage")
    assert card.translation == "bagagem"
    assert "luggage" in card.example
    # enriquecido pela tool (lookup injetado)
    assert card.phonetics == "/ˈlʌɡɪdʒ/"
    assert card.part_of_speech == "noun"


def test_fluxo_leitura():
    model = _fake(
        [
            {"intent": "reading", "reading_text": "Python is a popular programming language."},
            {
                "questions": [
                    {
                        "question": "What is Python?",
                        "answer": "A programming language",
                        "explanation": "Diz no texto.",
                    },
                    {
                        "question": "Is it popular?",
                        "answer": "Yes",
                        "explanation": "O texto afirma isso.",
                    },
                ]
            },
        ]
    )
    report = run_agent(
        AgentRequest(message="Python is a popular programming language.", level=CEFRLevel.B1),
        model=model,
    )

    assert report.request_type == RequestType.READING
    assert len(report.questions) == 2
    assert report.questions[0].question == "What is Python?"


def test_entrada_vazia_e_bloqueada():
    model = _fake([{"intent": "unknown"}])
    report = run_agent(AgentRequest(message="   ", level=CEFRLevel.A2), model=model)

    assert report.request_type == RequestType.UNKNOWN
    assert "bloqueada" in report.summary.lower()


def test_intencao_desconhecida():
    model = _fake([{"intent": "unknown"}])
    report = run_agent(AgentRequest(message="asdf 123 ??", level=CEFRLevel.B1), model=model)

    assert report.request_type == RequestType.UNKNOWN
    assert report.flashcards == []
    assert report.questions == []
