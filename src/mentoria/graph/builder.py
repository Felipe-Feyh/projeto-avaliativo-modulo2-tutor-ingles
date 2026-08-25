"""Construcao do grafo LangGraph do MentorIA.

Topologia (DAG, sem loops -> terminacao garantida):

    START -> validate_input
      validate_input --(bloqueado?)--> build_report
      validate_input --(ok)--> screen_input -> load_memory -> classify_intent
        classify_intent --(flashcards)--> generate_vocabulary
        classify_intent --(reading)----> generate_questions
        classify_intent --(unknown)----> build_report

      # fan-out paralelo + join
      generate_vocabulary -> generate_examples  -> assemble_flashcards
      generate_vocabulary -> enrich_definitions -> assemble_flashcards
      assemble_flashcards -> build_report
      generate_questions  -> build_report
      build_report -> persist_memory -> END
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from mentoria.graph import nodes
from mentoria.graph.state import AgentState
from mentoria.llm import get_chat_model
from mentoria.observability import instrument
from mentoria.schemas import RequestType

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def _route_after_validate(state: AgentState) -> str:
    return "blocked" if state.get("blocked") else "ok"


def _route_by_intent(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == RequestType.FLASHCARDS:
        return "flashcards"
    if intent == RequestType.READING:
        return "reading"
    return "unknown"


def build_graph(
    model: BaseChatModel | None = None,
    dictionary_lookup=None,
    memory=None,
    checkpointer=None,
    audit=None,
):
    """Monta e compila o grafo. `model`, `dictionary_lookup`, `memory` e
    `audit` podem ser injetados (testes/offline). Quando `audit` e fornecido,
    cada node e instrumentado (logs estruturados + trilha de auditoria)."""
    if model is None:
        model = get_chat_model()

    graph = StateGraph(AgentState)

    def _add(name: str, fn) -> None:
        graph.add_node(name, instrument(name, fn, audit) if audit is not None else fn)

    # Nodes deterministicos
    _add("validate_input", nodes.validate_input)
    _add("screen_input", nodes.screen_input)
    if memory is not None:
        _add("load_memory", partial(nodes.load_memory, memory=memory))
        _add("persist_memory", partial(nodes.persist_memory, memory=memory))
    else:
        _add("load_memory", nodes.load_memory)
        _add("persist_memory", nodes.persist_memory)
    if dictionary_lookup is not None:
        _add("enrich_definitions", partial(nodes.enrich_definitions, lookup=dictionary_lookup))
    else:
        _add("enrich_definitions", nodes.enrich_definitions)
    _add("assemble_flashcards", nodes.assemble_flashcards)
    _add("build_report", nodes.build_report)

    # Nodes com LLM (modelo injetado via partial)
    _add("classify_intent", partial(nodes.classify_intent, model=model))
    _add("generate_vocabulary", partial(nodes.generate_vocabulary, model=model))
    _add("generate_examples", partial(nodes.generate_examples, model=model))
    _add("generate_questions", partial(nodes.generate_questions, model=model))

    # Fluxo
    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges(
        "validate_input",
        _route_after_validate,
        {"blocked": "build_report", "ok": "screen_input"},
    )
    graph.add_edge("screen_input", "load_memory")
    graph.add_edge("load_memory", "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        _route_by_intent,
        {
            "flashcards": "generate_vocabulary",
            "reading": "generate_questions",
            "unknown": "build_report",
        },
    )

    # Paralelizacao: vocabulary faz fan-out para dois nodes que rodam no
    # mesmo super-step e convergem em assemble_flashcards (join).
    graph.add_edge("generate_vocabulary", "generate_examples")
    graph.add_edge("generate_vocabulary", "enrich_definitions")
    graph.add_edge("generate_examples", "assemble_flashcards")
    graph.add_edge("enrich_definitions", "assemble_flashcards")

    graph.add_edge("assemble_flashcards", "build_report")
    graph.add_edge("generate_questions", "build_report")
    graph.add_edge("build_report", "persist_memory")
    graph.add_edge("persist_memory", END)

    return graph.compile(checkpointer=checkpointer)
