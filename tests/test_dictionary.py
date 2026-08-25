"""Testes da tool de dicionario (offline, com httpx.MockTransport)."""

from __future__ import annotations

import httpx
import pytest

from mentoria.tools.dictionary import (
    DictionaryClient,
    InvalidWordError,
    validate_word,
)

PAYLOAD = [
    {
        "word": "luggage",
        "phonetic": "/ˈlʌɡɪdʒ/",
        "phonetics": [{"text": "/ˈlʌɡɪdʒ/"}],
        "meanings": [
            {
                "partOfSpeech": "noun",
                "definitions": [{"definition": "bags", "example": "The luggage was heavy."}],
            }
        ],
    }
]


def _client(handler, **kwargs) -> DictionaryClient:
    return DictionaryClient(
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
        **kwargs,
    )


def test_validate_word_normaliza_e_valida():
    assert validate_word("  Luggage ") == "luggage"
    assert validate_word("boarding pass") == "boarding pass"
    for invalid in ["", "   ", "a" * 51, "hack; rm -rf", "café123"]:
        with pytest.raises(InvalidWordError):
            validate_word(invalid)


def test_lookup_sucesso():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    result = _client(handler).lookup("luggage")
    assert result is not None
    assert result.phonetic == "/ˈlʌɡɪdʒ/"
    assert result.part_of_speech == "noun"
    assert result.example == "The luggage was heavy."


def test_lookup_404_retorna_none():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"title": "No Definitions Found"})

    assert _client(handler).lookup("asdfqwer") is None


def test_retry_em_erro_5xx_e_sucesso():
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=PAYLOAD)

    result = _client(handler, max_retries=2).lookup("luggage")
    assert result is not None
    assert calls["n"] == 3


def test_esgota_retries_retorna_none():
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    assert _client(handler, max_retries=1).lookup("luggage") is None
    assert calls["n"] == 2


def test_timeout_faz_fallback():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout simulado")

    assert _client(handler, max_retries=1).lookup("luggage") is None


def test_lookup_invalida_levanta_erro():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    with pytest.raises(InvalidWordError):
        _client(handler).lookup("")
