# Napkin Runbook

## Curation Rules

- Re-prioritize on every read.
- Keep recurring, high-value notes only; this is a runbook, not a chronological session log.
- Keep at most 10 items per category.
- Every item must include a date and an explicit `Do instead:` action.
- Treat `POC-ops-investigator.md`, `CONTEXT.md`, `README.md` and `HANDOFF.md` as detailed references; keep this file focused on execution-critical knowledge.

## Mission & Safety Guardrails (Highest Priority)

1. **[2026-09-10] The service detects, investigates, records and notifies; it never repairs production**
   Do instead: give integrations and the future LangGraph investigator read-only capabilities and return an inconclusive result when evidence is insufficient.

2. **[2026-09-10] Keep the Ops Investigator independent from the customer-service runtime**
   Do instead: deploy it as a separate FastAPI application in Coolify so n8n, Chatwoot or the future customer-service LangGraph cannot share its lifecycle.

3. **[2026-09-10] Do not send customer content or secrets to an LLM**
   Do instead: sanitize evidence, store references and summaries rather than full logs, and exclude phone numbers, message text, tokens and credentials.

4. **[2026-09-10] Bound all evidence collection**
   Do instead: use read-only credentials and restrict Loki queries to a window of at most 60 minutes around the incident.

5. **[2026-09-10] Keep secrets outside Git and diagnostic output**
   Do instead: configure webhook secrets, API tokens and database credentials as Coolify environment variables and use placeholders in documentation/tests.

## Architecture & Domain Behavior

1. **[2026-09-10] Distinguish signals from real degradation**
   Do instead: call a monitoring signal an `Alerta`, a bounded degradation an `Incidente`, and an immutable evidence-based analysis an `Investigação`; multiple alerts may belong to one incident.

2. **[2026-09-10] Detect incidents deterministically before invoking LangGraph**
   Do instead: use application rules and persisted state to open an incident, then let LangGraph collect evidence, separate facts from hypotheses, estimate confidence and recommend a next check.

3. **[2026-09-10] Keep the two agents conceptually separate**
   Do instead: treat n8n as the current `Execução de Atendimento` engine (future customer-service LangGraph) and the future investigator LangGraph as the processor of already-detected incidents.

4. **[2026-09-10] Model unanswered conversations as unfulfilled response expectations**
   Do instead: when Chatwoot receives an inbound message in a bot-owned, unassigned conversation, create an `Expectativa de Resposta` with a four-minute deadline.

5. **[2026-09-10] Cancel false-positive unanswered-conversation incidents**
   Do instead: satisfy the expectation when the bot replies and cancel it when a human/team assumes the conversation; at the deadline, re-read Chatwoot before opening an incident.

6. **[2026-09-10] Avoid duplicate timers and incidents for one conversation**
   Do instead: correlate by Chatwoot conversation and the latest unanswered inbound message, updating the active expectation rather than creating parallel incidents.

7. **[2026-09-10] Separate generation failure from delivery failure**
   Do instead: classify `Falha de Geração` when the automation produces no response, `Falha de Entrega` when a response exists but bridge/UAZAPI does not deliver it, or `inconclusivo` when evidence cannot distinguish them.

8. **[2026-09-10] Evidence sources have defined responsibilities**
   Do instead: use Chatwoot for messages/assignment, n8n error webhooks for execution failures, Loki for `chatwoot`, `chatwoot-worker` and `bridge` logs, Zabbix for problems/metrics, and UAZAPI only through an appropriate read-only status endpoint.

## Implemented Application Behavior

1. **[2026-09-10] FastAPI entry points are already operational**
   Do instead: preserve `GET /health` returning `{"status":"ok"}` and `POST /webhooks/zabbix` returning HTTP 202 after validation and processing.

2. **[2026-09-10] Authenticate the Zabbix webhook with constant-time comparison**
   Do instead: require `X-Webhook-Secret`, compare it with `secrets.compare_digest`, and return HTTP 401 for a missing or invalid secret.

3. **[2026-09-10] Preserve the current Zabbix payload contract**
   Do instead: accept `event_id`, `event_name`, `severity`, `host`, `status`, `occurred_at`, optional `description` and optional `tags`; normalize severity to lowercase and status to uppercase.

4. **[2026-09-10] Notification failures must not reject an accepted alert**
   Do instead: return HTTP 202 with `notification.status` equal to `sent`, `skipped` or `failed`, retaining a sanitized failure detail for diagnosis.

5. **[2026-09-10] WhatsApp notification currently travels through Chatwoot**
   Do instead: create a public outgoing message in the fixed operations conversation using `/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages`; use `CHATWOOT_ENABLED=false` for safe local processing.

6. **[2026-09-10] PostgreSQL persistence is locally validated and awaiting production deploy**
   Do instead: deploy the Alembic-backed incident, alert-occurrence and notification-attempt tables; preserve one `inc_<16 hex>` identity across a Zabbix event's `PROBLEM` and `RESOLVED` transitions and skip repeated transitions.

7. **[2026-09-10] Automated coverage is currently minimal**
   Do instead: preserve tests for health, invalid webhook secret, and accepted/normalized Zabbix alert, then add database, deduplication, retry and Chatwoot-event tests with each increment.

## Deployment & Runtime

1. **[2026-09-10] Production runs from the repository Dockerfile in Coolify**
   Do instead: keep Python 3.12, Uvicorn on `0.0.0.0:8000`, the curl healthcheck, and the host mapping `127.0.0.1:8010 -> 8000`.

2. **[2026-09-10] The public endpoint uses host Nginx and Certbot**
   Do instead: route `https://gb6oomf5wsjouiiomgfttw7q.108.174.146.11.sslip.io` to `http://127.0.0.1:8010`; retain `server_names_hash_bucket_size 128;` in Nginx because the automatic hostname is long.

3. **[2026-09-10] Cross-application Docker DNS is not available in the current layout**
   Do instead: configure `CHATWOOT_URL` with the public Chatwoot base URL; do not use `http://chatwoot:3000` while the applications remain on separate Docker networks.

4. **[2026-09-10] The observed VPS stack is Docker-based**
   Do instead: account for Coolify, Chatwoot/worker/database/Redis, bridge, n8n main/workers/database/Redis, Zabbix server/web/database, Grafana, Loki, Promtail, Portainer and MCP Grafana when diagnosing dependencies.

5. **[2026-09-10] The dedicated application database is running privately in Coolify**
   Do instead: use `ops-investigator-postgres` (`postgres:16-alpine`) with user/database `ops_investigator` through its internal URL; keep Public access `Private` and never reuse the Zabbix, Chatwoot or n8n databases.

6. **[2026-09-10] Coolify displays `3000:5432` as an empty port-mapping placeholder**
   Do instead: recognize the gray placeholder as an example, leave the field empty, and confirm that Public access remains `Private` before starting PostgreSQL.

7. **[2026-09-10] `DATABASE_URL` is configured as a production runtime secret**
   Do instead: use the database's internal URL literally, keep it unavailable during image build, and never paste its password into chat, source files or logs.

## Zabbix 7.0.28 Integration — Validated

1. **[2026-09-10] The full Zabbix-to-WhatsApp path is proven for both state transitions**
   Do instead: preserve the validated flow `Zabbix Action -> Ops Investigator webhook -> Chatwoot operations conversation -> WhatsApp`; controlled PROBLEM and RESOLVED notifications both arrived.

2. **[2026-09-10] Use the validated Zabbix objects and scope**
   Do instead: keep Media Type and Action named `Ops Investigator`, user `ops-investigator-notifier`, user group `Ops Investigator Notifications`, host group `TecnoCW`, visible host `TecnoCW VPS Production`, and technical host name `tecnocw-prod-vps` where an exact sender host is required.

3. **[2026-09-10] Zabbix 7.0 does not expand `{EVENT.TIMESTAMP}`**
   Do instead: have the Media Type JavaScript fall back to `new Date().toISOString()` (currently the webhook execution time) and pass the resulting valid ISO-8601 timestamp to the API.

4. **[2026-09-10] Recovery needs its own status macro**
   Do instead: pass `recovery_status={EVENT.RECOVERY.STATUS}` and choose it for recovery operations so WhatsApp receives `RESOLVED`, not another `PROBLEM`.

5. **[2026-09-10] Manual Media Type tests do not provide a real event context**
   Do instead: tolerate literal macros such as `{EVENT.ID}` only for isolated script validation; use a real Action-triggered event to validate macro expansion and end-to-end behavior.

6. **[2026-09-10] Direct unencrypted `zabbix_sender` is blocked for the production host**
   Do instead: use the controlled calculated-item test driven by host macro `{$OPS_INVESTIGATOR_TEST}` unless sender TLS is explicitly configured; the server logged `connection of type "unencrypted" is not allowed` for `tecnocw-prod-vps`.

7. **[2026-09-10] Controlled integration test uses a calculated item and trigger**
   Do instead: keep item `Ops Investigator integration test` with key `ops.investigator.test`, toggle `{$OPS_INVESTIGATOR_TEST}` from `0` to `1` to create PROBLEM and back to `0` to recover, and leave it at `0` after testing.

8. **[2026-09-10] Avoid duplicate legacy notifications during controlled tests**
   Do instead: keep the old `Report problems to Zabbix administrators` Action disabled while validating the dedicated Ops Investigator Action; it previously sent Telegram and attempted Email independently.

## Verification & Operational Tactics

1. **[2026-09-10] Flush a new incident before inserting its alert event**
   Do instead: because the models currently use a scalar `incident_id` without an ORM relationship, explicitly flush the new `Incident` before adding `AlertEvent`; keep SQLite foreign-key enforcement enabled in the repository regression test so PostgreSQL ordering failures are caught locally.

2. **[2026-09-10] Verify webhook changes with a complete transition cycle**
   Do instead: trigger `0 -> 1 -> 0`, inspect Zabbix action history, confirm the API response, and confirm distinct PROBLEM and RESOLVED messages in WhatsApp.

3. **[2026-09-10] Check the Zabbix server log when sender processing fails**
   Do instead: filter recent `tecnocw-zabbix-server` logs for the item key, technical host, `trapper`, `not found` and `cannot process` before changing host/item definitions.

4. **[2026-09-10] Send PowerShell test payloads as UTF-8 bytes**
   Do instead: encode JSON using `[System.Text.Encoding]::UTF8.GetBytes($payload)` before the HTTP request to prevent parsing/character-encoding failures.

5. **[2026-09-10] Treat the working tree as user-owned**
   Do instead: preserve unrelated changes and the currently untracked `HANDOFF.md`; inspect `git status` before edits and never discard files to make the tree clean.

6. **[2026-09-10] The repository has no `.planning/` GSD structure**
   Do instead: use the existing product documents as authority unless the user explicitly chooses to initialize GSD planning; do not assume phase files exist.

## Immediate Roadmap

1. **[2026-09-10] Deploy and verify persistence before adding more inbound event sources**
   Do instead: ship the locally validated migration/repository changes, confirm Alembic creates the production tables, then run one `PROBLEM -> duplicate PROBLEM -> RESOLVED` cycle and verify one incident with two alert occurrences.

2. **[2026-09-10] Make accepted alerts reliable**
   Do instead: add idempotent handling, safe Chatwoot retries, structured logs and tests before expanding the action beyond the controlled host/test trigger.

3. **[2026-09-10] Implement unanswered-conversation detection after persistence**
   Do instead: add authenticated `POST /webhooks/chatwoot`, persist Chatwoot events and response expectations, run a PostgreSQL-backed worker for the four-minute deadline, and re-query Chatwoot before opening an `Incidente de Atendimento`; do not add Redis for the POC.

4. **[2026-09-10] Add n8n errors as correlated evidence**
   Do instead: implement authenticated `POST /webhooks/n8n`, store sanitized execution metadata, and correlate it to conversation/execution IDs without assuming absence of an error webhook proves success.

5. **[2026-09-10] Validate read-only evidence adapters before LangGraph**
   Do instead: implement bounded reads from Zabbix and Loki, verify Chatwoot conversation reads, and evaluate a read-only UAZAPI status endpoint independently.

6. **[2026-09-10] Introduce LangGraph only after deterministic integrations work**
   Do instead: pass a normalized persisted incident to the graph, collect evidence through read-only adapters, record an immutable investigation, and notify operations with facts, hypothesis, confidence and next check.

7. **[2026-09-10] Telegram is fallback scope, not the current primary path**
   Do instead: keep WhatsApp via Chatwoot as primary and add Telegram only after the investigation and unanswered-conversation flows are reliable.

## User Collaboration Directives

1. **[2026-09-10] Guide configuration one immediate step at a time**
   Do instead: give one concrete action, wait for the user's completion/result, inspect screenshots or command output, then provide the next action.

2. **[2026-09-10] Match instructions to Zabbix 7.0.28**
   Do instead: use labels and macros available in 7.0.28 and adapt when the UI lacks options documented for newer versions, such as a displayed `And` calculation selector.

3. **[2026-09-10] Explain component ownership whenever the flow becomes ambiguous**
   Do instead: state explicitly who detects, who investigates, which system delivers, and which human receives each alert before proceeding with configuration.
