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

## Fatia atual

- Qual é: `FATIA 2 — Menu de contexto ao abrir`
- Estado: `concluída`

## Próxima fatia

- Qual é: `FATIA 3 — Registro de projetos`
- Dependências:
  - `FATIA 1` concluída com `cwd` default preservado
  - `FATIA 2` concluída com menu fino reaproveitando `analyze` e `--project-root`
  - memória externa alinhada em `MIGRATION_PLAN.md`

## Itens em Grupo 6

- Nenhum nesta trilha de implementação até o momento.
