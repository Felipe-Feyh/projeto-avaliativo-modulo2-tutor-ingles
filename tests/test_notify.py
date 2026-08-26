"""Testes do notificador ChatOps (Discord)."""

from __future__ import annotations

import httpx

from mentoria.notify import format_report_summary, post_to_discord
from mentoria.schemas import CEFRLevel, Flashcard, MentorReport, RequestType


def test_post_sucesso():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert post_to_discord("https://discord.test/webhook", "ola", client=client) is True


def test_post_url_vazia_retorna_false():
    assert post_to_discord("", "ola") is False


def test_post_falha_de_rede_retorna_false():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert post_to_discord("https://discord.test/webhook", "ola", client=client) is False


def test_format_report_summary():
    report = MentorReport(
        request_type=RequestType.FLASHCARDS,
        level=CEFRLevel.B1,
        theme="travel",
        flashcards=[Flashcard(term="luggage", translation="bagagem")],
        summary="1 flashcards gerados.",
    )
    summary = format_report_summary(report)
    assert "MentorIA" in summary
    assert "luggage" in summary
