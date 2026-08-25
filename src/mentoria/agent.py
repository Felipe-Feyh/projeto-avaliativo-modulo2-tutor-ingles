"""Entrypoint de alto nivel do agente MentorIA."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from mentoria.graph import build_graph
from mentoria.schemas import AgentRequest, MentorReport

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def run_agent(
    request: AgentRequest,
    *,
    model: BaseChatModel | None = None,
    dictionary_lookup=None,
    memory=None,
    checkpointer=None,
) -> MentorReport:
    """Executa o fluxo do agente e retorna o relatorio estruturado.

    `model`, `dictionary_lookup` e `memory` podem ser injetados
    (testes/offline); quando None, o cliente real (Groq/Gemini), a Free
    Dictionary API e a memoria SQLite padrao sao usados.
    """
    graph = build_graph(
        model=model,
        dictionary_lookup=dictionary_lookup,
        memory=memory,
        checkpointer=checkpointer,
    )
    run_id = uuid.uuid4().hex
    initial: dict = {
        "message": request.message,
        "level": request.level,
        "student_id": request.student_id,
        "run_id": run_id,
        "errors": [],
    }
    config = None
    if checkpointer is not None:
        # thread por aluno (ou por execucao, se anonimo) para o checkpointer
        thread_id = request.student_id or run_id
        config = {"configurable": {"thread_id": thread_id}}
    final = graph.invoke(initial, config=config)
    return final["report"]
