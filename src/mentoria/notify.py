"""ChatOps: notificacao de resultados/alertas via webhook do Discord.

Saida observavel da automacao low-code (requisito 4.9). Resiliente: falhas de
rede nao derrubam o fluxo (retorna False). O webhook e um segredo e vem por
variavel de ambiente (DISCORD_WEBHOOK_URL).
"""

from __future__ import annotations

import httpx

MAX_CONTENT = 1900  # limite pratico de conteudo por mensagem no Discord


def post_to_discord(
    webhook_url: str,
    content: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 5.0,
) -> bool:
    """Posta uma mensagem no webhook do Discord. Retorna True em sucesso."""
    if not webhook_url:
        return False
    payload = {"content": content[:MAX_CONTENT]}
    own_client = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        response = client.post(webhook_url, json=payload)
        return response.status_code in (200, 204)
    except httpx.HTTPError:
        return False
    finally:
        if own_client:
            client.close()


def format_report_summary(report) -> str:
    """Monta um resumo curto do relatorio para ChatOps."""
    lines = [f"**MentorIA** - {report.request_type} (nivel {report.level})", report.summary]
    if report.flashcards:
        preview = ", ".join(card.term for card in report.flashcards[:5])
        lines.append(f"Flashcards: {preview}")
    if report.questions:
        lines.append(f"Perguntas geradas: {len(report.questions)}")
    return "\n".join(lines)
