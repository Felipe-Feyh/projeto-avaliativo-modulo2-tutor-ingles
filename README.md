# MentorIA — Agente Tutor de Inglês

> Projeto Avaliativo — Módulo 2 (M2.2). Agente de IA que apoia o aprendizado de inglês.

**Status:** em desenvolvimento.

## O que é

MentorIA é um agente de IA (LangGraph) que ajuda estudantes de inglês em dois cenários principais:

1. **Flashcards por tema** — gera cartões de vocabulário sobre um tema (viagens, comidas, entrevistas, etc.), com termo, tradução, exemplo de uso e fonética.
2. **Compreensão de leitura** — recebe um texto curto (ex: sobre programação) e gera perguntas de compreensão sobre o conteúdo.

## Stack

- Python 3.14
- LangGraph / LangChain
- LLM: Groq (primário) com fallback para Google Gemini — configurável por variável de ambiente
- FastAPI (API local)
- SQLite (memória e persistência)
- pytest + ruff
- GitHub Actions (CI)

## Configuração

Copie `.env.example` para `.env` e preencha as chaves. Nenhum segredo é versionado.

Documentação completa (arquitetura, cenários, execução, evidências) será adicionada ao longo do desenvolvimento em `/docs` e neste README.
