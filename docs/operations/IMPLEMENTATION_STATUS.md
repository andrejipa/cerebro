# Implementation Status — External Cerebro Model

## Current Live Gate — 2026-04-22

- Suite gate: `759` tests, `0` failures, `6` skips via the exact AGENTS-equivalent workspace-local-temp runner
- Architecture gate: `51` tests, `0` failures
- Derived `recall_eval` gate: `49` tests, `0` failures in `experiments/recall_eval/tests`
- Derived `operational_signals` base gate: `31` tests, `0` failures in `experiments/operational_signals/tests`
- Derived `operational_signals/suggestions` gate: `97` tests, `0` failures in `experiments/operational_signals/suggestions/tests`
- Canonical-runtime posture: deliberate freeze remains active for new core capability growth
- Canonical-runtime status: gate green; raw digest primitives now converge in `core/digests.py` with direct regression coverage, Slice 2 now routes the read-model trio through `core/state_read_model_service.py` behind the unchanged `StateStore` facade, and the current user-directed session is continuing through the mapped StateStore sequence with Slice 3
- Derived-track posture:
  - `experiments/recall_eval/` has been implemented and benchmarked against real corpora; it remains experimental, derived, and not promoted
  - `experiments/operational_signals/` has been implemented and is ready for opt-in derived use; its initial registry is currently empty, which is the correct state until real insufficiency signals are observed

The per-slice suite counts recorded below remain historical implementation evidence from the moment each slice closed. They do not replace the live suite gate above or the AGENTS-equivalent runner authority for this shell.

## Hardening Arquitetural — Grupo 6

- Estado do Grupo 6: `encerrado`
- Prova de parada: `P1-P5` limpa em `2026-04-19`
- Próximo passo: `nenhum para o runtime canônico — operar sob freeze; trilhas derivadas aprovadas permanecem externas e não autoritativas`

- Débito 3: `verify` host-trusting
  - Estado: `fechado`
  - Fechado em: `2026-04-19`
  - Arquivos alterados:
    - `core/verification_runtime.py:24-37`
    - `core/verification_runtime.py:66-80`
    - `core/verification_runtime.py:83-97`
    - `core/verification_runtime.py:100-125`
    - `core/verification_runtime.py:128-182`
    - `tests/test_alpha_runtime.py:963-1086`
    - `tests/test_alpha_runtime.py:1088-1150`
    - `tests/test_alpha_runtime.py:1152-1210`
  - Critério satisfeito: `sim`
  - Evidência:
    - `verify` não herda mais o `PATH` completo do host; o subprocesso usa `PATH` mínimo reconstruído a partir do comando resolvido
    - `stdout/stderr` continuam redigidos antes da persistência, inclusive por segmento de `PATH`
    - regressões cobrem leak de env, helper chain mínima via comando resolvido e preservação de `C:` legítimo

- Débito 2: `check-state` sintético
  - Estado: `fechado`
  - Fechado em: `2026-04-19`
  - Arquivos alterados:
    - `core/agent_runtime.py:481-525`
    - `core/validation.py:696-734`
    - `core/validation.py:1025-1031`
    - `core/verification_runtime.py:363-383`
    - `core/verification_runtime.py:471-525`
    - `cli/commands/verify.py:45-92`
    - `core/state_store.py:1722`
    - `core/state_store.py:4261-4299`
    - `core/memory_runtime.py:109-111`
    - `extensions/status_export/exporter.py:185-187`
    - `core/__init__.py:3-15`
    - `tests/test_verification_runtime.py:65-121`
    - `tests/test_alpha_runtime.py:633-650`
    - `tests/test_alpha_runtime.py:2096-2109`
    - `tests/test_state_store.py:388-462`
    - `tests/test_validate.py:108-201`
  - Critério satisfeito: `sim`
  - Evidência:
    - `verification.state_check` agora persiste preflight explicitamente
    - `verification.checks` voltou a conter apenas checks de comando
    - legado `gate == "state"` migra automaticamente na canonicalização
    - `python -m unittest discover -s tests -v` -> `696` testes, `0` falhas, `6` skips
    - `python -m unittest tests.test_architecture -v` -> `51` testes, `0` falhas

- Débito 1: `approval` por efeito em `overwrite=true`
  - Estado: `fechado`
  - Fechado em: `2026-04-19`
  - Arquivos alterados:
    - `core/execution_policy.py:73-126`
    - `cli/commands/apply.py:178-230`
    - `cli/commands/apply.py:409-436`
    - `cli/commands/rollback.py:60-77`
    - `core/validation.py:975-981`
    - `tests/test_execution_policy.py:58-70`
    - `tests/test_alpha_runtime.py:2529-2553`
    - `tests/test_alpha_runtime.py:4105-4169`
    - `tests/test_validation_approval_guards.py:51-68`
    - `tests/test_validate.py:411-434`
  - Critério satisfeito: `sim`
  - Evidência:
    - approval agora depende do efeito destrutivo real ou projetado, não apenas do `kind`
    - overwrite destrutivo real e batch `create -> overwrite` agora retornam `approval_required` antes da mutação
    - `create` benigno continua livre
    - `validate` e `rollback` reaplicam o mesmo contrato sobre o histórico persistido
    - `python -m unittest discover -s tests -v` -> `700` testes, `0` falhas, `6` skips
    - `python -m unittest tests.test_architecture -v` -> `51` testes, `0` falhas

## Auditoria Pós-Hardening — 2026-04-19

- Estado: `encerrada`
- Prova de parada: `limpa`
- Próximo passo: `nenhum para o runtime canônico — operar sob freeze; trilhas derivadas aprovadas permanecem externas e não autoritativas`

- Correção 1: `approval-by-effect` reaplicado no boundary direto do core
  - Estado: `fechado`
  - Arquivos alterados:
    - `core/action_runtime.py:179-187`
    - `core/action_runtime.py:755-825`
    - `tests/test_action_runtime.py:299-339`
    - `tests/test_execution_policy.py:62-172`
  - Critério satisfeito: `sim`
  - Evidência:
    - `apply_action()` volta a exigir approval para mutações governadas mesmo sem o preflight do CLI
    - `fs.create_file overwrite=true` e `fs.move` destrutivos falham fechados quando chamados diretamente
    - `create` benigno em alvo ausente continua livre

- Correção 2: `verify` live-project guard + restore pristino
  - Estado: `fechado`
  - Arquivos alterados:
    - `core/verification_runtime.py:57-108`
    - `core/verification_runtime.py:450-599`
    - `tests/test_alpha_runtime.py:1025-1080`
    - `tests/test_alpha_runtime.py:1082-1136`
  - Critério satisfeito: `sim`
  - Evidência:
    - `verify` falha fechado quando um comando tenta escrever no workspace real fora do sandbox
    - o restore usa clone pristino separado do sandbox de execução, impedindo restore envenenado
    - o conteúdo vivo é restaurado antes da finalização do resultado `failed`

- Suite da auditoria:
  - `python -m unittest discover -s tests -v` -> `704` testes, `0` falhas, `6` skips
  - `python -m unittest tests.test_architecture -v` -> `51` testes, `0` falhas

## Fatias concluídas

- Fatia 1: `--project-root` global
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/main.py:32-57`
    - `cli/main.py:320-322`
    - `cli/commands/plan.py:105`
    - `cli/commands/_plan_input.py:11-61`
    - `tests/test_cli.py:224-344`
    - `tests/test_alpha_runtime.py:199-225`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_current_working_directory_by_default`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_explicit_project_root_to_handlers`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_accepts_explicit_project_root_after_subcommand`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_plan_uses_explicit_project_root_for_relative_input_file`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_bootstrap_scan_root_argument_overrides_global_project_root`
    - `tests.test_alpha_runtime.AlphaRuntimeTests.test_plan_command_resolves_relative_input_file_from_root_instead_of_process_cwd`
  - Critério de pronto: `sim`

- Fatia 2: `Menu de contexto ao abrir`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/main.py:32-55`
    - `cli/main.py:344-355`
    - `tests/test_cli.py:286-385`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_opens_context_menu_and_dispatches_development_mode`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_none_uses_process_argv_for_context_menu_dispatch`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_opens_context_menu_and_dispatches_managed_project_mode`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_fails_closed_for_invalid_context_menu_selection`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_fails_closed_for_blank_project_root`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_fails_closed_when_terminal_is_unavailable`
  - Critério de pronto: `sim`

- Fatia 3: `Registro de projetos`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/project_registry.py:1-140`
    - `cli/main.py:33-92`
    - `tests/test_cli.py:345-541`
    - `docs/operations/MIGRATION_PLAN.md:1-129`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_opens_context_menu_and_dispatches_managed_project_mode`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_lists_registered_projects_and_dispatches_selected_project`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_without_argv_fails_closed_when_project_registry_is_invalid`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_project_registry_serializes_concurrent_updates`
  - Critério de pronto: `sim`

- Fatia 4: `Dashboard de estado ao abrir`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/project_dashboard.py:1-143`
    - `cli/main.py:391-403`
    - `tests/test_cli.py:293-326`
    - `tests/test_cli.py:355-383`
    - `tests/test_cli.py:553-683`
    - `docs/operations/MIGRATION_PLAN.md:1-137`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_explicit_analyze_does_not_render_open_dashboard`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_render_open_dashboard_reads_operational_summary_and_initialized_project_state`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_render_open_dashboard_reports_not_initialized_when_project_has_no_state`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_render_open_dashboard_treats_invalid_doc_encoding_as_unknown`
  - Critério de pronto: `sim`

- Fatia 5: `cerebro doctor`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/commands/doctor.py:1-246`
    - `cli/main.py`
    - `tests/test_cli.py`
    - `tests/test_doctor.py:1-115`
    - `tests/test_architecture.py`
    - `docs/operations/MIGRATION_PLAN.md`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_doctor_help_declares_read_only_diagnostic_role`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_current_working_directory_to_doctor_by_default`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_explicit_project_root_to_doctor_handler`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_explicit_doctor_does_not_dispatch_analyze`
    - `tests.test_doctor.DoctorCommandTests.test_run_doctor_reports_initialized_project_without_mutating_state`
    - `tests.test_doctor.DoctorCommandTests.test_run_doctor_reports_missing_state_without_creating_runtime_files`
    - `tests.test_doctor.DoctorCommandTests.test_run_doctor_returns_non_zero_when_a_critical_check_fails`
    - `tests.test_doctor.DoctorCommandTests.test_run_doctor_fails_closed_when_repo_suite_is_unavailable`
    - `tests.test_architecture.ArchitectureIsolationTests.test_doctor_command_remains_read_only`
  - Critério de pronto: `sim`

- Fatia 6: `Commit automático por iteração`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/commands/iteration_commit.py`
    - `cli/main.py`
    - `tests/test_iteration_commit.py`
    - `tests/test_cli.py`
    - `tests/test_architecture.py`
    - `docs/operations/MIGRATION_PLAN.md`
  - Testes adicionados:
    - `tests.test_iteration_commit.IterationCommitCommandTests.test_run_iteration_commit_generates_commit_with_documented_message`
    - `tests.test_iteration_commit.IterationCommitCommandTests.test_run_iteration_commit_fails_closed_when_index_is_not_clean`
    - `tests.test_iteration_commit.IterationCommitCommandTests.test_run_iteration_commit_unstages_selection_when_commit_fails`
    - `tests.test_iteration_commit.IterationCommitCommandTests.test_build_iteration_commit_rejects_paths_outside_repo`
    - `tests.test_iteration_commit.IterationCommitCommandTests.test_build_commit_message_falls_back_to_last_completed_fatia`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_iteration_commit_help_declares_generated_commit_role`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_current_working_directory_to_iteration_commit_handler`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_explicit_project_root_to_iteration_commit_handler`
  - Critério de pronto: `sim`

## Fatia atual

- Qual é: `FATIA 6 — Commit automático por iteração`
- Estado: `concluída`

## Próxima fatia

- Qual é: `nenhuma — prova de parada e encerramento formal`
- Dependências:
  - `FATIAS 1-6` concluídas
  - suíte completa verde
  - `tests.test_architecture` verde
  - memória externa alinhada em `MIGRATION_PLAN.md`

## Itens em Grupo 6

- Nenhum nesta trilha de implementação até o momento.

## Trilha Worktrees

### Fatias concluídas

- Fatia 1: `cerebro worktree create <nome>`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `.gitignore`
    - `cli/main.py`
    - `cli/worktree_registry.py`
    - `cli/commands/worktree.py`
    - `tests/test_cli.py`
    - `tests/test_architecture.py`
    - `docs/operations/WORKTREE_PLAN.md`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_help_declares_isolated_git_role`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_current_working_directory_to_worktree_handler`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_main_dispatches_explicit_project_root_to_worktree_handler`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_creates_git_worktree_and_registry_entry`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_rejects_invalid_name`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_fails_closed_when_name_is_already_registered`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_cleans_up_when_registry_persist_fails`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_create_reports_cleanup_failure_when_registry_persist_fails`
  - Teste de worktree:
    - comando real `git worktree add .worktrees/test-wt -b worktree-test-wt` executado com sucesso
    - suíte dentro do worktree executada sobre o `HEAD` commitado (`Ran 164 tests ... / OK`), que é o limite natural de um worktree criado a partir de um workspace ainda sem commit desta iteração
  - Critério de pronto: `sim`

- Fatia 2: `cerebro worktree list`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/main.py`
    - `cli/commands/worktree.py`
    - `cli/worktree_registry.py`
    - `tests/test_cli.py`
    - `docs/operations/WORKTREE_PLAN.md`
    - `docs/operations/IMPLEMENTATION_STATUS.md`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_reports_active_registered_entry`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_reports_missing_registered_entry`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_reports_unregistered_detached_entry`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_fails_closed_when_git_listing_fails`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_fails_closed_when_registry_name_does_not_match_path`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_list_uses_admin_root_when_invoked_from_child_worktree`
  - Teste de worktree:
    - `python -m cli.main --project-root . worktree create codex-fat2-admin-check` — `OK`
    - `python -m cli.main --project-root .worktrees/codex-fat2-admin-check worktree list` — `OK`
    - `git worktree remove --force .worktrees/codex-fat2-admin-check` + `git branch -D worktree-codex-fat2-admin-check` — `OK`
  - Critério de pronto: `sim`

- Fatia 3: `cerebro worktree clean <nome>`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `cli/main.py`
    - `cli/commands/worktree.py`
    - `cli/worktree_registry.py`
    - `tests/test_cli.py`
    - `docs/operations/WORKTREE_PLAN.md`
    - `docs/operations/IMPLEMENTATION_STATUS.md`
  - Testes adicionados:
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_removes_worktree_branch_and_registry_entry`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_blocks_dirty_worktree`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_keeps_registry_when_branch_delete_fails`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_recovers_when_checkout_was_removed_before_branch_delete`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_recovers_when_registry_persist_fails_after_physical_cleanup`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_fails_closed_when_removed_checkout_has_tampered_branch`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_fails_closed_when_active_worktree_has_tampered_branch`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_uses_admin_root_when_invoked_from_child_worktree`
    - `tests.test_cli.CliHelpAndExitCodeTests.test_worktree_clean_fails_closed_when_registry_entry_is_stale`
  - Teste de worktree:
    - `python -m cli.main --project-root . worktree create codex-fat3-check` — `OK`
    - `python -m cli.main --project-root . worktree clean codex-fat3-check` — `OK`
    - `python -m cli.main --project-root . worktree list` — `worktrees: 0`
  - Critério de pronto: `sim`

- Fatia 4: `spawn em worktree isolado`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `_local/automation_bridge/run_parallel_worktrees.py`
    - `_local/automation_bridge/test_run_bridge.py`
    - `_local/automation_bridge/README.md`
    - `docs/operations/WORKTREE_PLAN.md`
    - `docs/operations/IMPLEMENTATION_STATUS.md`
  - Testes adicionados:
    - `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_launch_child_bridge_runs_with_distinct_roots`
    - `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_fail_closed_when_target_is_not_initialized`
    - `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_fail_closed_when_registered_worktree_is_missing_from_git`
    - `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_parallel_worktrees_fail_closed_when_registered_worktree_branch_diverges`
  - Teste de worktree:
    - criação real de dois worktrees temporários — `OK`
    - `init` real em cada worktree — `OK`
    - `python _local/automation_bridge/run_parallel_worktrees.py ... --worktree alpha --worktree beta ...` com executor fake — `OK`
  - Critério de pronto: `sim`

- Fatia 5: `merge supervisionado`
  - Implementada em: `2026-04-18`
  - Arquivos alterados:
    - `_local/automation_bridge/review_worktree.py`
    - `_local/automation_bridge/test_run_bridge.py`
    - `_local/automation_bridge/README.md`
    - `docs/operations/WORKTREE_PLAN.md`
    - `docs/operations/IMPLEMENTATION_STATUS.md`
  - Testes adicionados:
    - `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_review_worktree_reports_branch_head_and_diffstat`
    - `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_review_worktree_fails_closed_when_worktree_is_dirty`
    - `_local.automation_bridge.test_run_bridge.AutomationBridgeTests.test_review_worktree_fails_closed_when_worktree_is_detached`
  - Teste de worktree:
    - criação real de worktree temporário com commit próprio — `OK`
    - `python _local/automation_bridge/review_worktree.py --repo-root ... --worktree alpha` — `OK`
    - revisão dirty bloqueada explicitamente — `OK`
  - Critério de pronto: `sim`

### Fatia atual

- Qual é: `nenhuma — encerrado`
- Estado: `concluída`

### Próxima fatia

- Qual é: `nenhuma — worktrees implementados`
- Dependências:
  - `FATIAS 1-5` concluídas
  - P2 limpo
  - suíte e arquitetura verdes

### Itens em Grupo 6 — Worktrees

- Nenhum nesta trilha até o momento.

## Auditoria De Worktrees — 2026-04-19

- Estado: `encerrada`
- Testes: `688 -> 694`
- Riscos confirmados e corrigidos:
  - `RISCO 1` + `RISCO 7` — serialização do `create_worktree` sob boundary único de registry lock.
    Evidência:
    [cli/commands/worktree.py](</D:/projetos_cli/cerebro/cli/commands/worktree.py:95>),
    [cli/worktree_registry.py](</D:/projetos_cli/cerebro/cli/worktree_registry.py:98>),
    [tests/test_cli.py](</D:/projetos_cli/cerebro/tests/test_cli.py:1631>),
    [tests/test_cli.py](</D:/projetos_cli/cerebro/tests/test_cli.py:1685>).
  - `RISCO 2` — recovery fail-closed de estado não registrado no `clean_worktree`.
    Evidência:
    [cli/commands/worktree.py](</D:/projetos_cli/cerebro/cli/commands/worktree.py:163>),
    [cli/commands/worktree.py](</D:/projetos_cli/cerebro/cli/commands/worktree.py:393>),
    [tests/test_cli.py](</D:/projetos_cli/cerebro/tests/test_cli.py:1719>),
    [tests/test_cli.py](</D:/projetos_cli/cerebro/tests/test_cli.py:1736>).
  - `RISCO 6` — regressão direta para falha de `git worktree add`, sem fallback para `main`.
    Evidência:
    [cli/commands/worktree.py](</D:/projetos_cli/cerebro/cli/commands/worktree.py:125>),
    [tests/test_cli.py](</D:/projetos_cli/cerebro/tests/test_cli.py:1606>).
- Riscos limpos:
  - `RISCO 3`, `RISCO 4`, `RISCO 5`.
- Teste manual:
  - `python -m cli.main --project-root D:\\projetos_cli\\cerebro worktree create audit-test` -> `list` -> `clean` — `OK`
- Timeouts:
  - `DEBATE 2 architect/mediator` — `TIMEOUT`; relançado serial e encerrado com os achados confirmados.
- Decisão final:
  - `AUDITORIA DE WORKTREES CONCLUÍDA. Sistema em estado operacional.`
