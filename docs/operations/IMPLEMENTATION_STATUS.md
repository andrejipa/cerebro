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

## Fatia atual

- Qual é: `FATIA 1 — --project-root global em cli/main.py`
- Estado: `concluída`

## Próxima fatia

- Qual é: `FATIA 2 — Menu de contexto ao abrir`
- Dependências:
  - `FATIA 1` concluída com `cwd` default preservado
  - parser global já aceita root explícito antes e depois do subcomando
  - memória externa atualizada em `MIGRATION_PLAN.md`

## Itens em Grupo 6

- Nenhum nesta trilha de implementação até o momento.
