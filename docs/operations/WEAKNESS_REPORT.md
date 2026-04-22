# Weakness Report

Structured residual index: `docs/operations/residuals.toml` is the canonical structured inventory for accepted or blocked residual entries. This report remains the narrative companion and evidence trail; when the two surfaces diverge, reconcile the TOML entry first and then restate the narrative here.

## Resumo executivo

 O Cerebro está operacionalmente estável e a suíte principal segue verde. Nesta sessão, o último débito crítico remanescente do `Grupo 6` foi fechado: approval agora é decidido por efeito destrutivo real ou projetado em `fs.create_file overwrite=true`, não apenas por `kind`. O sentinel sintético `check-state` já havia sido removido do contrato persistido de `verification`, e `verify` já havia deixado de herdar o ambiente amplo do host. A auditoria pós-hardening posterior também fechou dois escapes residuais: o boundary direto de `apply_action()` voltou a exigir approval para mutações governadas, e `verify` passou a falhar fechado e restaurar o live workspace quando um comando tenta escrever fora do sandbox descartável. Fora disso, a base ainda mostra um padrão claro de dívida concentrada: `StateStore` supercarregado, contratos implícitos entre módulos, e cobertura forte nos fluxos principais mas desigual em alguns helpers e cenários de bootstrap/corrupção.

## Achados confirmados pelos debates

### CRÍTICO

- Fechamento desta sessão: approval por efeito agora cobre `fs.create_file overwrite=true` quando o alvo já existe no filesystem real ou no estado projetado do batch. `apply` calcula `target_exists` antes da execução, `validation` e `rollback` reaplicam o mesmo contrato sobre o `action_record` persistido, e `create` benigno continua livre.
  Evidência do fechamento:
  [core/execution_policy.py](</d:/projetos_cli/cerebro/core/execution_policy.py:73>),
  [core/execution_policy.py](</d:/projetos_cli/cerebro/core/execution_policy.py:100>),
  [core/execution_policy.py](</d:/projetos_cli/cerebro/core/execution_policy.py:116>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:178>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:202>),
  [cli/commands/apply.py](</d:/projetos_cli/cerebro/cli/commands/apply.py:409>),
  [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:975>),
  [cli/commands/rollback.py](</d:/projetos_cli/cerebro/cli/commands/rollback.py:60>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4105>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4163>),
  [tests/test_validation_approval_guards.py](</d:/projetos_cli/cerebro/tests/test_validation_approval_guards.py:51>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:411>),
  [tests/test_execution_policy.py](</d:/projetos_cli/cerebro/tests/test_execution_policy.py:62>).
  Prova operacional: a reprodução adversarial do overwrite destrutivo real e do batch projetado `create -> overwrite` agora retorna `approval_required`, preserva o conteúdo anterior, não registra `actions` e cria apenas o `approval` pendente. A suíte ampla permaneceu verde com `700` testes, `0` falhas e `6` skips; `tests.test_architecture` também permaneceu verde com `51` testes.

- Fechamento anterior nesta categoria:
  o gap pós-mutação de `exec.command` foi fechado em
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:148>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:839>)
  e cristalizado por
  [tests/test_action_runtime.py](</d:/projetos_cli/cerebro/tests/test_action_runtime.py:95>).
  O runtime agora converte falha de persistência de `stdout.txt`/`stderr.txt` em `action_record` canônico com `status == "failed"`, sem deixar o CLI cair em `internal_error`.

- Fechamento da auditoria pós-hardening: o boundary direto de `apply_action()` agora reaplica approval no core para mutações governadas, então `fs.create_file overwrite=true` e `fs.move` destrutivos não conseguem mais bypassar a policy quando o runtime é chamado sem o preflight do CLI.
  Evidência do fechamento:
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:179>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:755>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:780>),
  [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:825>),
  [tests/test_action_runtime.py](</d:/projetos_cli/cerebro/tests/test_action_runtime.py:299>),
  [tests/test_action_runtime.py](</d:/projetos_cli/cerebro/tests/test_action_runtime.py:330>),
  [tests/test_execution_policy.py](</d:/projetos_cli/cerebro/tests/test_execution_policy.py:62>).
  Prova operacional: a chamada direta ao runtime agora devolve `approval_required` antes da mutação quando o alvo já existe, enquanto `create` benigno em alvo ausente continua passando sem fatigue nova. A suíte ampla permaneceu verde ao final da auditoria com `704` testes, `0` falhas e `6` skips; `tests.test_architecture` seguiu verde com `51` testes.

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

- Fechamento desta sessão: o sentinel sintético `check-state` saiu do contrato persistido de `verification`; o preflight agora vive em `verification.state_check`, `verification.checks` voltou a conter apenas checks reais de comando, a migração legada ficou centralizada na canonicalização e os consumidores passaram a depender de um helper único em vez de filtros distribuídos.
  Evidência do fechamento:
  [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:481>),
  [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:525>),
  [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:696>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:363>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:525>),
  [cli/commands/verify.py](</d:/projetos_cli/cerebro/cli/commands/verify.py:45>),
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:4261>),
  [core/memory_runtime.py](</d:/projetos_cli/cerebro/core/memory_runtime.py:111>),
  [extensions/status_export/exporter.py](</d:/projetos_cli/cerebro/extensions/status_export/exporter.py:187>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:523>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:2096>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:388>).
  Critério satisfeito: `check-state` não é mais persistido em `verification.checks`, falha de preflight cai em `state_check.failed`, verify parcial continua parcial sem sentinel, e a suíte ampla permaneceu verde (`696` testes, `0` falhas, `6` skips; `tests.test_architecture` verde com `51` testes).

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
  Prova operacional: a regressão nova força `prepare_project_sandbox()` a lançar `OSError`, observa `run_verify()` retornando `1`, `verification.status == "failed"` com `state_check.failed`, `checks == []` e um único evento `verify_failed` persistido no audit trail.

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

- Fechamento desta sessão: `verify` deixou de herdar o `PATH` completo do host, passou a montar um `PATH` mínimo a partir do comando resolvido, manteve apenas o subconjunto compatível de variáveis herdadas, e redige `stdout`/`stderr` antes da persistência de artifacts, inclusive por segmento de `PATH`.
  Evidência do fechamento:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:24>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:66>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:83>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:100>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:128>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:179>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:963>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:1088>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:1152>).
  Prova operacional: reproduções manuais com `INV2_SECRET`, `PYTHONIOENCODING` e `HOST-PATH-SEGMENT-SENTINEL` deixaram de reaparecer em `artifacts/verification/...`, inclusive quando o comando tenta derivar apenas o nome do primeiro segmento do `PATH`. O helper mínimo via comando resolvido continua executável, e `SYSTEMDRIVE` saiu do scrub para preservar `C:` legítimo em `stdout/stderr`.
  Residual remanescente: `verify` ainda preserva um subconjunto mínimo de compatibilidade (`COMSPEC`, `PATHEXT`, `SYSTEMDRIVE`, `SYSTEMROOT`, `WINDIR`), mas o caminho original de exfiltração persistida via host env amplo ficou fechado.

- Fechamento da auditoria pós-hardening: `verify` agora detecta mutação do live project fora do sandbox descartável, restaura os caminhos alterados a partir de um snapshot pristino separado e falha fechado em vez de reportar verde com side effect host-side.
  Evidência do fechamento:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:57>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:74>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:108>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:450>),
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:568>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:1025>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:1082>).
  Prova operacional: a reprodução com escrita por path absoluto no workspace real agora retorna `verification_failed`, restaura o conteúdo original do arquivo vivo e continua válida mesmo quando o comando tenta envenenar simultaneamente o arquivo do sandbox e o arquivo real. A suíte ampla permaneceu verde ao final da auditoria com `704` testes, `0` falhas e `6` skips.

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

- Fechamento desta sessão: `verify` agora aceita o budget cheio de `32` checks de comando porque o preflight saiu de `verification.checks`, impedindo o falso overflow sintético e preservando o contrato command-only.
  Evidência:
  [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:231>),
  [core/agent_runtime.py](</d:/projetos_cli/cerebro/core/agent_runtime.py:214>),
  [tests/test_verification_runtime.py](</d:/projetos_cli/cerebro/tests/test_verification_runtime.py:18>).
  Prova operacional: a regressão nova persiste um plano com `32` comandos `allow_in_verify`, observa `run_verify()` retornar `0`, `checks: 32`, ausência de `invalid_agent_verification_checks` e `verification.status == "passed"`.

- Fechamento desta sessão: a cobertura negativa de approval agora cristaliza tanto o caso destrutivo real quanto o batch projetado para `fs.create_file overwrite=true` sob `approval_required_kinds=["fs.write_patch"]`.
  Evidência:
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4105>),
  [tests/test_alpha_runtime.py](</d:/projetos_cli/cerebro/tests/test_alpha_runtime.py:4163>),
  [tests/test_validation_approval_guards.py](</d:/projetos_cli/cerebro/tests/test_validation_approval_guards.py:51>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:411>),
  [tests/test_execution_policy.py](</d:/projetos_cli/cerebro/tests/test_execution_policy.py:62>),
  [docs/operations/ROBUSTNESS_BASELINE.md](</d:/projetos_cli/cerebro/docs/operations/ROBUSTNESS_BASELINE.md:73>).
  Critério satisfeito: o helper central distingue `target_exists=False/True`, `create` benigno segue sem fatigue indevida, e histórico persistido sem `approval_id` para overwrite destrutivo falha fechado em `validate` e `rollback`.

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
  `verify` agora persiste o preflight separadamente em `verification.state_check` e reserva `verification.checks` apenas para checks de comando reais em [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:380>);
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
- Fechado nesta sessão: `verify` agora tem regressão explícita para o budget cheio de `32` comandos reais sem overflow sintético.
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
- Fechado nesta sessão: os cenários de `import-context` e `checkpoint` para falha em `close_session()`/`save_state()` no nível do CLI agora exercitam falhas reais de I/O no boundary do filesystem, sem `mock.patch.object(StateStore, ...)`.
  Evidência:
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1012>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1064>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1973>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:2027>).
  Prova operacional: os testes agora falham `Path.unlink` em `session.local.json` e `os.replace` em `state.json`, confirmando `operation_failed` sem `internal_error` e restauração de `state`, `session.local.json`, claim externo e live proof externo.
- Fechado nesta sessão: `close_session()` não engole mais falha de leitura/validação de `session.local.json`; o core agora registra `session_close_failed` e falha fechado antes de limpar registry, claim ou live-proof, e os chamadores CLI `import-context` e `checkpoint` cristalizam `operation_failed` sem mutação de estado.
  Evidência:
  [core/state_store.py](</d:/projetos_cli/cerebro/core/state_store.py:1189>),
  [tests/test_state_store.py](</d:/projetos_cli/cerebro/tests/test_state_store.py:2347>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:1064>),
  [tests/test_validate.py](</d:/projetos_cli/cerebro/tests/test_validate.py:2031>).
  Prova operacional: `_read_session_file()` inválido ou explosivo agora preserva `active_session_id`, `active_session_claim_id`, `session.local.json`, claim externo e live-proof externo, enquanto `import-context` e `checkpoint` retornam `operation_failed` em vez de seguir com sucesso silencioso.
- Fechado nesta sessão: a lacuna de policy em que `fs.create_file` com `overwrite=true` dispensava approval por estar classificado só por `kind`.

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
- A auditoria de worktrees de `2026-04-19` fechou sem residual aberto no fluxo suportado do Cerebro: `RISCO 1/7` (corrida no create/registry), `RISCO 2` (órfão parcial) e `RISCO 6` (fallback silencioso) ficaram cobertos por regressão direta; `RISCO 3/4/5` foram investigados e limpos. Prova operacional: suíte `688 -> 694`, `tests.test_architecture` verde e teste manual `create -> list -> clean` aprovado.

## Próxima rodada

- Primeiro item: nenhum dentro do `Grupo 6`; a prova de parada `P1-P5` terminou limpa em `2026-04-19`.
- Segundo item: manter o foco residual nos débitos arquiteturais fora do `Grupo 6`, especialmente concentração no `StateStore` e contratos ainda implícitos entre runtime, validator e documentação.
- Terceiro item: reabrir o loop apenas por `Formal Resume Trigger` ou por problema novo confirmado com evidência rastreável.
