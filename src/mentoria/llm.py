"""Cliente de LLM com provedor primario (Groq) e fallback (Gemini).

O modelo e configurado por variavel de ambiente (requisito 4.10). Quando
ambos os provedores tem credenciais, usa-se `with_fallbacks` para que uma
falha do primario acione o secundario automaticamente (resiliencia).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from mentoria.config import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class LLMConfigError(RuntimeError):
    """Nenhum provedor de LLM foi configurado com credenciais."""


def _build_groq(settings: Settings) -> BaseChatModel:
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.3,
    )


def _build_gemini(settings: Settings) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.3,
    )


def get_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Constroi o chat model conforme as credenciais disponiveis.

    Ordem: provedor primario definido em LLM_PROVIDER; o outro (se tiver
    chave) e registrado como fallback.
    """
    settings = settings or get_settings()

    builders = {
        "groq": (_build_groq, settings.has_groq()),
        "gemini": (_build_gemini, settings.has_gemini()),
    }
    primary_name = settings.llm_provider if settings.llm_provider in builders else "groq"

    primary_builder, primary_ok = builders[primary_name]
    if not primary_ok:
        # cai para qualquer provedor disponivel
        available = [name for name, (_, ok) in builders.items() if ok]
        if not available:
            raise LLMConfigError(
                "Nenhuma credencial de LLM configurada. Defina GROQ_API_KEY ou GEMINI_API_KEY."
            )
        primary_name = available[0]
        primary_builder, _ = builders[primary_name]

    model = primary_builder(settings)

    fallbacks = [
        builder(settings) for name, (builder, ok) in builders.items() if ok and name != primary_name
    ]
    if fallbacks:
        model = model.with_fallbacks(fallbacks)
    return model


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_json_block(text: str) -> dict:
    """Extrai e faz parse de um bloco JSON da resposta do modelo.

    Tolera cercas de codigo markdown e texto ao redor do objeto.
    """
    text = text.strip()
    match = _JSON_FENCE.search(text)
    if match:
        text = match.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)
