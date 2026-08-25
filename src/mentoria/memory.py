"""Memoria persistente do aluno (SQLite).

Estrategia de memoria de longo prazo do dominio (requisito 4.4): guarda o
historico do aluno (temas estudados e termos ja vistos) e recupera esse
perfil em execucoes futuras para personalizar o vocabulario, evitando
repetir termos que o aluno ja conhece.

Complementa o checkpointer do LangGraph (memoria de curto prazo / estado
de execucao), que e usado na feature de governanca para pausar/retomar em
pontos de aprovacao humana.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    request_type TEXT,
    theme        TEXT,
    run_id       TEXT,
    created_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS seen_terms (
    student_id  TEXT NOT NULL,
    term        TEXT NOT NULL,
    times_seen  INTEGER NOT NULL DEFAULT 1,
    last_seen   REAL NOT NULL,
    PRIMARY KEY (student_id, term)
);
"""


class StudentMemory:
    """Armazenamento persistente do perfil do aluno em SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: nodes podem rodar em threads (paralelismo).
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def record_session(
        self,
        student_id: str,
        request_type: str | None,
        theme: str | None,
        run_id: str | None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (student_id, request_type, theme, run_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (student_id, request_type, theme, run_id, time.time()),
            )

    def record_terms(self, student_id: str, terms: list[str]) -> None:
        now = time.time()
        with self._lock, self._conn:
            for term in terms:
                self._conn.execute(
                    "INSERT INTO seen_terms (student_id, term, times_seen, last_seen) "
                    "VALUES (?, ?, 1, ?) "
                    "ON CONFLICT(student_id, term) DO UPDATE SET "
                    "times_seen = times_seen + 1, last_seen = excluded.last_seen",
                    (student_id, term, now),
                )

    def get_profile(self, student_id: str, *, term_limit: int = 50, theme_limit: int = 5) -> dict:
        """Recupera o perfil: temas recentes, termos ja vistos e nº de sessoes."""
        with self._lock:
            themes = [
                row["theme"]
                for row in self._conn.execute(
                    "SELECT DISTINCT theme FROM sessions "
                    "WHERE student_id = ? AND theme IS NOT NULL "
                    "ORDER BY created_at DESC LIMIT ?",
                    (student_id, theme_limit),
                )
            ]
            terms = [
                row["term"]
                for row in self._conn.execute(
                    "SELECT term FROM seen_terms WHERE student_id = ? "
                    "ORDER BY times_seen DESC, last_seen DESC LIMIT ?",
                    (student_id, term_limit),
                )
            ]
            (session_count,) = self._conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE student_id = ?", (student_id,)
            ).fetchone()
        return {
            "student_id": student_id,
            "recent_themes": themes,
            "known_terms": terms,
            "sessions": session_count,
        }

    def close(self) -> None:
        self._conn.close()


_default_memory: StudentMemory | None = None


def get_default_memory() -> StudentMemory:
    """Instancia (lazy) a memoria padrao a partir das configuracoes."""
    global _default_memory
    if _default_memory is None:
        from mentoria.config import get_settings

        _default_memory = StudentMemory(get_settings().mentoria_db_path)
    return _default_memory
