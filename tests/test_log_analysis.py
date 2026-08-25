"""Testes do analisador de logs (DevOps inteligente)."""

from __future__ import annotations

from mentoria.devops.log_analysis import analyze, load_audit


def _rec(run_id, node, status="ok", latency=100.0):
    return {"run_id": run_id, "node": node, "status": status, "latency_ms": latency}


def test_metricas_por_node():
    records = [
        _rec("r1", "classify_intent", latency=400),
        _rec("r1", "enrich_definitions", "error", 5),
        _rec("r2", "classify_intent", latency=500),
        _rec("r2", "enrich_definitions", latency=200),
    ]
    report = analyze(records)
    assert report.total_events == 4
    enrich = next(n for n in report.nodes if n.node == "enrich_definitions")
    assert enrich.calls == 2
    assert enrich.errors == 1
    assert enrich.error_rate == 0.5


def test_detecta_erro_recorrente():
    records = [_rec(f"r{i}", "enrich_definitions", "error", 5) for i in range(4)]
    records += [_rec("r9", "enrich_definitions", "ok", 5)]
    report = analyze(records)
    kinds = {a.kind for a in report.anomalies if a.node == "enrich_definitions"}
    assert "erro_recorrente" in kinds


def test_detecta_latencia_alta():
    records = [
        _rec("r1", "a", latency=100),
        _rec("r2", "a", latency=100),
        _rec("r3", "spike", latency=5000),
    ]
    report = analyze(records)
    kinds = {(a.node, a.kind) for a in report.anomalies}
    assert ("spike", "latencia_alta") in kinds


def test_risco_alto_quando_tendencia_sobe():
    # Primeira metade sem erros, segunda metade com muitos erros.
    records = [_rec(f"r{i}", "n", "ok", 10) for i in range(5)]
    records += [_rec(f"r{i}", "n", "error", 10) for i in range(5, 10)]
    report = analyze(records)
    assert report.risk.level == "alto"
    assert report.risk.probability > 0.30


def test_risco_baixo_quando_saudavel():
    records = [_rec(f"r{i}", "n", "ok", 10) for i in range(10)]
    report = analyze(records)
    assert report.risk.level == "baixo"
    assert report.anomalies == []


def test_load_audit_do_arquivo_de_exemplo():
    records = load_audit("docs/evidencias/sample-audit.jsonl")
    report = analyze(records)
    assert report.total_events == 25
    assert report.risk.level == "alto"
    assert any(a.kind == "erro_recorrente" for a in report.anomalies)
    assert any(a.kind == "latencia_alta" for a in report.anomalies)
