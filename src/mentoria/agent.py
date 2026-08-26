"""Entrypoint de alto nivel do agente MentorIA."""

from __future__ import annotations

import uuid
from time import perf_counter
from typing import TYPE_CHECKING

from mentoria.graph import build_graph
from mentoria.observability import get_logger
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
    audit=None,
) -> MentorReport:
    """Executa o fluxo do agente e retorna o relatorio estruturado.

    `model`, `dictionary_lookup`, `memory` e `audit` podem ser injetados
    (testes/offline); quando None, o cliente real (Groq/Gemini), a Free
    Dictionary API e a memoria SQLite padrao sao usados. Passar `audit`
    ativa os sinais de observabilidade (logs estruturados + auditoria).
    """
    graph = build_graph(
        model=model,
        dictionary_lookup=dictionary_lookup,
        memory=memory,
        checkpointer=checkpointer,
        audit=audit,
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

    if audit is not None:
        logger = get_logger()
        started = perf_counter()
        logger.info("run.started", run_id=run_id, level=str(request.level))
        final = graph.invoke(initial, config=config)
        logger.info(
            "run.completed",
            run_id=run_id,
            request_type=str(final["report"].request_type),
            latency_ms=round((perf_counter() - started) * 1000, 2),
        )
        return final["report"]

    final = graph.invoke(initial, config=config)
    return final["report"]
