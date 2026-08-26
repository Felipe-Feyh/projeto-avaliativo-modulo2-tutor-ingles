# Automação low-code (n8n) — MentorIA

Fluxo visual que orquestra a integração com a aplicação. **A lógica permanece na
aplicação** (API `/ask`); o n8n apenas dispara e encaminha a saída (requisito 4.9).

## Fluxo

```
Webhook (trigger)  ->  HTTP Request: POST /ask (MentorIA)  ->  HTTP Request: Discord (saída observável)
```

- **Gatilho:** Webhook do n8n (`POST /webhook/mentoria-flashcards`) recebendo `{ "theme", "level", "student_id" }`.
- **Integração:** chama a API local do MentorIA (`POST http://localhost:8000/ask`) — toda a lógica agêntica roda na aplicação.
- **Saída observável:** posta um resumo do relatório em um canal do Discord via webhook.

Arquivo importável: [`mentoria-n8n.json`](./mentoria-n8n.json).

## Reprodução

1. Suba a API do MentorIA (com as chaves no `.env`):
   ```bash
   uvicorn mentoria.api:app --port 8000
   ```
2. No n8n, **Import from File** → selecione `docs/lowcode/mentoria-n8n.json`.
3. Defina as variáveis de ambiente do n8n: `MENTORIA_API_KEY` (se a API exigir) e
   `DISCORD_WEBHOOK_URL` (webhook do canal).
4. Ative o workflow e dispare o webhook, por exemplo:
   ```bash
   curl -X POST http://localhost:5678/webhook/mentoria-flashcards \
     -H "Content-Type: application/json" \
     -d '{"theme": "job interview", "level": "B2"}'
   ```
5. O resumo dos flashcards aparece no canal do Discord.

## Alternativa sem n8n (mesma saída observável)

A própria API pode notificar o Discord diretamente, chamando `/ask?notify=true`
(requer `DISCORD_WEBHOOK_URL` no ambiente):

```bash
curl -X POST "http://localhost:8000/ask?notify=true" \
  -H "Content-Type: application/json" \
  -d '{"message": "job interview", "level": "B2"}'
```
