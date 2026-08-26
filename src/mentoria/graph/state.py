"""Estado compartilhado tipado do grafo.

O estado e um TypedDict propagado entre os nodes. Campos escritos por
nodes que rodam em paralelo usam chaves distintas para evitar conflito
de escrita; `errors` usa um reducer aditivo por ser potencialmente
escrito por mais de um node no mesmo super-step.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from mentoria.schemas import (
    CEFRLevel,
    ComprehensionQuestion,
    Flashcard,
    MentorReport,
    RequestType,
)


class AgentState(TypedDict, total=False):
    """Estado do fluxo do agente."""

    # Entrada
    message: str
    level: CEFRLevel
    student_id: str | None
    run_id: str

    # Controle / decisoes
    intent: RequestType
    blocked: bool
    block_reason: str | None
    injection_detected: bool
    injection_flags: list[str]

    # Memoria (recuperada do perfil do aluno)
    known_terms: list[str]
    recent_themes: list[str]

    # Ramo flashcards
    theme: str | None
    vocab: list[dict[str, str]]  # [{term, translation}]
    examples: dict[str, str]  # term -> frase de exemplo (node paralelo A)
    definitions: dict[str, dict[str, Any]]  # term -> {phonetics, part_of_speech} (node paralelo B)
    flashcards: list[Flashcard]

    # Ramo leitura
    reading_text: str | None
    questions: list[ComprehensionQuestion]

    # Saida e diagnostico
    report: MentorReport
    errors: Annotated[list[str], operator.add]
