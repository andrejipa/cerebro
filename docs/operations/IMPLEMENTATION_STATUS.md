# Implementation Status — External Cerebro Model

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
