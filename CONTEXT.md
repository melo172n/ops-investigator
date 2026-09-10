# Ops Investigator

Vocabulário do domínio usado para distinguir os sinais operacionais, os problemas reais e as análises produzidas pelo investigador.

## Linguagem

**Alerta**:
Um sinal emitido por uma fonte de monitoramento que indica uma condição relevante. Vários alertas podem se referir ao mesmo incidente.
_Evitar_: Incidente, problema

**Ocorrência de Alerta**:
Uma transição de estado comunicada por uma fonte para um alerta, como `PROBLEM` ou `RESOLVED`. A repetição da mesma transição é uma entrega duplicada, não uma nova ocorrência.
_Evitar_: Incidente, tentativa de notificação

**Incidente**:
Uma degradação real e delimitada na operação da plataforma de atendimento. Pode reunir vários alertas e várias investigações durante seu ciclo de vida.
_Evitar_: Alerta, evento

**Incidente de Atendimento**:
Uma falha delimitada a um atendimento específico no qual uma resposta esperada não foi gerada ou entregue.
_Evitar_: Incidente operacional, alerta

**Incidente Operacional**:
Uma degradação compartilhada que agrupa incidentes de atendimento relacionados por uma mesma causa provável.
_Evitar_: Incidente de atendimento, alerta agregado

**Investigação**:
Um registro imutável da análise feita em determinado momento sobre um incidente, contendo as evidências disponíveis e sua conclusão naquele instante.
_Evitar_: Incidente, diagnóstico

**Expectativa de Resposta**:
O compromisso de que uma mensagem recebida em uma conversa sob responsabilidade do bot deve resultar em uma resposta correspondente dentro do prazo acordado.
_Evitar_: Alerta, execução

**Execução de Atendimento**:
Uma tentativa delimitada de produzir a resposta do bot, independentemente do mecanismo que a executa.
_Evitar_: Workflow do n8n, execução do LangGraph

**Falha de Geração**:
Um incidente de atendimento em que o atendimento automatizado não produz a resposta esperada.
_Evitar_: Falha de entrega

**Falha de Entrega**:
Um incidente de atendimento em que uma resposta foi produzida, mas não chegou ao canal do cliente.
_Evitar_: Falha de geração
