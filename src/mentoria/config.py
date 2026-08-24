"""Configuracao da aplicacao via variaveis de ambiente.

O modelo e o provedor de LLM sao configurados por env vars, mantendo
credenciais fora do codigo (requisito 4.10). Um arquivo .env local pode
ser usado em desenvolvimento; .env nunca e versionado.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = str  # "groq" | "gemini"


class Settings(BaseSettings):
    """Configuracoes carregadas do ambiente (ou de um .env local)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM primario (Groq) e fallback (Gemini)
    llm_provider: Provider = Field(default="groq")
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.0-flash")

    # App
    log_level: str = Field(default="INFO")
    mentoria_db_path: str = Field(default="data/mentoria.db")

    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    """Retorna as configuracoes (cacheadas) da aplicacao."""
    return Settings()
