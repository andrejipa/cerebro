# GAP-02 — intencao canonica

## Problema

Hoje o runtime nao possui uma entidade canonica propria para `intencao`.
O conceito operacional existe, mas esta disperso entre campos de `goal` e em registros procedurais externos.
Isso importa porque a falta de um campo autoritativo unico dificulta distinguir:

- objetivo do checkpoint
- objetivo do plano atual
- intencao da rodada externa

Sem essa separacao, o operador precisa inferir semantica a partir de texto curto e contexto do round.

## Evidencia atual

Achados comprovados no estado e na validacao atuais:

- `checkpoint.goal` existe como campo canonico em [core/schema.py](</d:/projetos_cli/cerebro/core/schema.py:25>) e eh inicializado em [core/schema.py](</d:/projetos_cli/cerebro/core/schema.py:63>); a validacao do bloco `checkpoint` exige exatamente as chaves atuais em [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:134>).
- `agent_runtime.plan.goal` existe como campo canonico em [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:7>), eh inicializado em [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:243>) e eh preservado pela canonicalizacao do plano em [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:295>).
- o comando `plan` persiste `goal` e `summary` no plano atual em [cli/commands/plan.py](</d:/projetos_cli/cerebro/cli/commands/plan.py:105>).
- o protocolo ja usa um `external round intent label` como disciplina operacional, nao como autoridade de runtime, em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:11>) e [docs/operations/AGENT_PROTOCOL.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_PROTOCOL.md:44>).
- a baseline explicita que decisoes de governanca como esta permanecem hoje como registros procedurais, nao como campos dedicados de runtime, em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:157>) e [docs/operations/AGENT_PROTOCOL.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_PROTOCOL.md:192>).

Achados ausentes ou apenas hipoteticos:

- campo literal `intention` ou `intencao` no estado canonico: nao encontrado.
- `checkpoint.summary`, `checkpoint.next_step` e `agent_runtime.plan.summary` como representacao formal de intencao: hipotese sem suporte estrutural atual.
- `state.json` para inspecao local neste workspace: nao encontrado.

## Avaliacao de freeze

Resultado do Reviewer: `bloqueado sob o freeze atual`.

Razao:

- o freeze proibe alterar `state.json` ou o schema em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:43>).
- o freeze proibe introduzir novo artefato canonico em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:42>).
- `core expansion or schema growth` esta explicitamente fora de escopo enquanto congelado em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:144>).

O `Formal Resume Trigger` atual nao destrava esse caso por si so.
O proprio `Minimum Safe Advance Policy` limita qualquer retomada a incrementos externos ao core e veda mudanca em schema e `state.json` em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:34>).

## Impacto estrutural

Resultado do Architect:

- a menor mudanca estrutural coerente seria um unico campo canonico em `checkpoint`, nao em `agent_runtime`.
- a forma minima proposta foi `checkpoint.round_intent` como autoridade unica, sem espelho em `plan`, `audit` ou eventos.

Se essa mudanca fosse autorizada fora do freeze, ela exigiria atualizacao conjunta de:

- [core/schema.py](</d:/projetos_cli/cerebro/core/schema.py:25>) para incluir a nova chave e o default em `build_initial_state`
- [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:134>) para validar a nova chave no bloco `checkpoint`
- [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:617>) para backfill canonico de estados legados
- [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1018>) e [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3197>) para aceitar e persistir o novo campo
- [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4235>) para expor o campo na leitura estavel

Contratos implicitos que quebrariam:

- estados legados falhariam sem canonicalizacao de backfill
- o writer de checkpoint hoje assume o conjunto atual exato de campos
- a leitura estavel de snapshot ficaria incompleta se o campo novo nao fosse projetado
- qualquer espelho do mesmo conceito em `agent_runtime`, `audit` ou replay de eventos criaria segunda fonte de verdade

## Opcoes consideradas com trade-offs

### Opcao A — nao mudar nada agora

Trade-off:

- preserva integralmente o freeze
- mantem o gap semantico atual
- nao cria risco de segunda fonte de verdade

### Opcao B — adicionar `checkpoint.round_intent` agora

Trade-off:

- fecha o gap conceitual com menor delta de schema
- cria uma autoridade unica mais clara
- viola o freeze atual porque toca schema, `state.json`, validacao e persistencia

### Opcao C — registrar intencao apenas em docs e round records

Trade-off:

- permanece dentro do freeze
- melhora disciplina operacional
- nao fecha o GAP-02 como entidade canonica; so documenta o residual

## Decisao

`Bloquear`.

Nao implementar neste round.
O estado atual do freeze torna qualquer schema change para intencao canonica uma violacao direta da politica vigente.
O round fecha como diagnostico de arquitetura, nao como slice de implementacao.

## Criterio de reabertura se bloqueado ou adiado

Reabrir apenas quando todos os itens abaixo estiverem satisfeitos:

- houver caso de uso operacional concreto e repetido mostrando que a superficie atual nao satisfaz a necessidade de forma limpa
- um humano registrar decisao arquitetural explicita autorizando sair do freeze para mudar `state.json` e o schema, e nao apenas abrir novo incremento externo read-only
- ficar decidido por humano que a autoridade unica sera no `checkpoint`, sem espelho em `agent_runtime`, `audit` ou event log
- ficar decidido o nome do campo, o dominio valido e a postura de compatibilidade legada

Sem esses quatro itens, a decisao correta continua sendo bloquear.

## Residual e proximo round

Residual:

- `GAP-02` permanece aberto
- o runtime continua sem entidade canonica propria para intencao
- a disciplina operacional externa continua sendo o unico lugar formal para o label de intencao do round

Proximo round recomendado:

- manter foco em documentacao e governanca enquanto o freeze permanecer ativo, ou
- abrir um round humano de arquitetura para decidir se o freeze sera explicitamente suspenso para um unico slice de schema
