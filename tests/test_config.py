"""Testes de fumaca da configuracao base."""

from mentoria import __version__
from mentoria.config import Settings


def test_version_exposta() -> None:
    assert __version__ == "0.1.0"


def test_settings_defaults(monkeypatch) -> None:
    # Garante defaults previsiveis mesmo sem .env no ambiente de CI.
    for var in ("LLM_PROVIDER", "GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "groq"
    assert settings.groq_model
    assert settings.has_groq() is False
    assert settings.has_gemini() is False


def test_settings_le_env(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "gemini"
    assert settings.has_groq() is True
