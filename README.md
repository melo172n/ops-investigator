# Ops Investigator

Primeira fatia da POC: receber um alerta do Zabbix e encaminhá-lo para uma conversa operacional do Chatwoot.

## Payload do Zabbix

```json
{
  "event_id": "123456",
  "event_name": "Chatwoot indisponível",
  "severity": "HIGH",
  "host": "chatwoot",
  "status": "PROBLEM",
  "occurred_at": "2026-09-09T14:02:00Z",
  "description": "Health check falhou",
  "tags": {
    "environment": "production"
  }
}
```

O webhook deve enviar o segredo no header `X-Webhook-Secret`.

## Execução com Docker

```bash
docker build -t ops-investigator .
docker run --rm -p 8000:8000 --env-file .env ops-investigator
```

Copie `.env.example` para `.env`. Enquanto `CHATWOOT_ENABLED=false`, o endpoint processa o alerta sem realizar envio externo.

## Teste do webhook

```bash
curl -X POST http://localhost:8000/webhooks/zabbix \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: change-me" \
  -d '{
    "event_id": "123456",
    "event_name": "Chatwoot indisponível",
    "severity": "HIGH",
    "host": "chatwoot",
    "status": "PROBLEM",
    "occurred_at": "2026-09-09T14:02:00Z"
  }'
```

## Endpoints

- `GET /health`
- `POST /webhooks/zabbix`
- `GET /docs`

## Próximo incremento

Persistir o alerta no PostgreSQL e impedir notificações duplicadas pelo `event_id`.
