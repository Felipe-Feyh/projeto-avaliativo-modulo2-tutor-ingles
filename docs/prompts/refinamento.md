# Ciclos de refinamento

Registro de refinamentos relevantes durante o desenvolvimento (requisito 4.10 / critério 15):
problema observado → alteração aplicada → resultado.

## 1. Comportamento do agente — resiliência da tool a rate limit (429)

- **Problema observado:** durante o desenvolvimento da tool de dicionário (PR #15), a Free
  Dictionary API apresentou instabilidade (respostas `502`/`5xx`) e aplica rate limit (`429`).
  O código tratava `429` como erro terminal, retornando `None` de imediato — degradando os
  flashcards sem necessidade.
- **Alteração aplicada:** em `DictionaryClient.lookup`, `429` passou a ser tratado como
  **transitório**, junto de `5xx`, com **retry + backoff exponencial** (PR #9, QA inteligente).
- **Resultado:** resiliência comprovada pelo teste `tests/test_dictionary.py::test_retry_em_429_rate_limit`
  (simula `429` seguido de `200` e verifica o retry). A análise de risco em
  `docs/evidencias/devops-analise.md` reforçou a prioridade dessa correção.

## 2. Prompt — personalização por histórico do aluno

- **Problema observado:** o vocabulário gerado repetia termos que o aluno já havia estudado,
  reduzindo o valor pedagógico para alunos recorrentes.
- **Alteração aplicada:** o prompt de vocabulário (`vocab_user` em `src/mentoria/prompts.py`)
  passou a receber os **termos já vistos** (recuperados da memória SQLite) com a instrução
  explícita de **não repeti-los**; o node `generate_vocabulary` injeta `known_terms`.
- **Resultado:** o agente passa a personalizar a saída conforme o histórico. O caminho de
  memória (gravação/recuperação e uso pelo prompt) é coberto por `tests/test_memory.py`.
