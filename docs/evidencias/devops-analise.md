# DevOps inteligente: análise de logs, anomalias e risco

Evidências do requisito 4.8 / critério 13: análise de logs de múltiplas etapas do
pipeline, detecção e explicação de anomalias, e estimativa simples de risco de falha.

## 1. Pipeline (CI) e logs por etapa

O workflow `.github/workflows/ci.yml` executa **lint → testes → build**. Trechos reais
de uma execução no GitHub Actions (run de 25/08/2026):

| Etapa | Log real | Leitura (IA) |
|-------|----------|--------------|
| Lint (ruff) | `All checks passed!` | Sem violações de estilo/lint; código dentro do padrão. |
| Testes (pytest) | `28 passed in 0.57s` | Suíte 100% verde; baixa latência de execução (~0,57s) indica suíte enxuta e rápida. |
| Build | `Successfully built mentoria-0.1.0.tar.gz and mentoria-0.1.0-py3-none-any.whl` | Empacotamento (sdist + wheel) concluído; artefato distribuível gerado. |

## 2. Anomalias detectadas e explicadas

### 2.1. Anomalia real no CI — deprecação do Node 20

Log recorrente em várias etapas (checkout, setup-python):

```
Node 20 is being deprecated. This workflow is running with Node 24 by default...
https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
```

- **Explicação:** as actions `actions/checkout@v4` e `actions/setup-python@v5` ainda
  declaram runtime Node 20, que o runner passou a forçar para Node 24.
- **Severidade:** baixa (aviso, não quebra o build).
- **Ação recomendada:** acompanhar novas majors das actions; não requer mudança imediata.

### 2.2. Anomalia na aplicação — falha recorrente da tool + latência alta

Analisando a trilha de auditoria da aplicação (`docs/evidencias/sample-audit.jsonl`,
dados **simulados e documentados** representando um período de instabilidade), o
analisador `mentoria.devops.log_analysis` detectou:

```json
"anomalies": [
  {"node": "enrich_definitions", "kind": "erro_recorrente",
   "detail": "taxa de erro 60% (3/5) acima do limite de 20%"},
  {"node": "generate_vocabulary", "kind": "latencia_alta",
   "detail": "latencia max 1500ms > 1200ms (mediana global 400ms x 3)"}
]
```

- **Erro recorrente em `enrich_definitions`:** 60% das chamadas falharam. É coerente com
  o comportamento **real** observado durante o desenvolvimento da tool, quando a Free
  Dictionary API retornou `502`/instabilidade (ver PR #15 e `docs/qa/code-review-ia.md`).
- **Latência alta em `generate_vocabulary`:** pico de 1500ms (3x acima da mediana global),
  típico de degradação/cauda longa do provedor de LLM.

## 3. Estimativa de risco de falha

Saída do analisador para o mesmo conjunto:

```json
"risk": {"probability": 0.351, "level": "alto",
         "rationale": "erro global 12%; tendencia subindo (1a metade 0% -> 2a metade 23%)"}
```

- **Método (determinístico e explicável):** `risco = taxa_de_erro_global + max(0, tendência)`,
  onde a tendência compara a taxa de erro da 2ª metade contra a 1ª metade da série temporal.
- **Conclusão:** risco **alto** (0,351). Embora o erro global seja 12%, a **tendência de
  subida** (0% → 23%) indica degradação em curso, concentrada na dependência externa
  (`enrich_definitions`). Isso **justifica** priorizar a resiliência dessa integração —
  exatamente o que motivou o fix de retry em `429`/`5xx` (ver `docs/qa/code-review-ia.md`).

## 4. Reprodução

```bash
# Analisar a trilha de auditoria (dados de exemplo)
python -m mentoria.devops.log_analysis docs/evidencias/sample-audit.jsonl

# Gerar uma trilha real executando o agente com observabilidade (requer chaves):
python -m mentoria "termos de entrevista" --level B2   # grava logs/audit.jsonl
python -m mentoria.devops.log_analysis logs/audit.jsonl
```

O formato de cada linha da auditoria: `{ts, run_id, node, status, latency_ms, [error]}`.
