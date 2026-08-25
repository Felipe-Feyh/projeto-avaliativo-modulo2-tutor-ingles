"""Observabilidade: logs estruturados + trilha de auditoria correlacionada.

Dois sinais correlacionados por `run_id` (requisito 4.6):
1. Logs estruturados (JSON) via structlog: um evento por node com nome,
   status e latencia.
2. Trilha de auditoria (audit trail): registro persistente por node com o
   mesmo `run_id`, permitindo reconstruir uma execucao ponta a ponta.

A instrumentacao dos nodes so e ativada quando um AuditLog e fornecido ao
grafo, mantendo execucoes de teste silenciosas por padrao.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import structlog

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configura o structlog para emitir logs estruturados em JSON."""
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        # False para permitir captura em testes (structlog.testing.capture_logs).
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str = "mentoria"):
    configure_logging()
    return structlog.get_logger(name)


class AuditLog:
    """Trilha de auditoria: mantem registros em memoria e, opcionalmente, em JSONL."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path
        self.records: list[dict[str, Any]] = []
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    def record(self, **fields: Any) -> None:
        entry = {"ts": datetime.now(UTC).isoformat(), **fields}
        self.records.append(entry)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def by_run(self, run_id: str) -> list[dict[str, Any]]:
        """Recupera os registros de uma execucao (para reconstrucao)."""
        return [r for r in self.records if r.get("run_id") == run_id]


def instrument(name: str, fn: Callable, audit: AuditLog) -> Callable:
    """Envolve um node para emitir os dois sinais (log estruturado + auditoria)."""
    logger = get_logger()

    def wrapped(state: dict) -> Any:
        run_id = state.get("run_id", "-")
        started = perf_counter()
        try:
            result = fn(state)
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1000, 2)
            logger.error(
                "node.failed",
                run_id=run_id,
                node=name,
                status="error",
                latency_ms=latency_ms,
                error=type(exc).__name__,
            )
            audit.record(
                run_id=run_id,
                node=name,
                status="error",
                latency_ms=latency_ms,
                error=type(exc).__name__,
            )
            raise
        latency_ms = round((perf_counter() - started) * 1000, 2)
        logger.info("node.completed", run_id=run_id, node=name, status="ok", latency_ms=latency_ms)
        audit.record(run_id=run_id, node=name, status="ok", latency_ms=latency_ms)
        return result

    return wrapped


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def monotonic_ms() -> float:
    return time.perf_counter() * 1000
