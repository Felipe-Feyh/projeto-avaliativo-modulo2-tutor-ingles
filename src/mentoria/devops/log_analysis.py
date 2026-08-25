"""Analise de logs, deteccao de anomalias e estimativa de risco de falha.

Consome a trilha de auditoria (JSONL produzido por observability.AuditLog),
agrega metricas por node/etapa, detecta anomalias (erro recorrente e latencia
alta) e produz uma estimativa simples de risco de falha (requisito 4.8).

As regras sao deterministicas e explicaveis (thresholds documentados), o que
permite justificar cada conclusao e reproduzir a analise.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Thresholds (documentados e ajustaveis)
ERROR_RATE_THRESHOLD = 0.20  # >20% de erros no node => anomalia de erro recorrente
LATENCY_FACTOR = 3.0  # latencia max > FATOR * mediana global => anomalia de latencia
LATENCY_FLOOR_MS = 50.0  # ignora ruido abaixo deste piso


class NodeStats(BaseModel):
    node: str
    calls: int
    errors: int
    error_rate: float
    latency_avg_ms: float
    latency_max_ms: float


class Anomaly(BaseModel):
    node: str
    kind: str  # "erro_recorrente" | "latencia_alta"
    detail: str


class RiskEstimate(BaseModel):
    probability: float = Field(..., ge=0.0, le=1.0)
    level: str  # "baixo" | "medio" | "alto"
    rationale: str


class AnalysisReport(BaseModel):
    total_events: int
    overall_error_rate: float
    nodes: list[NodeStats]
    anomalies: list[Anomaly]
    risk: RiskEstimate


def load_audit(path: str | Path) -> list[dict[str, Any]]:
    """Carrega registros de auditoria de um arquivo JSONL."""
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _node_stats(records: list[dict[str, Any]]) -> list[NodeStats]:
    by_node: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        by_node.setdefault(rec.get("node", "?"), []).append(rec)

    stats: list[NodeStats] = []
    for node, recs in sorted(by_node.items()):
        latencies = [float(r.get("latency_ms", 0.0)) for r in recs]
        errors = sum(1 for r in recs if r.get("status") == "error")
        stats.append(
            NodeStats(
                node=node,
                calls=len(recs),
                errors=errors,
                error_rate=round(errors / len(recs), 3),
                latency_avg_ms=round(statistics.fmean(latencies), 2) if latencies else 0.0,
                latency_max_ms=round(max(latencies), 2) if latencies else 0.0,
            )
        )
    return stats


def _detect_anomalies(records: list[dict[str, Any]], nodes: list[NodeStats]) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    all_latencies = [float(r.get("latency_ms", 0.0)) for r in records]
    median_latency = statistics.median(all_latencies) if all_latencies else 0.0
    latency_limit = max(LATENCY_FLOOR_MS, median_latency * LATENCY_FACTOR)

    for stat in nodes:
        if stat.error_rate > ERROR_RATE_THRESHOLD:
            anomalies.append(
                Anomaly(
                    node=stat.node,
                    kind="erro_recorrente",
                    detail=(
                        f"taxa de erro {stat.error_rate:.0%} "
                        f"({stat.errors}/{stat.calls}) acima do limite de "
                        f"{ERROR_RATE_THRESHOLD:.0%}"
                    ),
                )
            )
        if stat.latency_max_ms > latency_limit:
            anomalies.append(
                Anomaly(
                    node=stat.node,
                    kind="latencia_alta",
                    detail=(
                        f"latencia max {stat.latency_max_ms:.0f}ms > "
                        f"{latency_limit:.0f}ms (mediana global {median_latency:.0f}ms x "
                        f"{LATENCY_FACTOR:g})"
                    ),
                )
            )
    return anomalies


def _estimate_risk(records: list[dict[str, Any]], overall_error_rate: float) -> RiskEstimate:
    """Estimativa simples: taxa de erro global + tendencia (2a metade - 1a metade)."""
    half = len(records) // 2 or 1
    first, second = records[:half], records[half:]

    def rate(recs: list[dict[str, Any]]) -> float:
        return (sum(1 for r in recs if r.get("status") == "error") / len(recs)) if recs else 0.0

    trend = rate(second) - rate(first)
    probability = round(min(1.0, max(0.0, overall_error_rate + max(0.0, trend))), 3)

    if probability < 0.10:
        level = "baixo"
    elif probability < 0.30:
        level = "medio"
    else:
        level = "alto"

    direction = "subindo" if trend > 0 else ("estavel" if trend == 0 else "caindo")
    rationale = (
        f"erro global {overall_error_rate:.0%}; tendencia {direction} "
        f"(1a metade {rate(first):.0%} -> 2a metade {rate(second):.0%})"
    )
    return RiskEstimate(probability=probability, level=level, rationale=rationale)


def analyze(records: list[dict[str, Any]]) -> AnalysisReport:
    """Produz o relatorio completo de analise a partir dos registros."""
    total = len(records)
    errors = sum(1 for r in records if r.get("status") == "error")
    overall_error_rate = round(errors / total, 3) if total else 0.0
    nodes = _node_stats(records)
    anomalies = _detect_anomalies(records, nodes)
    risk = _estimate_risk(records, overall_error_rate)
    return AnalysisReport(
        total_events=total,
        overall_error_rate=overall_error_rate,
        nodes=nodes,
        anomalies=anomalies,
        risk=risk,
    )


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        sys.stderr.write("uso: python -m mentoria.devops.log_analysis <audit.jsonl>\n")
        return 2
    report = analyze(load_audit(argv[0]))
    sys.stdout.write(report.model_dump_json(indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
