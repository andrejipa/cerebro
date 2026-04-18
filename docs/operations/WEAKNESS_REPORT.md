# Weakness Report

## Resumo executivo

 O Cerebro está operacionalmente estável e a suíte principal segue verde, mas a auditoria ainda confirma riscos técnicos abertos no runtime. Com o fechamento nesta sessão do guard de monotonicidade em `save_state()`, do preflight de posse em `verify`, do branch de falha em `prepare_project_sandbox()`, do residual de rollback em `fs.move` e agora também do residual `create-new` em `fs.create_file`, os `ALTO` abertos mais graves ficaram concentrados na lacuna de policy em `fs.create_file` com `overwrite=true`, que ainda consegue mutar um arquivo existente sem approval porque o gate continua decidido por `kind`, não por efeito destrutivo observável, e no sentinel sintético `check-state`, que segue contaminando `verification.checks` e já depende de decisão arquitetural para sair do formato persistido. Fora disso, a base mostra um padrão claro de dívida concentrada: `StateStore` supercarregado, contratos implícitos entre módulos, um boundary host-trusting em `verify` no nível de ambiente herdado e artifacts, e cobertura forte nos fluxos principais mas desigual em alguns helpers e cenários de bootstrap/corrupção.

## Achados confirmados pelos debates

### CRÍTICO

- Nenhum item `CRÍTICO` aberto.
  Fechamento desta sessão:
  o gap pós-mutação de `exec.command` foi fechado em
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:148>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:839>)
  e cristalizado por
  [tests/test_action_runtime.py](</d:/projetos_cli/cerebro/tests/test_action_runtime.py:95>).
  O runtime agora converte falha de persistência de `stdout.txt`/`stderr.txt` em `action_record` canônico com `status == "failed"`, sem deixar o CLI cair em `internal_error`.

### ALTO

- Fechamento desta sessão: `_save_state_with_refreshed_session()` agora grava um journal local `session.refresh.pending.json`, restaura o sidecar anterior quando o crash acontece antes do commit de `state.json` e finaliza journals remanescentes na próxima validação sem relaxar `session_revision_invalid`.
  Evidência do fechamento:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3312>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3507>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3542>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3664>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:1809>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:1869>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1060>).
  Debate que confirmou: oponente falsificou o reorder isolado porque ele só espelha o split e continua batendo em `session_revision_invalid`; a correção vencedora foi `journal + early recovery` local no `StateStore`, ainda sem tocar `core/validation.py`.

- Fechamento desta sessão: `session-discard` agora limpa o resíduo estreito em que o registro canônico da sessão sobrevive, mas `session.local.json` já não existe.
  Evidência do fechamento:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1221>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1355>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:2178>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1157>).
  Oponente falsificou a solução de reordenar `open_session()` porque ela reabria o bug inverso `session_not_registered`; a correção vencedora manteve a ordem canônica atual e abriu só o caminho explícito de recovery para `registry active + session.local.json ausente`, sem alterar o comportamento de `session_absent` puro.

- Fechamento desta sessão: `verify` agora converte falha de persistência de `*.stdout.txt`/`*.stderr.txt` depois do subprocesso em `verification_record` canônico `failed`, limpa artifacts parciais, registra `verify_failed` com `reason_code=command_artifact_persistence_exception` e responde `verification_failed` sem cair em `internal_error`.
  Evidência do fechamento:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:108>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:137>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:286>),
  [cli/commands/verify.py](</d:/projetos_cli/cerebro/cli/commands/verify.py:92>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:16>).
  Debate que confirmou: a varredura proativa encontrou o vazamento cru em `core/verification_runtime.py:240-243`; a oposição não falsificou o bug e a menor correção segura reaplicou em `verify` o padrão consolidado em `apply`: falhar fechado, auditar, persistir o record canônico e nunca deixar `OSError` cru escapar.

- Fechamento desta sessão: `verify` agora traduz o deny-path de policy (`ExecutionPolicyError`) em `VerificationRuntimeError` local ao runtime, então planos em `A0/A1` respondem `verification_failed` com mensagem explícita em vez de cair no fallback `internal_error`.
  Evidência do fechamento:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:248>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:250>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:17>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:618>).
  Debate que confirmou: a varredura proativa confirmou o bug no fluxo real de `verify`, a oposição não falsificou o deny-path e o mediador aprovou o menor patch no boundary do runtime, sem tocar `core/validation.py` nem o contrato persistido.

- Fechamento desta sessão: `save_state()` agora falha fechado quando o payload tenta persistir `revision` menor do que a revisão já canônica em disco, mesmo se `expected_revision` ainda coincidir com o estado atual.
  Evidência do fechamento:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:971>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:981>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:1366>).
  Debate que confirmou: o rollout principal reproduziu `0 -> 1 -> 0` diretamente no boundary canônico; a alternativa de deixar a monotonicidade apenas nos chamadores foi descartada porque mantinha o downgrade possível no nível mais baixo de persistência.

- `approval_required_kinds` continua operando por `kind`, então `fs.create_file` com `overwrite=true` ainda consegue sobrescrever um arquivo existente sem `approval_id`, embora o efeito físico seja destrutivo para o conteúdo anterior.
  Evidência:
  [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:204>),
  [core/execution_policy.py](</d:/projetos_cli/cerebro/core/execution_policy.py:54>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:147>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:608>).
  Debate que confirmou: a falsificação adversarial derrubou a leitura de “bypass acidental” porque a policy atual é explicitamente por `kind`, mas não falsificou o risco operacional por efeito. A reprodução direta desta rodada sobrescreveu `draft.txt` com `overwrite=true`, `approval_id == ""` e `approval_count == 0`.
  Status atual: a menor correção segura cruza [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:947>), então este item saiu da trilha corretiva imediata e ficou bloqueado para `Grupo 6` até decisão arquitetural explícita.

- `verification.checks` continua misturando o sentinel sintético `check-state` com checks reais de comando, então CLI, `StateStore`, memória e extensões já precisam filtrar `gate == "command"` para reconstruir o contrato operacional real.
  Evidência:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:184>),
  [cli/commands/verify.py](</d:/projetos_cli/cerebro/cli/commands/verify.py:54>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4186>),
  [core/memory_runtime.py](</d:/projetos_cli/cerebro/core/memory_runtime.py:108>),
  [extensions/status_export/exporter.py](</d:/projetos_cli/cerebro/extensions/status_export/exporter.py:185>).
  Debate que confirmou: oponente não falsificou a contaminação do contrato, apenas observou que os filtros atuais limitam parte do dano.
  Status atual: a menor correção segura cruza o formato persistido de `verification`, `cli/commands/verify.py`, `core/state_store.py`, `core/memory_runtime.py` e `extensions/status_export/exporter.py`, então este item ficou bloqueado para `Grupo 6` até decisão arquitetural explícita.

### MÉDIO

- Fechamento desta sessão: o teste isolado de `open_session()` com falha na gravação final de `session.local.json` agora sandboxa `CEREBRO_SESSION_CLAIMS_DIR` e `CEREBRO_SESSION_LIVE_PROOFS_DIR` em diretórios temporários explícitos, então a comparação before/after deixou de depender do storage externo compartilhado do usuário.
  Evidência do fechamento:
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:1692>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:1998>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:2550>).
  Prova operacional: o rerun isolado de `StateStoreTests.test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails` ficou verde em cinco execuções consecutivas no workspace principal, e a suíte completa permaneceu verde sem tocar o runtime.

- Fechamento desta sessão: `open_session()` agora reaproveita o recovery `registry-only` quando a escrita final de `session.local.json` falha e a reversão de `state.json` também falha, então a falha dupla deixa o runtime de volta em estado válido em vez de persistir `session_registry_mismatch`.
  Evidência do fechamento:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1154>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1172>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1399>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:1732>).
  Prova operacional: a regressão nova força a sequência “`session.local.json` falha -> restore de `state.json` falha`”, recebe o erro composto esperado (`state restore failed`) e ainda assim confirma `validate_state()["ok"] == True` com claim/live-proof externos restaurados ao baseline.

- Fechamento desta sessão: `apply` single-file agora reutiliza [StateStore.read_snapshot_and_runtime()](</d:/projetos_cli/cerebro/core/state_store.py:202>) para carregar `snapshot + runtime` em um único `load_state()` antes da primeira mutação, eliminando as duas hidratações redundantes de `read_sources()` + `read_agent_runtime()` do preflight.
  Evidência:
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:266>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:279>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4394>).
  Benchmark que cristalizou: o fluxo completo de `run_apply()` single-file caiu de `6` para `4` chamadas de `load_state()`, o contador no boundary da primeira chamada a `apply_action()` caiu de `4` para `2`, e o microbenchmark sintético caiu de `20.697ms/iter` para `18.408ms/iter`.

- Fechamento desta sessão: `verify` agora executa o ciclo `validate -> run_verification_commands -> update_agent_verification` por um helper do core, então o CLI deixou de depender de `StateStore._runtime_lock()`, o preflight parou de recarregar `agent_runtime` por `read_agent_runtime()`, e o helper falha fechado se `root` e `StateStore` não apontarem para o mesmo workspace.
  Evidência:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1723>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:373>),
  [cli/commands/verify.py](</d:/projetos_cli/cerebro/cli/commands/verify.py:16>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:21>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:213>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:272>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4559>).
  Benchmark que cristalizou: o caminho feliz de `run_verify()` caiu de `4` para `3` chamadas de `load_state()`, e o contador antes do primeiro `run_verification_commands()` caiu de `2` para `1`, com custo estável de `155.864ms/iter` para `154.274ms/iter`.

- Fechamento desta sessão: `verify` agora prova a posse da sessão ativa ainda dentro da transação do core antes de disparar qualquer subprocesso, então um `session_token` ausente ou inválido falha fechado com `session_token_required` sem executar comandos nem materializar side effects fora do runtime.
  Evidência:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:385>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:389>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3456>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:285>).
  Prova operacional: a regressão nova intercepta `run_verification_commands()` e confirma que `run_verify()` retorna `1`, emite `session_token_required` e preserva `verification.status == "idle"` quando a posse da sessão não foi comprovada.

- Fechamento desta sessão: se `prepare_project_sandbox()` falha antes do primeiro comando, `verify` agora registra `verify_failed` com `reason_code=sandbox_prepare_failed` e persiste um `verification_record` canônico `failed` em vez de abortar sem trilha auditável.
  Evidência:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:138>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:241>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:244>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:347>).
  Prova operacional: a regressão nova força `prepare_project_sandbox()` a lançar `OSError`, observa `run_verify()` retornando `1`, `verification.status == "failed"` com `check-state` falho e um único evento `verify_failed` persistido no audit trail.

- Fechamento desta sessão: `rollback` de `fs.move` agora poda a árvore de destino criada pelo `apply` quando ela fica vazia após restaurar o arquivo na origem, sem tocar diretórios preexistentes nem o caso com `target_preimage_ref`.
  Evidência:
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:77>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:738>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:962>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:3049>).
  Prova operacional: a regressão nova força `draft.txt -> notes/archive/draft.txt -> rollback`, confirma a restauração do arquivo na origem e prova `notes/archive/` e `notes/` ausentes no fim do rollback.

- Fechamento desta sessão: `rollback` de `fs.create_file` no caso `create-new` agora também poda a árvore recém-criada pelo `apply` quando ela fica vazia após remover o arquivo no rollback.
  Evidência:
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:77>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:686>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:920>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:3106>).
  Prova operacional: a regressão nova força `notes/archive/draft.txt -> rollback`, confirma a remoção do arquivo e prova `notes/archive/` e `notes/` ausentes no fim do rollback.

- Fechamento desta sessão: a perda de `.cerebro/state.json` logo após `init` agora tem regressão explícita no nível do CLI, cristalizando que `validate` falha fechado com `state_missing` e orientação operacional, sem cair em `internal_error`.
  Evidência:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1723>),
  [cli/output.py](</d:/projetos_cli/cerebro/cli/output.py:28>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:888>).
  Prova operacional: a regressão nova executa `run_init()`, remove `.cerebro/state.json`, roda `run_validate(root)` e confirma `state_missing`, a mensagem `no Cerebro state found in current directory` e ausência de `internal_error`.

- Fechamento desta sessão: o runtime agora tem um teste contínuo único cobrindo `bootstrap -> validate/analyze -> plan -> apply -> verify -> rollback`, em um único fluxo com comandos reais e posse de sessão explícita.
  Evidência:
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:2185>),
  [cli/commands/analyze.py](</d:/projetos_cli/cerebro/cli/commands/analyze.py:12>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:122>),
  [cli/commands/verify.py](</d:/projetos_cli/cerebro/cli/commands/verify.py:14>),
  [cli/commands/rollback.py](</d:/projetos_cli/cerebro/cli/commands/rollback.py:82>).
  Prova operacional: a regressão nova executa `run_init()`, `run_validate()`, `run_analyze()` com emissão de `session_token`, `run_plan()`, `run_apply()`, `run_verify()` e `run_rollback()` no mesmo projeto temporário, e confirma no fim `validation_passed`, action `rolled_back`, `verification.status == "idle"` e ausência de delta residual no workspace.

- `verify` continua host-trusting: herda quase todo o ambiente do processo e persiste `stdout`/`stderr` brutos em artifacts, então comandos marcados como `read_only` ainda podem ler segredos herdados e exfiltrá-los pela trilha canônica.
  Evidência:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:36>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:182>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:240>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:772>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:791>),
  [core/command_sandbox.py](</d:/projetos_cli/cerebro/core/command_sandbox.py:84>).
  Debate que confirmou: `Debate 2` no eixo de segurança concluiu que o primeiro abuso prático tende a ser `command_registry -> verify`, porque o comando parece seguro, roda com menos atrito operacional e grava a própria exfiltração em `artifacts/verification/...`. No ranking operacional agregado ele continua abaixo de `WEAK-CRIT-001`, porque depende de command input malicioso ou descuidado; ainda assim, ficou confirmado como a superfície de abuso mais crítica do eixo de segurança.

- Fechamento desta sessão: `runtime.lock` agora trata probes de PID inválido no Windows (`WinError 87`) como dono inativo, então locks órfãos com owner PID morto passam a ser recuperados em vez de esperar até timeout; o timeout fica explícito apenas para o caso em que o owner PID ainda parece vivo.
  Evidência:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4865>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4879>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4897>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:2307>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:2320>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:835>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:906>).
  Prova operacional: a regressão nova simula o probe `os.kill(pid, 0)` retornando `WinError 87`, observa `validate_state()` recuperar o lock e seguir verde; um segundo teste fixa o caminho oposto e prova que o timeout continua intencional quando o owner PID ainda parece ativo.

- Fechamento desta sessão: `verify` agora falha cedo quando a seleção de comandos ultrapassa o budget efetivo de `verification.checks`, reservando explicitamente um slot para o `check-state` sintético e impedindo a persistência inválida de `33` checks.
  Evidência:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:231>),
  [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:214>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:18>).
  Prova operacional: a regressão nova persiste um plano com `32` comandos `allow_in_verify`, observa `run_verify()` retornar `1` com `verification_failed`, mensagem explícita de budget (`at most 31 commands can run`) e ausência de `invalid_agent_verification_checks`, preservando `verification.status == "idle"`.

- A cobertura negativa de approval ainda deixa aberto o caso `fs.create_file` com `overwrite=true` sobre arquivo existente sob `approval_required_kinds=["fs.write_patch"]`.
  Evidência:
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:2628>),
  [docs/operations/ROBUSTNESS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/ROBUSTNESS_BASELINE.md:73>).
  Residual estreitado nesta sessão: o negativo direto para action sensível `failed` sem `approval_id` agora está cristalizado em [tests/test_validation_approval_guards.py](</d:/projetos_cli/cerebro/tests/test_validation_approval_guards.py:24>).
  Debate que confirmou: a oposição não encontrou teste que cobrisse a combinação destrutiva `overwrite=true` sob approval.

## Dívida técnica por categoria

### morto

- Import não usado em [cli/commands/import_context.py](</d:/projetos_cli/cerebro/cli/commands/import_context.py:8>).
- Import não usado em [extensions/status_export/exporter.py](</d:/projetos_cli/cerebro/extensions/status_export/exporter.py:7>).
- Variável atribuída e não lida em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:902>).
- Constantes atribuídas e não lidas em [core/work_profile.py](</d:/projetos_cli/cerebro/core/work_profile.py:14>) e [core/work_profile.py](</d:/projetos_cli/cerebro/core/work_profile.py:20>).

### duplicado

- `status_export` duplica a janela de eventos do plano em [extensions/status_export/exporter.py](</d:/projetos_cli/cerebro/extensions/status_export/exporter.py:22>) em vez de depender do helper canônico [core/runtime_event_window.py](</d:/projetos_cli/cerebro/core/runtime_event_window.py:6>).

### inconsistente

- `command_registry.commands[*].cwd` é aceito como string no validator e só recebe boundary check tardio em runtime:
  [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:442>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:761>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:209>).

### acoplado

- `StateStore` concentra persistência, sessão, retenção, read models, seleção de task, audit e recovery:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:23>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:120>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1722>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4056>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4186>).
- `verification_runtime` e `action_runtime` dependem de duck-typing do `StateStore`, não de interface explícita:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:82>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:174>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:68>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:126>).
- O fingerprint de action e o blocking de retry dependem de sinais espalhados entre runtime/discipline/decision:
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:303>),
  [core/discipline_runtime.py](</d:/projetos_cli/cerebro/core/discipline_runtime.py:61>),
  [core/decision_runtime.py](</d:/projetos_cli/cerebro/core/decision_runtime.py:183>).

### sem teste

- `core/windows_credential_store.py` só com cobertura condicional Windows:
  [core/windows_credential_store.py](</d:/projetos_cli/cerebro/core/windows_credential_store.py:67>).

## Divergências doc/código

- `AGENT_ARCHITECTURE.md` ainda descreve `DELEGATE`/`RECORD` e papéis como se fossem parte do runtime canônico, mas o estado real persiste plano, approvals, actions e verification, não um scheduler de papéis.
  Evidência:
  [docs/operations/AGENT_ARCHITECTURE.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_ARCHITECTURE.md:24>),
  [docs/operations/AGENT_ARCHITECTURE.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_ARCHITECTURE.md:39>),
  [docs/operations/AGENT_ARCHITECTURE.md](</d:/projetos_cli/cerebro/docs/operations/AGENT_ARCHITECTURE.md:68>),
  [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:243>).
- Comportamentos reais ainda não registrados no baseline operacional:
  `validate_state()` tenta até 3 vezes em concorrência antes de `state_changed_during_validation` em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1660>);
  `verify` reescreve sandbox env completo em [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:36>);
  `plan_updated` reseta `batch_registry["used_ids"]` em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1346>);
  o “sandbox” de `verify` é apenas um clone descartável do workspace, não um sandbox de host, em [core/command_sandbox.py](</d:/projetos_cli/cerebro/core/command_sandbox.py:84>) e [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:209>);
  `verify` sempre injeta um `check-state` sintético antes dos checks registrados em [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:133>);
  `action_belongs_to_current_plan()` faz fallback para `task_id`/`action_id` quando `plan_generation_id` está ausente em [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:651>);
  `record_parallel_approach_consolidation()` auto-preenche `consolidation_id` quando ele não vem explícito em [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:373>).

## Padrões históricos do git

- `bootstrap_scan` concentrou a sequência recente mais clara de “feat -> stabilize -> harden -> close -> fix”, sugerindo correções repetidas no mesmo slice:
  commits `aef679f`, `4f69cae`, `a04e0e4`, `7755f22`, `fd0b537`.
- No histórico recente, `tests/test_architecture.py`, `docs/WORKSTREAM_BOARD.md` e `README.md` recebem muito mais churn do que módulos de runtime, indicando um projeto em forte fase de governança/documentação.
- No histórico preservado de `core/`, `core/state_store.py` aparece como hotspot recorrente, coerente com a concentração atual de responsabilidades.

## Oportunidades de melhoria

### dentro do freeze

- Fechado nesta sessão: `session-discard` já recupera o split `registry active + session.local.json` ausente; o residual corretivo de sessão agora ficou fechado também no caminho de refresh com `session.refresh.pending.json` e recovery antecipado antes de `session_revision_invalid`.
- Adicionar teste direto para perda de `state.json` após bootstrap/init.
- Fechado nesta sessão: o e2e contínuo `bootstrap -> validate/analyze -> plan -> apply -> verify -> rollback` agora está cristalizado num único teste de integração.
- Fechado nesta sessão: `invalid_command_registry_command_cwd` agora tem cobertura direta no validator e nos boundaries tardios de `apply`/`verify`.
- Fechado nesta sessão: `core/command_sandbox.py` agora tem testes diretos para clone descartável e diff de manifesto sem falso positivo por `mtime` de diretório.
- Fechado nesta sessão: `core/execution_policy.py` agora tem testes diretos para boundary de path, gate de comando e regra de approval.
- Fechado nesta sessão: `core/runtime_event_window.py` agora tem teste direto para o recorte da janela do plano mais recente, incluindo tolerância a ruído não-dict e fail-closed para input inválido.
- Fechado nesta sessão: `fs.move` com `from == to` agora falha fechado como `action_no_effect` antes da mutação, evitando o falso `applied` e o rollback envenenado que antes terminava em `original source path already exists and blocks rollback`.
- Fechado nesta sessão: as regressões de `fs.move` agora cobrem também paths lexicalmente diferentes que resolvem para o mesmo arquivo, cristalizando o contrato real do guard por path resolvido.
- Fechado nesta sessão: `runtime.lock` agora tem regressões explícitas separando owner PID inválido/morto (cleanup) de owner PID ainda vivo (timeout esperado).
- Fechado nesta sessão: `verify` agora tem regressão explícita para o edge de `32` comandos registrados mais o `check-state` sintético e falha cedo antes de tentar persistir `33` checks.
- Fechado nesta sessão: a compensação de `guarded_apply_batch()` e `guarded_rollback_batch()` agora continua em best effort mesmo quando o primeiro restore falha, restaurando os caminhos restantes antes de propagar erro canônico de compensation.
- Fechado nesta sessão: `exec.command` agora ancora approval e retry ao snapshot resolvido do `command_registry`, então drift de `argv`/`cwd`/`timeout_ms`/`side_effect` deixa de reaproveitar aprovação antiga silenciosamente.
- Fechado nesta sessão: `exec.command` com `command_id` removido do `command_registry` agora falha fechado antes de approval/retry, em vez de gerar um novo gate para um comando que já não existe.
- Documentado nesta sessão: `validate --retention-report` e `validate --retention-apply` ainda recarregam o estado e varrem `events.jsonl` por completo no mesmo comando; o custo agora ficou explícito em `docs/operations/COST_TOPOLOGY.md`, mas segue sem benchmark dedicado.
- Documentar os comportamentos hoje não explicitados no baseline (`validate_state` retry concorrente, sandbox env completo de `verify`, reset de `batch_registry.used_ids`).
- Endurecer o teste isolado de `open_session` para não depender de diretórios externos compartilhados.
- Fechado nesta sessão: `tests/test_analyze.py` remove asserts frágeis por índice e cristaliza o caminho negativo em que `session_token` não é emitido por padrão, enquanto a emissão explícita continua restrita a `emit_session_token=True`.
  Evidência:
  [tests/test_analyze.py](</d:/projetos_cli/cerebro/tests/test_analyze.py:43>),
  [tests/test_analyze.py](</d:/projetos_cli/cerebro/tests/test_analyze.py:94>),
  [tests/test_analyze.py](</d:/projetos_cli/cerebro/tests/test_analyze.py:124>).
  Prova operacional: `test_analyze_with_valid_state_prints_stable_context_and_opens_session` valida a saída estável e a abertura da sessão; `test_analyze_does_not_emit_session_token_by_default` garante ausência do token no caminho padrão; `test_analyze_emits_session_token_only_when_requested` garante o token só quando solicitado.
- Ainda aberto no `main`: os cenários de `import-context` e `checkpoint` que exercitam falha em `close_session()`/`save_state()` em `tests/test_validate.py` ainda usam `mock.patch.object(StateStore, ...)` para injetar `StateStoreError`, então a suíte prova a tradução estável de `operation_failed`, mas ainda não cristaliza a mesma trilha por falha real de I/O no filesystem.
  Evidência:
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:982>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1013>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1900>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1935>).
- Fechar a lacuna de policy em que `fs.create_file` com `overwrite=true` continua dispensando approval por estar classificado só por `kind`.

### exige arquitetura

- Introduzir uma camada transacional única para mutações críticas (`apply`, `rollback`, refresh de sessão).
- Quebrar `StateStore` em serviços coesos atrás de uma façade fina, sem segunda fonte de verdade.
- Tornar o contrato de runtime explícito e centralizado, em vez de espalhado entre canonicalização, validação, execução e documentação.
- Endurecer o boundary de execução de `verify` para que segredos herdados e efeitos host-side não dependam só de disciplina/documentação.

### especulativo

- Cache persistente de `state.json` entre comandos.
- Índice persistente de `events.jsonl` para consolidações/status.
- Nova camada de export/read model com invalidação própria.

## O que está saudável

- Os contratos principais de sessão, ownership, checkpoint, discard e validação estão implementados e fortemente cobertos:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1088>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3019>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:3247>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1060>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1431>).
- Approval scoping, batch registry, caps de histórico e retenção governada estão cobertos por testes diretos e integrações:
  [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:935>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1346>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1722>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4056>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:548>).
- As guardas arquiteturais de boundary e o contrato read-only das extensões continuam fortes:
  [tests/test_architecture.py](</d:/projetos_cli/cerebro/tests/test_architecture.py:1474>),
  [tests/test_extension_contracts.py](</d:/projetos_cli/cerebro/tests/test_extension_contracts.py:253>),
  [tests/test_extension_contracts.py](</d:/projetos_cli/cerebro/tests/test_extension_contracts.py:286>).

## Próxima rodada

- Primeiro item: manter o gap de approval por efeito em `fs.create_file overwrite=true` em `Grupo 6`, porque a menor correção segura cruza `core/validation.py`.
- Segundo item: fechar as lacunas de cobertura pequenas e baratas (e2e contínuo de sessão->plan->apply->verify->rollback, testes diretos de helpers centrais, `runtime.lock` órfão) e alinhar a documentação operacional aos comportamentos reais já descobertos nesta auditoria.
- Terceiro item: decidir se o boundary host-trusting atual de `verify` permanece residual aceito ou se sobe para slice corretivo/arquitetural explícito, junto do edge de `32` checks + `check-state` e da falta de contrato explícito hoje espalhada entre validator, runtime e docs.
