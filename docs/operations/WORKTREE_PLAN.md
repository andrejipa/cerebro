# Worktree Plan

## Estado Atual Confirmado — 2026-04-18

- Baseline confirmado no início da trilha: `Ran 665 tests in 40.053s` / `OK`
- Baseline após a Fatia 1: `Ran 671 tests in 42.536s` / `OK (skipped=6)`
- Baseline após a Fatia 2: `Ran 677 tests in 32.452s` / `OK (skipped=6)`
- Baseline após a Fatia 3: `Ran 682 tests in 34.338s` / `OK (skipped=6)`
- Baseline final após correções e prova de parada: `Ran 688 tests in 37.632s` / `OK`
- `git worktree list` atual:
  - `D:/projetos_cli/cerebro 296cb50 [main]`
- Prova de parada final:
  - `P1-P5` retornaram `NÍVEL 0`
  - `P2` confirmado limpo
- Suporte atual de worktree já existe para a Fatia 1:
  - `cli/main.py:345-363`
  - `cli/worktree_registry.py`
  - `cli/commands/worktree.py`
  - `tests/test_cli.py:1179-1244`
- O boundary atual já opera por `root` explícito:
  - `core/state_store.py:121-130`
  - `cli/main.py:450-453`
- O lock atual é por `root/.cerebro/runtime.lock`, não por repositório git:
  - `core/state_store.py:129`
  - `core/state_store.py:4967-5000`
- `root_sha256` ancora sessão por path resolvido, não por identidade git:
  - `core/state_store.py:2705-2707`
  - `core/state_store.py:3207-3209`
  - `core/state_store.py:3307-3309`

## Arquitetura Proposta E Aprovada

### Decisão

- Cada worktree será um `project_root` independente.
- Cada worktree terá seu próprio `.cerebro/`, `state.json`, `runtime.lock` e sessão.
- O repositório principal manterá apenas o registro central em `.cerebro/worktrees.toml`.
- O checkout do worktree **não** ficará dentro de `.cerebro/`.
- O diretório aprovado para checkouts é `<repo>/.worktrees/<nome>/`.

### Razão

- O runtime atual ancora a autoridade em `root/.cerebro`, então ancorar um checkout dentro de `.cerebro/` mistura boundary autoritativo com workspace ativo:
  - `core/state_store.py:121-130`
- `exec.command` restringe `cwd` ao `root`, mas não saneia argumentos arbitrários; um checkout dentro de `.cerebro/` amplia superfície lateral para tocar o `.cerebro` pai:
  - `core/action_runtime.py:889-903`
- O `runtime.lock` só protege instâncias que compartilham o mesmo `root/.cerebro`, então worktrees com roots distintos são isolados por design:
  - `core/state_store.py:129`
  - `core/state_store.py:4967-5000`
- `root_sha256` já favorece isolamento por path, o que combina com sessão própria por worktree:
  - `core/state_store.py:2705-2707`
  - `core/state_store.py:3207-3209`

### Rejeições Explícitas

- Rejeitado: checkout em `.cerebro/worktrees/<nome>/`
- Rejeitado: `state.json` canônico compartilhado entre worktrees nesta fase
- Rejeitado: sessão compartilhada entre worktrees
- Rejeitado: aceitar nome de worktree via `Path.resolve()` sem saneamento específico

## Contrato Mínimo

- `worktree create <nome>` deve aceitar apenas slug estrito.
- Proibidos no `nome`: vazio, `/`, `\`, `..`, path absoluto e qualquer segmento que escape do diretório `.worktrees/`.
- O registro central ficará em `.cerebro/worktrees.toml`.
- O branch padrão será `worktree-<nome>`.
- O spawn paralelo usará `--project-root <repo>/.worktrees/<nome>`.
- Não haverá merge automático; a fase 5 apenas registra diff/branch/status para revisão supervisionada.

## Fatias

### Fatia 1 — `cerebro worktree create <nome>`

- Status: `concluída`
- Implementada em: `2026-04-18`

- Objetivo:
  - criar branch `worktree-<nome>`
  - criar checkout em `.worktrees/<nome>/`
  - registrar entrada em `.cerebro/worktrees.toml`
- Áreas tocadas:
  - `cli/main.py`
  - `cli/worktree_registry.py`
  - `cli/commands/worktree.py`
  - `.gitignore`
  - `tests/test_cli.py`
  - `tests/test_architecture.py`
- Registro esperado no TOML:
  - `name`
  - `path`
  - `branch`
  - `created_at`
  - `status = "active"`
- Critério de pronto:
  - diretório do worktree existe — `confirmado`
  - branch existe — `confirmado`
  - entrada existe em `.cerebro/worktrees.toml` — `confirmado`
  - nome inválido falha fechado — `confirmado`
  - criação duplicada falha fechado — `confirmado`
- Teste mínimo:
  - criar worktree com nome válido — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_creates_git_worktree_and_registry_entry`
  - rejeitar `..`, `/`, `\`, absoluto e vazio — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_rejects_invalid_name`
  - validar que `--project-root` aponta corretamente para o worktree criado — `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_explicit_project_root_to_worktree_handler`
  - rejeitar criação duplicada — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_fails_closed_when_name_is_already_registered`
  - rollback completo quando a persistência do registry falha — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_cleans_up_when_registry_persist_fails`
  - falha parcial de cleanup fica explícita quando o rollback do branch falha — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_reports_cleanup_failure_when_registry_persist_fails`
  - teste manual de worktree real em `.worktrees/test-wt` — `executado`

### Fatia 2 — `cerebro worktree list`

- Status: `concluída`
- Implementada em: `2026-04-18`
- Objetivo:
  - listar worktrees registrados e reconciliá-los com `git worktree list --porcelain`
  - expor divergência operacional em vez de esconder stale registry entries
- Áreas tocadas:
  - `cli/main.py`
  - `cli/commands/worktree.py`
  - `cli/worktree_registry.py`
  - `tests/test_cli.py`
- Critério de pronto:
  - lista `name`, `path`, `branch`, `status` — `confirmado`
  - distingue `active`, `missing` e `unregistered` sem fallback silencioso — `confirmado`
  - falha fechado quando o Git não consegue listar worktrees — `confirmado`
  - falha fechado quando o registry local mente sobre `name/path` — `confirmado`
  - resolve o root administrativo do repositório principal mesmo quando invocado de dentro de um worktree filho — `confirmado`
- Teste mínimo:
  - saída textual para worktree ativo — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_reports_active_registered_entry`
  - saída textual para registro ausente no Git — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_reports_missing_registered_entry`
  - saída textual para worktree unregistered com `detached HEAD` — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_reports_unregistered_detached_entry`
  - falha fechada se `git worktree list` falhar — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_fails_closed_when_git_listing_fails`
  - falha fechada se `name` divergir do basename do `path` no registry — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_fails_closed_when_registry_name_does_not_match_path`
  - invocação a partir do worktree filho ainda usa o admin root central — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_uses_admin_root_when_invoked_from_child_worktree`
  - teste manual real: create + list a partir do worktree filho + cleanup — `executado`

### Fatia 3 — `cerebro worktree clean <nome>`

- Status: `concluída`
- Implementada em: `2026-04-18`
- Objetivo:
  - remover worktree e branch `worktree-<nome>`
  - atualizar `.cerebro/worktrees.toml`
- Áreas tocadas:
  - `cli/main.py`
  - `cli/commands/worktree.py`
  - `cli/worktree_registry.py`
  - `tests/test_cli.py`
- Sequência mínima:
  - validar registro
  - recusar clean se houver mudanças pendentes
  - executar `git worktree remove <path>`
  - remover branch apenas após sucesso
  - remover entrada do TOML apenas após sucesso consistente
- Critério de pronto:
  - diretório removido — `confirmado`
  - branch removida — `confirmado`
  - TOML não mente após falha parcial — `confirmado`
  - `clean` falha fechado se Git e registry divergirem sobre a entry alvo — `confirmado`
- Testes de pronto:
  - remove worktree, branch e entrada do registry com sucesso — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_removes_worktree_branch_and_registry_entry`
  - bloqueia `clean` em worktree sujo — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_blocks_dirty_worktree`
  - preserva registry quando `git branch -D` falha — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_keeps_registry_when_branch_delete_fails`
  - rerun conclui a limpeza quando o checkout já foi removido antes do delete da branch — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_recovers_when_checkout_was_removed_before_branch_delete`
  - rerun conclui a limpeza quando a persistência do registry falha após a limpeza física — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_recovers_when_registry_persist_fails_after_physical_cleanup`
  - falha fechado para registry adulterado tanto com checkout removido quanto ativo — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_fails_closed_when_removed_checkout_has_tampered_branch`, `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_fails_closed_when_active_worktree_has_tampered_branch`
  - usa admin root central quando invocado do worktree filho — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_uses_admin_root_when_invoked_from_child_worktree`
  - falha fechado quando a entry do registry ficou stale em relação ao Git — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_fails_closed_when_registry_entry_is_stale`
  - invocação a partir do worktree filho ainda usa o admin root central — `confirmado`
- Teste mínimo:
  - clean bem-sucedido — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_removes_worktree_branch_and_registry_entry`
  - clean bloqueado por dirty worktree — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_blocks_dirty_worktree`
  - falha parcial mantém registro coerente quando o delete da branch falha — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_keeps_registry_when_branch_delete_fails`
  - invocação a partir do worktree filho usa o admin root central — `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_uses_admin_root_when_invoked_from_child_worktree`
  - teste manual real: create + clean + list final vazio — `executado`

### Fatia 4 — spawn em worktree isolado

- Status: `concluída`
- Implementada em: `2026-04-18`
- Objetivo:
  - despachar execução paralela externa para worktrees registrados com `--project-root` apontando para `.worktrees/<nome>`
- Áreas tocadas:
  - `_local/automation_bridge/run_parallel_worktrees.py`
  - `_local/automation_bridge/test_run_bridge.py`
  - `_local/automation_bridge/README.md`
  - `docs/operations/WORKTREE_PLAN.md`
  - `docs/operations/IMPLEMENTATION_STATUS.md`
- Limite desta fatia:
  - launcher externo apenas; nenhum scheduler embutido no produto rastreado
  - isolamento por worktree via `--project-root`
  - sem lock compartilhado entre worktrees
  - sem sessão compartilhada entre worktrees
  - worktree precisa já existir no Git e já ter `.cerebro/state.json` próprio
- Critério de pronto:
  - dois despachos paralelos recebem roots distintos — `confirmado`
  - cada worktree materializa `.cerebro/` próprio antes do dispatch — `confirmado`
  - launcher falha fechado para worktree não registrado, stale ou não inicializado — `confirmado`
  - boundary continua externo a `cli/`, `core/` e ao scheduler do runtime — `confirmado`
- Teste mínimo:
  - dispatch paralelo para dois worktrees inicializados — `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_launch_child_bridge_runs_with_distinct_roots`
  - falha fechada para worktree sem `.cerebro/state.json` — `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_fail_closed_when_target_is_not_initialized`
  - falha fechada para registry stale quando o Git já não lista o worktree — `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_fail_closed_when_registered_worktree_is_missing_from_git`
  - falha fechada para branch Git divergente do registry — `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_fail_closed_when_registered_worktree_branch_diverges`
  - teste manual: criar dois worktrees, inicializar ambos, executar `run_parallel_worktrees.py` com executor fake e confirmar run dirs distintos — `executado`

### Fatia 5 — merge supervisionado

- Status: `concluída`
- Implementada em: `2026-04-18`
- Objetivo:
  - produzir evidência explícita de `diff`, `branch`, `HEAD` e `merge-base` antes de qualquer merge manual
- Áreas tocadas:
  - `_local/automation_bridge/review_worktree.py`
  - `_local/automation_bridge/test_run_bridge.py`
  - `_local/automation_bridge/README.md`
  - `docs/operations/WORKTREE_PLAN.md`
  - `docs/operations/IMPLEMENTATION_STATUS.md`
- Critério de pronto:
  - não existe caminho de merge automático no produto rastreado — `confirmado`
  - a revisão fica explícita como saída derivada `pending_manual_merge`, não como estado persistido — `confirmado`
  - worktree dirty bloqueia a revisão — `confirmado`
  - branch, `HEAD`, `merge-base` e diff ficam visíveis ao operador antes do merge manual — `confirmado`
- Teste mínimo:
  - revisão read-only exibe `branch`, `HEAD` e diff — `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_review_worktree_reports_branch_head_and_diffstat`
  - revisão falha fechada quando o worktree está dirty — `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_review_worktree_fails_closed_when_worktree_is_dirty`
  - revisão falha fechada quando o worktree está `detached` — `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_review_worktree_fails_closed_when_worktree_is_detached`
  - merge continua manual por desenho; nenhum executor de merge foi adicionado — `confirmado por inspeção`

## Ordem De Esforço

1. Fatia 1 — create
2. Fatia 2 — list
3. Fatia 3 — clean
4. Fatia 4 — spawn isolado
5. Fatia 5 — merge supervisionado

## Riscos Confirmados

- Boundary incorreto se o checkout ficar dentro de `.cerebro/`
  - `core/state_store.py:121-130`
  - `core/action_runtime.py:889-903`
- `runtime.lock` não coordena worktrees com roots distintos
  - `core/state_store.py:129`
  - `core/state_store.py:4967-5000`
- `root_sha256` não serve para sessão compartilhada entre worktrees
  - `core/state_store.py:2705-2707`
  - `core/state_store.py:3207-3209`
- `resolve()` sozinho não protege nome/path de worktree contra desenho inseguro
  - `cli/main.py:117-123`

## Riscos Descartados

- Refatorar `StateStore` para aceitar `root` explícito
  - descartado; já aceita em `core/state_store.py:121-123`
- Refatorar o despacho principal da CLI para suportar root alternativo
  - descartado; já existe em `cli/main.py:450-453`

## Próxima Fatia

- `nenhuma — encerramento formal concluído`
