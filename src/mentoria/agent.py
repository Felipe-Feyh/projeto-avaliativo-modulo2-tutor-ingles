"""Entrypoint de alto nivel do agente MentorIA."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from mentoria.graph import build_graph
from mentoria.schemas import AgentRequest, MentorReport

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def run_agent(request: AgentRequest, *, model: BaseChatModel | None = None) -> MentorReport:
    """Executa o fluxo do agente e retorna o relatorio estruturado.

    `model` pode ser injetado (testes/offline); quando None, o cliente real
    (Groq/Gemini) e construido a partir das variaveis de ambiente.
    """
    graph = build_graph(model=model)
    initial: dict = {
        "message": request.message,
        "level": request.level,
        "student_id": request.student_id,
        "run_id": uuid.uuid4().hex,
        "errors": [],
    }
    final = graph.invoke(initial)
    return final["report"]
