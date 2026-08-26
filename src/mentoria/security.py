"""Guardrails de seguranca: deteccao de prompt injection e entrada nao confiavel.

O conteudo enviado pelo aluno (tema ou texto para leitura) e SEMPRE tratado
como dado, nunca como instrucao. Este modulo detecta tentativas comuns de
prompt injection / jailbreak para registro (auditoria) e para reforcar o
comportamento seguro: conteudo externo nao substitui as regras da aplicacao,
acoes nao autorizadas nao sao executadas e segredos nao sao revelados.

A defesa e defense-in-depth:
1. Os prompts de sistema instruem o modelo a tratar o conteudo como dado.
2. Os nodes so usam a mensagem como tema/texto -- nunca a executam como comando.
3. Este screening detecta e sinaliza padroes adversariais (nao confia no LLM).
"""

from __future__ import annotations

import re

# Padroes de injecao/jailbreak (portugues e ingles), case-insensitive.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(all\s+|previous\s+|prior\s+|above\s+)*instructions", re.I),
    ),
    ("ignore_instructions_pt", re.compile(r"ignore\s+(todas\s+as\s+|as\s+)?instru", re.I)),
    ("disregard", re.compile(r"disregard\s+(all|previous|the)", re.I)),
    (
        "reveal_prompt",
        re.compile(r"(reveal|show|print|repeat|expose|display)\s+.{0,30}(system\s+)?prompt", re.I),
    ),
    (
        "reveal_prompt_pt",
        re.compile(r"(revele|mostre|imprima|exiba)\s+.{0,30}(prompt|instru)", re.I),
    ),
    ("you_are_now", re.compile(r"you\s+are\s+now\b", re.I)),
    ("act_as", re.compile(r"\bact\s+as\b|\baja\s+como\b|finja\s+ser", re.I)),
    ("forget", re.compile(r"forget\s+(everything|all|previous)|esque\S*\s+tudo", re.I)),
    ("override", re.compile(r"\boverride\b|\bbypass\b|ignore\s+the\s+rules", re.I)),
    ("jailbreak", re.compile(r"\bjailbreak\b|\bDAN\b|developer\s+mode", re.I)),
    (
        "leak_secret",
        re.compile(r"(api[_\s-]?key|senha|password|token|secret|credential|env\s+var)", re.I),
    ),
    ("new_instructions", re.compile(r"(new|updated)\s+instructions|novas\s+instru", re.I)),
]


def detect_injection(text: str) -> list[str]:
    """Retorna os rotulos dos padroes adversariais encontrados no texto."""
    if not text:
        return []
    return [label for label, pattern in _INJECTION_PATTERNS if pattern.search(text)]


def is_suspicious(text: str) -> bool:
    """True se o texto contem sinais de prompt injection / entrada nao confiavel."""
    return bool(detect_injection(text))
