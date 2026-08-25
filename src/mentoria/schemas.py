"""Schemas Pydantic da aplicacao.

Sao a fronteira de contrato do agente: a entrada do aluno e a saida
estruturada (relatorio) que a aplicacao produz. Manter os tipos aqui
facilita validacao, serializacao JSON e testes.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RequestType(StrEnum):
    """Intencao classificada da solicitacao do aluno."""

    FLASHCARDS = "flashcards"
    READING = "reading"
    UNKNOWN = "unknown"


class CEFRLevel(StrEnum):
    """Nivel de proficiencia (Common European Framework)."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class AgentRequest(BaseModel):
    """Entrada do aluno para o agente."""

    message: str = Field(..., description="Texto livre do aluno (tema ou texto para leitura).")
    level: CEFRLevel = Field(default=CEFRLevel.B1)
    student_id: str | None = Field(default=None, description="Identificador opcional do aluno.")


class Flashcard(BaseModel):
    """Cartao de vocabulario."""

    term: str
    translation: str = Field(..., description="Traducao em portugues.")
    example: str = Field(default="", description="Frase de exemplo em ingles.")
    phonetics: str | None = Field(default=None, description="Transcricao fonetica (IPA).")
    part_of_speech: str | None = Field(default=None, description="Classe gramatical.")


class ComprehensionQuestion(BaseModel):
    """Pergunta de compreensao de leitura."""

    question: str
    answer: str
    explanation: str | None = Field(default=None)


class MentorReport(BaseModel):
    """Saida estruturada do agente."""

    request_type: RequestType
    level: CEFRLevel
    theme: str | None = None
    reading_text: str | None = None
    flashcards: list[Flashcard] = Field(default_factory=list)
    questions: list[ComprehensionQuestion] = Field(default_factory=list)
    summary: str = ""
    notes: list[str] = Field(default_factory=list)
