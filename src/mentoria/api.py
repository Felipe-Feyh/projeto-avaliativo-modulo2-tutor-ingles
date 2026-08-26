"""API HTTP local (FastAPI) do MentorIA.

Serve como ponto de integracao para a automacao low-code (n8n/Make): a
ferramenta visual dispara um webhook -> chama esta API (a logica permanece na
aplicacao) -> a saida pode ser notificada via ChatOps (Discord).

Seguranca: se MENTORIA_API_KEY estiver definido, exige o header X-API-Key.
Se nao estiver definido, a API fica aberta (apenas uso local/dev) e registra
um aviso. Documentado no README.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException

from mentoria.agent import run_agent
from mentoria.config import get_settings
from mentoria.notify import format_report_summary, post_to_discord
from mentoria.observability import AuditLog, get_logger
from mentoria.schemas import AgentRequest


def get_overrides() -> dict[str, Any]:
    """Injecao de dependencias (model/lookup/memory) para testes. Vazio = real."""
    return {}


def _check_auth(x_api_key: str | None) -> None:
    settings = get_settings()
    if settings.mentoria_api_key and x_api_key != settings.mentoria_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key invalido ou ausente.")


def create_app() -> FastAPI:
    app = FastAPI(title="MentorIA API", version="0.1.0")
    logger = get_logger()
    if not get_settings().mentoria_api_key:
        logger.warning("api.auth_disabled", detail="MENTORIA_API_KEY nao definido; API aberta.")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "mentoria"}

    @app.post("/ask")
    def ask(
        request: AgentRequest,
        overrides: dict = Depends(get_overrides),
        x_api_key: str | None = Header(default=None),
        notify: bool = False,
    ) -> dict:
        """Executa o agente. `notify=true` envia um resumo ao Discord (ChatOps)."""
        _check_auth(x_api_key)
        audit = overrides.pop("audit", None) or AuditLog(path="logs/audit.jsonl")
        report = run_agent(request, audit=audit, **overrides)

        if notify:
            settings = get_settings()
            if settings.discord_webhook_url:
                sent = post_to_discord(settings.discord_webhook_url, format_report_summary(report))
                logger.info("chatops.discord", sent=sent, run_id=getattr(report, "run_id", None))

        return report.model_dump()

    return app


app = create_app()
