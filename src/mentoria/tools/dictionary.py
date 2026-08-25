"""Tool de integracao com a Free Dictionary API.

Fonte: https://dictionaryapi.dev (endpoint publico, sem chave).
Enriquece os flashcards com fonetica (IPA), classe gramatical e um
exemplo real de uso.

Requisito 4.3 (tool com validacao e tratamento de falhas):
- Validacao de entrada (palavra) antes de qualquer chamada externa.
- Schema de saida tipado (DictionaryResult).
- Resiliencia: timeout, retry limitado com backoff exponencial e
  fallback (retorna None quando a palavra nao e encontrada ou apos
  esgotar as tentativas), sem derrubar o fluxo do agente.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import quote

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel

DEFAULT_BASE_URL = "https://api.dictionaryapi.dev"
_WORD_RE = re.compile(r"^[a-z][a-z '\-]{0,49}$")


class InvalidWordError(ValueError):
    """A palavra informada nao passou na validacao de entrada."""


class DictionaryResult(BaseModel):
    """Resultado tipado de uma consulta ao dicionario."""

    word: str
    phonetic: str | None = None
    part_of_speech: str | None = None
    example: str | None = None


def validate_word(word: str) -> str:
    """Valida e normaliza a palavra. Levanta InvalidWordError se invalida."""
    if not isinstance(word, str):
        raise InvalidWordError("A palavra deve ser uma string.")
    normalized = word.strip().lower()
    if not normalized:
        raise InvalidWordError("Palavra vazia.")
    if len(normalized) > 50:
        raise InvalidWordError("Palavra excede 50 caracteres.")
    if not _WORD_RE.match(normalized):
        raise InvalidWordError(f"Palavra com caracteres invalidos: {word!r}")
    return normalized


def _parse_payload(word: str, payload: object) -> DictionaryResult | None:
    if not isinstance(payload, list) or not payload:
        return None
    entry = payload[0]
    if not isinstance(entry, dict):
        return None

    phonetic = entry.get("phonetic")
    if not phonetic:
        for ph in entry.get("phonetics", []):
            if isinstance(ph, dict) and ph.get("text"):
                phonetic = ph["text"]
                break

    part_of_speech = None
    example = None
    meanings = entry.get("meanings", [])
    if meanings and isinstance(meanings[0], dict):
        part_of_speech = meanings[0].get("partOfSpeech")
        for definition in meanings[0].get("definitions", []):
            if isinstance(definition, dict) and definition.get("example"):
                example = definition["example"]
                break

    return DictionaryResult(
        word=word,
        phonetic=phonetic or None,
        part_of_speech=part_of_speech,
        example=example,
    )


class DictionaryClient:
    """Cliente resiliente para a Free Dictionary API."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 5.0,
        max_retries: int = 2,
        backoff: float = 0.5,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._max_retries = max_retries
        self._backoff = backoff
        self._sleep = sleep

    def lookup(self, word: str) -> DictionaryResult | None:
        """Consulta a palavra. Retorna None em caso de nao encontrada/falha."""
        normalized = validate_word(word)
        path = f"/api/v2/entries/en/{quote(normalized)}"

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(path)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt < self._max_retries:
                    self._sleep(self._backoff * (2**attempt))
                    continue
                return None  # fallback apos esgotar tentativas

            if response.status_code == 404:
                return None  # palavra nao encontrada -> fallback silencioso
            # 429 (rate limit) e 5xx sao transitorios -> retry com backoff.
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self._max_retries:
                    self._sleep(self._backoff * (2**attempt))
                    continue
                return None
            if response.status_code != 200:
                return None

            try:
                return _parse_payload(normalized, response.json())
            except ValueError:
                return None
        return None

    def close(self) -> None:
        self._client.close()


_default_client: DictionaryClient | None = None


def _get_default_client() -> DictionaryClient:
    global _default_client
    if _default_client is None:
        _default_client = DictionaryClient()
    return _default_client


def lookup_word(word: str) -> DictionaryResult | None:
    """Consulta a palavra usando o cliente padrao. Entrada invalida -> None."""
    try:
        return _get_default_client().lookup(word)
    except InvalidWordError:
        return None


@tool
def dictionary_lookup(word: str) -> dict:
    """Consulta fonetica (IPA), classe gramatical e exemplo de uma palavra em ingles."""
    result = lookup_word(word)
    if result is None:
        return {"word": word, "phonetic": None, "part_of_speech": None, "example": None}
    return result.model_dump()
