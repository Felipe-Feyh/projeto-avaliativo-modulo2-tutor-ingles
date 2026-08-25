"""CLI do MentorIA.

Uso:
    python -m mentoria "termos usados em entrevistas de emprego" --level B2
    python -m mentoria "Python is a programming language. It is widely used..." --level B1
"""

from __future__ import annotations

import argparse
import sys

from mentoria.agent import run_agent
from mentoria.observability import AuditLog
from mentoria.schemas import AgentRequest, CEFRLevel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mentoria", description="MentorIA - tutor de ingles")
    parser.add_argument("message", help="Tema (flashcards) ou texto em ingles (leitura)")
    parser.add_argument(
        "--level",
        default="B1",
        choices=[lvl.value for lvl in CEFRLevel],
        help="Nivel CEFR (padrao: B1)",
    )
    parser.add_argument("--student-id", default=None, help="Identificador opcional do aluno")
    parser.add_argument(
        "--no-observability",
        action="store_true",
        help="Desativa logs estruturados e trilha de auditoria",
    )
    args = parser.parse_args(argv)

    request = AgentRequest(
        message=args.message,
        level=CEFRLevel(args.level),
        student_id=args.student_id,
    )
    audit = None if args.no_observability else AuditLog(path="logs/audit.jsonl")
    report = run_agent(request, audit=audit)
    sys.stdout.write(report.model_dump_json(indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
