# Phase Closure

## Data e estado final

- Data: 2026-04-16
- Estado final da fase: `closed`
- Suite final: `548` testes passando, `6` skips
- Estado operacional: `GAP-01`, `GAP-03` e `GAP-04` fechados; `GAP-02` bloqueado por decisao formal de arquitetura; rounds corretivos posteriores fecharam os `ALTO`, `MEDIO` e residuos de approval sem reabrir o freeze

## Gaps resolvidos com evidencia

### GAP-01 — ownership residual de sessao

Fechado nesta fase como correcao operacional minima: o runtime passou a usar backend `file-backed` por default para `session claim` e `live proof`, inclusive no Windows, com residual de seguranca explicitamente documentado.

Evidencia:

- default `file-backed` para claim em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:2260>)
- default `file-backed` para live proof em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:2282>)
- contrato operacional documentado em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:89>)
- residual explicito do backend file-backed em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:90>)
- cobertura complementar do caminho WinCred live-proof em [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:170>) e [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:182>)

### GAP-03 — retencao de `artifacts/` e `events.jsonl`

Fechado nesta fase como politica manual validate-gated, auditavel e agora tambem provada para idempotencia de rerun e falha parcial relevante.

Evidencia:

- superficie CLI existente em [cli/main.py](</d:/projetos_cli/cerebro/cli/main.py:139>) e [cli/main.py](</d:/projetos_cli/cerebro/cli/main.py:144>)
- execucao do apply em [cli/commands/validate.py](</d:/projetos_cli/cerebro/cli/commands/validate.py:31>)
- implementacao do archive governado em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1719>)
- planejamento do log com exclusao de `retention_applied` da pressao de rerun em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1828>) e [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1854>)
- politica manual e conservadora documentada em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:131>), [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:134>) e [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:135>)
- happy path + idempotencia em [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:309>)
- falha parcial com rerun seguro em [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:356>)

### GAP-04 — criterios formais de entrada/saida de roles

Fechado como alinhamento documental canonico dos papeis `Researcher`, `Reviewer` e `Documenter`.

Evidencia:

- saida formal do `Researcher` em [docs/operations/AGENT_ROLES.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_ROLES.md:111>)
- gatilho formal do `Reviewer` em [docs/operations/AGENT_ROLES.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_ROLES.md:153>)
- entrada formal do `Documenter` em [docs/operations/AGENT_ROLES.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_ROLES.md:199>)

## Gaps bloqueados com ADR referenciado

### GAP-02 — intencao como entidade canonica

Bloqueado nesta fase por violacao direta do freeze atual.

Evidencia:

- decisao formal `Bloquear` em [docs/operations/adr/GAP-02-intencao-canonica.md](</d:/projetos_cli/cerebro/docs/operations/adr/GAP-02-intencao-canonica.md:92>)
- veredito explicito em [docs/operations/adr/GAP-02-intencao-canonica.md](</d:/projetos_cli/cerebro/docs/operations/adr/GAP-02-intencao-canonica.md:94>)
- criterio de reabertura proprio do gap em [docs/operations/adr/GAP-02-intencao-canonica.md](</d:/projetos_cli/cerebro/docs/operations/adr/GAP-02-intencao-canonica.md:100>)

## Contagem de testes

- Inicio da fase: `525`
- Fim da fase: `548`
- Delta: `+23`

## Residual aceito explicitamente

- `GAP-02` permanece bloqueado por ADR; nao ha autorizacao nesta fase para alterar `state.json` ou o schema canonico.
- O backend `file-backed` continua com residual explicito de `same-user tamper or restore` do authority store externo em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:90>).
- `verify` continua com boundary residual para tamper transitorio perfeitamente restaurado, efeitos fora do root e drift totalmente oculto em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:119>) e [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:123>).
- `apply` e `rollback` continuam sem garantia de atomicidade perfeita contra writers externos arbitrarios durante a execucao em [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:126>), [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:129>) e [docs/operations/OPERATIONS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/OPERATIONS_BASELINE.md:157>).

## Criterio de reabertura da proxima fase

A proxima fase so pode ser reaberta quando pelo menos um dos gatilhos formais abaixo estiver satisfeito:

- existir um caso de uso concreto e repetido que a superficie operacional atual nao satisfaz de forma limpa em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:68>)
- existir necessidade operacional real documentada e comprovadamente nao atendida pela superficie aprovada atual em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:69>)
- existir decisao arquitetural explicita autorizando abertura controlada de novo incremento alem do envelope atual em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:70>)

O protocolo de referencia para essa reabertura continua sendo o `Formal Resume Trigger` em [docs/operations/FREEZE_POLICY.md](</d:/projetos_cli/cerebro/docs/operations/FREEZE_POLICY.md:64>).

## Revalidacao Documental De Encerramento

- Em 2026-04-16, a prova de parada documental nao encontrou novo hotspot elegivel, novo bypass de fila, nem novo cenario de recovery fora do residual aceito.
- A revalidacao formal de encerramento agora esta coberta por guardas explicitas em `tests/test_doc_governance.py` e `tests/test_architecture.py`.
- `PHASE_CLOSURE.md` agora faz parte do perimetro automatizado de prova documental.
- O bloqueio `BLOCKED-TEST-001` foi fechado sem reabrir o freeze porque o slice ficou restrito a cobertura regressiva proporcional e alinhamento factual do estado documental.
- Um endurecimento documental posterior elevou o gate vivo da suite para `550` testes sem reabrir a fase corretiva fechada nem alterar o runtime.
- O endurecimento estrutural adicional deste documento permanece como slice separado e bloqueado fora da fila documental ativa.

## Encerramento Formal Da Sessao — 2026-04-18

### Data e estado final

- Data: `2026-04-18`
- Estado final da sessao: `closed`
- Suite final desta sessao: `595` testes passando, `6` skips
- Gate arquitetural final: `python -m unittest tests.test_architecture -v` verde com `50` testes
- Estado operacional final: nenhum `CRITICO` aberto; nenhum `ALTO` executavel; `2` itens `ALTO` permanecem apenas em `Grupo 6`; a rodada final de prova `P1-P5` terminou limpa

### Contagem de testes da sessao

- Inicio da sessao: `574`
- Fim da sessao: `595`
- Delta: `+21`

### Itens corrigidos nesta sessao

- `runtime.lock` stale-owner recovery no Windows:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4882>).
  Testes que cristalizaram: [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:2307>) e [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:2322>).
- Boundary de `command_registry.commands[*].cwd` agora coberto diretamente no validator e nos fail-closed tardios de `apply` e `verify`:
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:324>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:334>),
  [tests/test_action_runtime.py](</d:/projetos_cli/cerebro/tests/test_action_runtime.py:16>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:17>).
- Helpers centrais agora com cobertura direta:
  [core/command_sandbox.py](</d:/projetos_cli/cerebro/core/command_sandbox.py:20>) e [tests/test_command_sandbox.py](</d:/projetos_cli/cerebro/tests/test_command_sandbox.py:12>);
  [core/execution_policy.py](</d:/projetos_cli/cerebro/core/execution_policy.py:25>) e [tests/test_execution_policy.py](</d:/projetos_cli/cerebro/tests/test_execution_policy.py:15>);
  [core/runtime_event_window.py](</d:/projetos_cli/cerebro/core/runtime_event_window.py:6>) e [tests/test_runtime_event_window.py](</d:/projetos_cli/cerebro/tests/test_runtime_event_window.py:9>).
- `fs.move` same-path deixou de sair como `applied` e passou a falhar fechado como `action_no_effect` antes de mutacao:
  [core/discipline_runtime.py](</d:/projetos_cli/cerebro/core/discipline_runtime.py:141>).
  Testes que cristalizaram: [tests/test_runtime_units.py](</d:/projetos_cli/cerebro/tests/test_runtime_units.py:758>) e [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4963>).
- `exec.command` approval/retry agora ficou ancorado ao snapshot resolvido do `command_registry`, e `command_id` ausente passou a falhar fechado antes de approval/retry:
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:143>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:429>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:286>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:380>).
  Testes que cristalizaram: [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4280>), [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4377>) e [tests/test_runtime_units.py](</d:/projetos_cli/cerebro/tests/test_runtime_units.py:816>).
- `tests/test_analyze.py` deixou de depender de asserts frageis por indice e cristalizou a supressao padrao de `session_token`:
  [tests/test_analyze.py](</d:/projetos_cli/cerebro/tests/test_analyze.py:83>) e [tests/test_analyze.py](</d:/projetos_cli/cerebro/tests/test_analyze.py:113>).
- `import-context` e `checkpoint` passaram a exercer falhas reais de `Path.unlink` e `os.replace` nas regressões de rollback/reporting, sem mocks estreitos de `StateStore.close_session` ou `StateStore.save_state`:
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1012>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1064>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1973>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:2027>).

### Itens retidos em Grupo 6

- Approval por efeito para `fs.create_file overwrite=true`:
  [docs/operations/WEAKNESS_REPORT.md](</d:/projetos_cli/cerebro/docs/operations/WEAKNESS_REPORT.md:65>).
  Razao: a menor correcao segura cruza `execution_policy`, `apply` e [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:947>), entao um patch local reabriria drift de contrato.
  Criterio de reabertura: decisao arquitetural explicita para approval sensivel a efeito destrutivo sem criar segunda fonte de verdade nem quebrar retrocompatibilidade.
- Contaminacao de `verification.checks` pelo `check-state` sintetico:
  [docs/operations/WEAKNESS_REPORT.md](</d:/projetos_cli/cerebro/docs/operations/WEAKNESS_REPORT.md:74>).
  Razao: a menor correcao segura exige separar contrato persistido, consumidores de export/status e validacao historica de verificacao.
  Criterio de reabertura: decisao arquitetural explicita para canonicalizar ou separar o gate sintetico sem quebrar consumidores existentes.

### Padroes externos aceitos, rejeitados ou adiados

- Aceitos: storage externo `file-backed` para claim/live-proof com paths redigidos e overrides treated-as-trusted; sandbox de `verify` como clone descartavel do workspace, nao isolamento de host; hotspot de retencao ja documentado em [docs/operations/COST_TOPOLOGY.md](</d:/projetos_cli/cerebro/docs/operations/COST_TOPOLOGY.md:68>).
- Rejeitados: mocks estreitos em boundaries de rollback do CLI; reaproveitar approval/retry de `exec.command` apos drift do `command_registry`; tratar `fs.move` same-path como sucesso observavel.
- Adiados: redesign de approval por efeito em overwrite destrutivo; separacao contratual de `check-state` frente a `verification.checks`; benchmark dedicado do custo de retencao.

### Proxima abertura

- A sessao so deve ser reaberta por `Formal Resume Trigger` ou por problema novo confirmado com evidencia rastreavel.
- Enquanto isso, o estado operacional esperado permanece: baseline verde, `CRITICO`/`ALTO` executaveis vazios e apenas os dois `ALTO` acima retidos em `Grupo 6`.

## Revalidacao Final De Encerramento — 2026-04-18 (delta)

### Data e estado final

- Data: `2026-04-18`
- Estado final desta rodada adicional: `closed`
- Suite final desta rodada: `610` testes passando, `6` skips
- Gate arquitetural final: `python -m unittest tests.test_architecture -v` verde com `50` testes
- Prova de parada desta rodada: `P1-P5` limpa, com `P2` confirmado sem bypass/regressao silenciosa

### Contagem de testes da rodada

- Inicio da rodada: `607`
- Fim da rodada: `610`
- Delta: `+3`

### Item corrigido nesta rodada

- `close_session()` deixou de engolir falha de leitura/validacao de `session.local.json` e agora falha fechado com `session_close_failed` antes de limpar registry, claim ou live-proof:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1189>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:2347>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1064>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:2031>).

### Itens retidos em Grupo 6

- Approval por efeito para `fs.create_file overwrite=true` permanece retido em [docs/operations/WEAKNESS_REPORT.md](</d:/projetos_cli/cerebro/docs/operations/WEAKNESS_REPORT.md:65>).
- Contaminacao de `verification.checks` pelo `check-state` sintetico permanece retida em [docs/operations/WEAKNESS_REPORT.md](</d:/projetos_cli/cerebro/docs/operations/WEAKNESS_REPORT.md:74>).

### Timeouts registrados nesta rodada

- Nenhum timeout de subagente foi registrado.

### Proxima abertura

- A proxima abertura continua restrita a `Formal Resume Trigger` ou problema novo confirmado com evidencia rastreavel.

## Fechamento Do Modelo Externo — 2026-04-18

### Data e estado final

- Data: `2026-04-18`
- Estado final: `MODELO EXTERNO IMPLEMENTADO`
- Compatibilidade com projetos existentes: confirmada; `cwd` continua default, `--project-root` segue opt-in e o estado canônico permanece em `<project-root>/.cerebro`
- Próxima fase natural: worktrees ou novo problema confirmado

### Contagem de testes da trilha

- Início da trilha: `595`
- Fim da trilha: `633`
- Delta: `+38`

### Fatias concluídas

- `FATIA 1 — --project-root` global:
  `cli/main.py`, `cli/commands/_plan_input.py`, `tests/test_cli.py`, `tests/test_alpha_runtime.py`.
- `FATIA 2 — Menu de contexto ao abrir`:
  `cli/main.py`, `tests/test_cli.py`.
- `FATIA 3 — Registro de projetos`:
  `cli/project_registry.py`, `cli/main.py`, `tests/test_cli.py`, `docs/operations/MIGRATION_PLAN.md`.
- `FATIA 4 — Dashboard de estado ao abrir`:
  `cli/project_dashboard.py`, `cli/main.py`, `tests/test_cli.py`.
- `FATIA 5 — cerebro doctor`:
  `cli/commands/doctor.py`, `cli/main.py`, `tests/test_doctor.py`, `tests/test_cli.py`, `tests/test_architecture.py`.
- `FATIA 6 — Commit automático por iteração`:
  `cli/commands/iteration_commit.py`, `cli/main.py`, `tests/test_iteration_commit.py`, `tests/test_cli.py`, `tests/test_architecture.py`.
  Testes que cristalizaram o slice final:
  `tests.test_iteration_commit.IterationCommitCommandTests.test_run_iteration_commit_generates_commit_with_documented_message`,
  `tests.test_iteration_commit.IterationCommitCommandTests.test_run_iteration_commit_fails_closed_when_index_is_not_clean`,
  `tests.test_iteration_commit.IterationCommitCommandTests.test_run_iteration_commit_unstages_selection_when_commit_fails`.

### Fatias em Grupo 6

- Nenhuma nesta trilha do modelo externo.

### Compatibilidade confirmada

- Projetos existentes continuam operando sem mudança quando o operador usa `cwd`.
- `--project-root` segue apenas como seleção explícita de root lógico; não muda `root_sha256` fora do root resolvido realmente usado pela sessão.
- O novo `iteration-commit` atua só no repositório do Cerebro e não escreve em `.cerebro` do projeto gerenciado.

### Prova final

- `python -m unittest discover -s tests -v` verde com `633` testes e `6` skips.
- `python -m unittest tests.test_architecture -v` verde com `51` testes.
- O modelo externo agora fecha a trilha canônica `FATIAS 1-6` sem pendências abertas nesta fila.
