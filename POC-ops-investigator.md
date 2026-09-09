# POC — Ops Investigator

Serviço independente de investigação assistida para a plataforma de atendimento formada por Chatwoot, UAZAPI, bridge e o agente atualmente executado no n8n.

O Ops Investigator recebe alertas do Zabbix e identifica conversas que ficaram sem resposta. Depois, reúne evidências com LangGraph e envia uma explicação curta pelo WhatsApp via Chatwoot. O Telegram funciona como canal alternativo.

## 1. Objetivo

Validar que o investigador consegue:

- receber e explicar alertas do Zabbix;
- identificar conversas sob responsabilidade do bot que ficaram sem resposta;
- consultar evidências no Zabbix, Loki, Chatwoot e n8n;
- indicar uma causa provável ou assumir que a investigação foi inconclusiva;
- avisar rapidamente uma pessoa pelo WhatsApp;
- reduzir o trabalho manual necessário para iniciar a investigação.

O sistema não corrige produção. Ele somente detecta, investiga, registra e notifica.

## 2. Casos de uso

### 2.1 Alerta do Zabbix

1. O Zabbix envia um webhook ao Ops Investigator.
2. O serviço valida e registra o alerta.
3. O investigador consulta o problema no Zabbix e os logs próximos ao evento no Loki.
4. O LangGraph organiza as evidências e produz uma causa provável ou uma conclusão inconclusiva.
5. A investigação é registrada.
6. Uma mensagem é enviada pelo WhatsApp via Chatwoot.
7. O Telegram pode receber a mesma mensagem ou servir como alternativa se o Chatwoot falhar.

### 2.2 Conversa sem resposta

1. O Chatwoot informa que uma mensagem de cliente foi recebida.
2. O Ops Investigator aguarda quatro minutos.
3. Ao final do prazo, verifica se:
   - a conversa continua sem agente humano e sem time atribuídos;
   - o bot ainda não respondeu.
4. Se um humano ou time assumir a conversa, o incidente não é aberto.
5. Se o bot responder, o incidente não é aberto.
6. Se continuar sem atribuição e sem resposta, um incidente é criado e investigado.

A investigação procura erros recebidos do n8n, logs de `chatwoot`, `chatwoot-worker` e `bridge`, problemas do Zabbix e, quando disponível, o status da UAZAPI.

O n8n enviará somente webhooks de erro nesta POC. Portanto, quando não houver evidência suficiente para diferenciar workflow não iniciado, travado ou concluído sem resposta, o resultado será inconclusivo.

## 3. Arquitetura

```text
Zabbix -------- alerta -----------+
                                  |
Chatwoot ------ mensagem ---------+--> FastAPI
                                  |      |
n8n ----------- erro do workflow -+      +--> PostgreSQL
                                         |
                                         v
                                LangGraph Investigator
                                  |-- Zabbix
                                  |-- Loki
                                  |-- Chatwoot
                                  |-- UAZAPI, se disponível
                                         |
                                         +--> Chatwoot --> WhatsApp
                                         |
                                         +--> Telegram
```

O Ops Investigator roda como aplicação separada no Coolify. Ele não roda dentro do n8n e não depende do ciclo de vida do agente de atendimento.

Para a POC, um worker simples apoiado no PostgreSQL controla o prazo de quatro minutos e executa as investigações. Não é necessário adicionar Redis ou uma plataforma de filas.

## 4. Fontes de evidência

| Fonte | Uso |
|---|---|
| Zabbix | Alertas, problemas e métricas relacionadas. |
| Loki | Logs de `chatwoot`, `chatwoot-worker` e `bridge`. |
| Chatwoot | Mensagens e estado de atribuição da conversa. |
| n8n | Webhooks de erro do workflow de atendimento. |
| UAZAPI | Status da integração, se houver endpoint de leitura. |

Os outros serviços visíveis no Loki ficam fora das consultas iniciais. Eles poderão ser adicionados quando houver um caso concreto que exija essas evidências.

## 5. Papel do LangGraph

A detecção é feita por regras. O LangGraph recebe um incidente já identificado e tenta explicá-lo.

```text
normalizar incidente
  -> buscar contexto no Zabbix
  -> buscar logs no Loki
  -> buscar erro correlato do n8n
  -> analisar evidências
  -> registrar investigação
  -> notificar
```

O investigador deve:

- separar fatos observados de hipóteses;
- informar quais fontes foram consultadas;
- continuar quando uma fonte estiver indisponível;
- responder “inconclusivo” quando faltarem evidências;
- nunca executar comandos nem alterar infraestrutura.

## 6. Dados mínimos

Cada incidente registra:

- origem e horário;
- serviço ou conversa afetada;
- severidade;
- resumo do problema;
- evidências sanitizadas;
- hipótese e nível de confiança;
- próximos passos;
- resultado da notificação.

Logs completos continuam no Loki. O banco guarda somente referências e resumos necessários para entender a investigação.

## 7. Notificação

Exemplo de alerta do Zabbix:

```text
🚨 Alerta operacional

Serviço: chatwoot
Severidade: alta
Início: 11:02 BRT

Resumo: taxa elevada de erros detectada pelo Zabbix.
Possível causa: falha de conexão com o PostgreSQL.
Confiança: média

Evidências:
- problema ativo no Zabbix;
- erros de conexão nos logs do chatwoot.

Próximo passo: verificar disponibilidade do PostgreSQL.
Incidente: inc_01J...
```

Exemplo de conversa sem resposta:

```text
⚠️ Conversa sem resposta

Conversa: 12345
Tempo sem resposta: 4 minutos
Agente/time atribuído: não

Possível causa: workflow do n8n apresentou erro.
Próximo passo: verificar a execução do workflow.
Incidente: inc_01K...
```

O WhatsApp é o canal principal e usa uma conversa de operações no Chatwoot. O Telegram é alternativo.

## 8. API mínima

| Método | Rota | Finalidade |
|---|---|---|
| `POST` | `/webhooks/zabbix` | Receber alertas do Zabbix. |
| `POST` | `/webhooks/chatwoot` | Receber mensagens do Chatwoot. |
| `POST` | `/webhooks/n8n` | Receber erros do workflow. |
| `GET` | `/incidents` | Consultar incidentes recentes. |
| `GET` | `/incidents/{id}` | Consultar uma investigação. |
| `GET` | `/health` | Verificar a aplicação. |

## 9. Limites de segurança

- Validar os webhooks com segredo compartilhado.
- Ignorar eventos repetidos usando o ID fornecido pela origem.
- Usar credenciais de leitura para Zabbix, Loki e UAZAPI.
- Não enviar ao modelo telefones, texto de clientes, tokens ou credenciais.
- Limitar consultas do Loki a uma janela de até 60 minutos.
- Não armazenar logs completos.
- Não permitir ferramentas que alterem produção.

## 10. Ordem de implementação

### Marco 1 — Zabbix até o WhatsApp

- Receber um alerta de teste do Zabbix.
- Registrar o evento.
- Enviar uma mensagem simples pelo Chatwoot para o WhatsApp.

### Marco 2 — Investigação

- Consultar Zabbix e Loki.
- Criar o grafo de investigação.
- Enviar hipótese, evidências e próximos passos.

### Marco 3 — Conversa sem resposta

- Receber mensagens do Chatwoot.
- Verificar a conversa depois de quatro minutos.
- Cancelar quando humano/time assumir ou o bot responder.
- Correlacionar webhooks de erro do n8n.
- Investigar e notificar a ausência de resposta.

### Marco 4 — Telegram

- Adicionar o canal alternativo.
- Registrar falhas de envio pelo Chatwoot.

## 11. Critérios de aceitação

A POC está validada quando:

- um alerta de teste do Zabbix gera uma investigação e chega ao WhatsApp;
- uma conversa sem atribuição e sem resposta por quatro minutos gera um incidente;
- uma conversa assumida por humano ou time não gera incidente;
- um erro do n8n aparece como evidência quando puder ser correlacionado;
- evidências insuficientes produzem resultado inconclusivo;
- eventos repetidos não geram notificações duplicadas;
- nenhuma investigação executa ações na infraestrutura.

## 12. Fora da POC

- Correção automática de incidentes.
- Substituição do agente do n8n por LangGraph.
- Confirmação final de entrega no dispositivo do cliente.
- Agrupamento avançado de incidentes por causa raiz.
- Análise contínua de todos os logs.
- Dashboard próprio completo.
- Multitenancy.
- Sistema avançado de filas, escalonamento e plantão.
