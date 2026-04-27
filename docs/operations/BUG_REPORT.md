## Current Snapshot — 2026-04-23

- Live executable bug queue: none. The machine-primary queue for still-resolvable work lives in `docs/operations/observation_center.toml`; this file is a historical ledger of closed canonical-runtime rounds and is not consulted for live scheduling.
- Posture: every entry below is preserved as historical evidence of a bug that was closed in a prior round. Language such as "Problemas confirmados" and the Round-by-Round progression applies only within that history; none of those items are currently open unless explicitly reopened in this Current Snapshot.
- Accepted residuals and freeze-blocked items recorded below are not an executable queue. They exist as audit trail and as anchors for future formal resume triggers if an operator chooses to reopen them.
- Disambiguation for future readers: if a line below reads like live state (for example a suite-count update or a "Problemas confirmados" heading), treat it as historical unless the Current Snapshot above explicitly promotes it back.

## Historical Canonical Bug Ledger

## Estado da suíte

- Antes da varredura: `534` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da varredura: `534` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 9 corretiva: `546` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 10 corretiva: `548` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 11 corretiva: `551` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 12 corretiva: `554` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 13 corretiva: `556` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 14 corretiva: `558` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 15 corretiva: `559` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 16 corretiva: `560` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 17 corretiva: `562` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 18 corretiva: `563` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)
- Depois da Round 19 corretiva: `567` testes passando, `6` skips, `0` falhas (`python -m unittest discover -s tests -v`)

## Problemas confirmados

### CRÍTICO — `exec.command` pode mutar o workspace e cair em `internal_error` antes do `action_record` canônico [FECHADO na Round 11]

- Localização do fechamento: `core/action_runtime.py:148-180`, `core/action_runtime.py:839-874`
- Descrição: depois que o subprocesso terminava, uma falha ao persistir `stdout.txt`/`stderr.txt` escapava como `OSError`, o CLI caía em `internal_error`, e o delta físico podia ficar sem `action_record` canônico.
- Como reproduzir: registrar um `exec.command` mutante, forçar falha em `stderr.txt` ou `stdout.txt` depois do subprocesso e rodar `cerebro apply --action-file ...`.
- Causa raiz confirmada: o runtime só auditava falha de launch; a persistência de artifacts vinha depois da mutação e antes do primeiro `record_agent_action(...)`, sem captura local desse `OSError`.
- Debate: oponente falsificou a correção fraca de “só reempacotar a exceção”; a proposta vencedora foi converter a falha pós-run em `action_record` canônico com `status="failed"`.
- Fechamento observado: `apply_action()` agora limpa artifacts parciais, retorna um `exec.command` canônico com `status="failed"` e `failure_message` explícito, e o CLI responde `action_failed` em vez de `internal_error`.
- Teste que cristalizou o fechamento: `tests/test_action_runtime.py:95` — `ActionRuntimeCommandTests.test_exec_command_artifact_write_failure_records_failed_action`

### ALTO — `exec.command` pode estourar exceção crua no apply [FECHADO na Round 8]

- Localização do fechamento: `core/action_runtime.py:771-790`
- Descrição: `apply_action()` chama `subprocess.run(...)` sem traduzir `OSError`/`FileNotFoundError`/`TimeoutExpired` para `ActionRuntimeError`. O CLI só captura isso no fallback genérico e responde `internal_error`.
- Como reproduzir: registrar um `command_registry` com `argv[0]` inexistente e executar uma action `exec.command`.
- Causa raiz confirmada: não há `try/except` ao redor do launch do subprocesso; a validação só verifica shape do comando, não launchability.
- Debate: sem divergência. Confirmação focada manteve o achado.
- Fechamento observado: o launch agora é encapsulado em `try/except`, registra `apply_failed` com `reason_code=command_execution_exception` e devolve `ActionRuntimeError` ao CLI em vez de cair em `internal_error`.
- Teste que cristalizou o fechamento: `tests/test_action_runtime.py:16` — `ActionRuntimeCommandTests.test_exec_command_launch_failure_is_structured_and_audited`

### ALTO — `verify` pode estourar exceção crua antes de produzir `VerificationRuntimeError` [FECHADO na Round 8]

- Localização do fechamento: `core/verification_runtime.py:198-239`
- Descrição: `run_verification_commands()` também chama `subprocess.run(...)` sem traduzir falhas de launch. O caminho de `verify` vira `internal_error` em vez de falha operacional tipada.
- Como reproduzir: registrar um verify command com executável inexistente, gerar `pending_action_ids`, rodar `cerebro verify`.
- Causa raiz confirmada: falta de captura de `FileNotFoundError`/`OSError`/`TimeoutExpired` no runtime de verificação.
- Debate: sem divergência. Confirmação focada manteve o achado.
- Fechamento observado: o launch agora é encapsulado em `try/except`, registra `verify_failed` com `reason_code=command_execution_exception` e devolve `VerificationRuntimeError` sem materializar checks parciais nem cair em `internal_error`.
- Teste que cristalizou o fechamento: `tests/test_alpha_runtime.py:617` — `AlphaRuntimeTests.test_verify_missing_executable_fails_cleanly_and_records_audit_event`

### ALTO — `open_session()` tem janela real de sessão órfã após crash [FECHADO na Round 8]

- Localização do fechamento: `core/state_store.py:1150-1172`, `core/state_store.py:2996-3003`
- Descrição: `session.local.json` e os artifacts externos de claim/live-proof são gravados antes de o registro ativo ser persistido em `state.json`.
- Como reproduzir: interromper o processo depois de gravar `session.local.json` e antes de `save_state()` retornar.
- Causa raiz confirmada: ordem de persistência dividida entre sidecar local/external proof e registro canônico.
- Efeito confirmado: restart encontra `.cerebro/session.local.json`, mas `state.json` continua sem `active_session_id`/`active_session_claim_id`; `validate_state()` falha com `session_not_registered`.
- Debate: sem divergência. Confirmação focada manteve o achado.
- Fechamento observado: o registro canônico agora é persistido antes de `session.local.json`; se a escrita final do arquivo local falha, o core restaura o registro anterior e remove claim/live-proof recém-criados, evitando sessão órfã parcialmente aberta.
- Teste que cristalizou o fechamento: `tests/test_state_store.py:1679` — `StateStoreTests.test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails`

### ALTO — `retention-apply` pode reportar sucesso com trilha degradada e `events.jsonl` corrompido [FECHADO na Round 8]

- Localização do fechamento: `core/state_store.py:1778-1814`
- Descrição: se o append do evento `retention_applied` falhar após escrita parcial, `apply_retention()` continua, grava `manifest.json`, retorna `applied=True` e deixa `events.jsonl` truncado/malformado.
- Como reproduzir: forçar `_write_trace_event_line()` a escrever um fragmento JSON do evento `retention_applied` e lançar `OSError` durante `cerebro validate --retention-apply`.
- Causa raiz confirmada: `_commit_trace_events()` engole `OSError`, apenas marca `trace_status=degraded` e não propaga falha para `apply_retention()`.
- Efeito confirmado: `manifest.json` finalizado com `retention_event_id`, `state.json` degradado, log com linha ilegível exposta depois como `unreadable_event_log_record`.
- Debate: sem divergência. A confirmação focada estreitou o claim: não é “estado saudável falso”, é “sucesso operacional com trilha degradada e log potencialmente corrompido”.
- Fechamento observado: `retention-apply` agora falha fechado quando o append de `retention_applied` degrada; o `manifest.json` só recebe `retention_event_id` depois de o evento realmente ser commitado, e o rerun continua seguro.
- Teste que cristalizou o fechamento: `tests/test_validate.py:415` — `ValidateCommandTests.test_validate_retention_apply_fails_when_retention_trace_append_degrades_and_rerun_is_safe`

### ALTO — `open_session()` podia deixar `session_registry_mismatch` sem recovery in-band [FECHADO na Round 12]

- Localização do fechamento: `core/state_store.py:1221-1266`, `core/state_store.py:1355-1385`
- Descrição: depois que `open_session()` já tinha persistido `active_session_id`/`active_session_claim_id`, a perda de `session.local.json` deixava o runtime preso em `session_registry_mismatch` e o próprio `session-discard` respondia `session_absent` em vez de limpar o resíduo.
- Como reproduzir: abrir uma sessão válida, remover `.cerebro/session.local.json` mantendo `state.json` e os artifacts externos intactos, e rodar `cerebro session-discard`.
- Causa raiz confirmada: `discard_session()` decidia pelo presence check de `session.local.json` antes de considerar o registro canônico já ativo, então o recovery explícito nunca era acionado para o split “registry active + local sidecar missing”.
- Debate: a proposta de reordenar `open_session()` foi falsificada porque reabria o bug inverso `session_not_registered`; a proposta vencedora foi manter a ordem canônica atual e estreitar o recovery em `discard_session()` para esse resíduo específico.
- Fechamento observado: `session-discard` agora limpa o resíduo `registry active + session.local.json` ausente, remove claim/live-proof externos quando ainda existem, revalida sem bump de revisão e preserva o comportamento `session_absent` quando não há sessão nem registro.
- Testes que cristalizam o fechamento:
  - `tests/test_state_store.py:2178` — `StateStoreTests.test_discard_session_clears_registry_only_session_residue_without_bumping_revision`
  - `tests/test_validate.py:1157` — `ValidateCommandTests.test_session_discard_clears_registry_only_session_residue_after_open_session_split`
  - `tests/test_validate.py:1182` — `ValidateCommandTests.test_session_discard_reports_absent_when_no_local_session_or_registry_exists`

### ALTO — `_save_state_with_refreshed_session()` podia deixar `session_revision_invalid` após crash [FECHADO na Round 13]

- Localização do fechamento: `core/state_store.py:3312-3314`, `core/state_store.py:3507-3606`, `core/state_store.py:3664-3688`
- Descrição: a helper escrevia `session.local.json` antes de persistir `state.json`, então um crash duro na janela deixava `session.local.json.based_on_revision > state.revision` e o runtime falhava fechado em `session_revision_invalid`.
- Como reproduzir: abrir uma sessão válida, provocar morte do processo entre a escrita de `session.local.json` e o retorno de `save_state()`, e então rodar `cerebro validate`.
- Causa raiz confirmada: o refresh de sessão era uma sequência de dois arquivos sem journal durável; o rollback local cobria só exceções Python síncronas e não sobrevivia a `SystemExit`/kill/crash duro.
- Debate: oponente falsificou o reorder isolado porque ele só espelhava o split (`state.revision > session.based_on_revision`) e continuava quebrando na mesma checagem estrita; a proposta vencedora foi `journal + early recovery` local no `StateStore`.
- Fechamento observado: `_save_state_with_refreshed_session()` agora grava `session.refresh.pending.json` antes do refresh, restaura o sidecar anterior quando o commit de `state.json` não acontece, e `validate_state()` finaliza ou recupera esse journal antes de emitir `session_revision_invalid`.
- Testes que cristalizam o fechamento:
  - `tests/test_state_store.py:1809` — `StateStoreTests.test_validate_state_recovers_pending_session_refresh_after_crash_before_state_save`
  - `tests/test_state_store.py:1869` — `StateStoreTests.test_validate_state_finalizes_stale_pending_session_refresh_after_successful_commit`
  - `tests/test_validate.py:1060` — `ValidateCommandTests.test_validate_fails_with_session_revision_invalid`

### ALTO — `verify` podia vazar `OSError` cru após o subprocesso e antes do `verification_record` canônico [FECHADO na Round 14]

- Localização do fechamento: `core/verification_runtime.py:108-137`, `core/verification_runtime.py:286-321`, `cli/commands/verify.py:92-102`
- Descrição: quando o subprocesso de `verify` terminava bem, uma falha ao persistir `cmd-001.stdout.txt`/`cmd-001.stderr.txt` escapava como `OSError`, o CLI não traduzia o erro para falha operacional estável, e o runtime perdia tanto o `verification_record` quanto a trilha auditável equivalente.
- Como reproduzir: registrar um comando de `verify` que execute com sucesso, forçar `Path.write_text` a falhar na gravação de `*.stdout.txt` ou `*.stderr.txt` depois do `subprocess.run(...)`, e rodar `cerebro verify`.
- Causa raiz confirmada: `run_verification_commands()` tratava falha de launch, mas deixava a persistência de artifacts fora da fronteira de captura; o comando já tinha executado, mas ainda não existiam cleanup, `verify_failed` pós-run nem `verification_record` canônico.
- Debate: a varredura proativa confirmou a falha; a oposição não a falsificou; a correção vencedora reaplicou em `verify` o padrão consolidado em `apply`: falhar fechado, limpar parcial, auditar e persistir estado canônico de falha.
- Fechamento observado: `verify` agora limpa artifacts parciais, registra `verify_failed` com `reason_code=command_artifact_persistence_exception`, persiste um `verification_record` `failed` com mensagem explícita quando não há artifact, e responde `verification_failed` sem cair em `internal_error`.
- Teste que cristalizou o fechamento: `tests/test_verification_runtime.py:16` — `VerificationRuntimeTests.test_verify_artifact_write_failure_records_failed_verification`

### ALTO — `verify` podia cair em `internal_error` quando a policy negava comando em `A0/A1` [FECHADO na Round 17]

- Localização do fechamento: `core/verification_runtime.py:248-250`, `tests/test_verification_runtime.py:17-66`, `tests/test_alpha_runtime.py:618-683`
- Descrição: `ensure_command_allowed()` levantava `ExecutionPolicyError` para planos em `A0/A1`, mas esse deny-path escapava cru do runtime de verificação; `run_verify()` não traduzia a exceção e o topo do CLI respondia `internal_error` em vez de `verification_failed`.
- Como reproduzir: persistir um plano com `autonomy_level="A1"`, registrar um comando verificável `read_only` e rodar `cerebro verify`.
- Causa raiz confirmada: `run_verification_commands()` chamava `ensure_command_allowed()` fora da fronteira de tradução para `VerificationRuntimeError`.
- Debate: a varredura proativa confirmou o bug no fluxo real; a oposição não falsificou a reprodução; a correção vencedora foi o menor patch local no runtime de `verify`, sem tocar `core/validation.py`.
- Fechamento observado: o deny-path de policy agora vira `VerificationRuntimeError` com mensagem explícita por `command_id`, então o CLI responde `verification_failed` e não cai mais no fallback `internal_error`.
- Testes que cristalizaram o fechamento:
  - `tests/test_verification_runtime.py:17` — `VerificationRuntimeTests.test_verify_policy_deny_is_typed_as_verification_runtime_error`
  - `tests/test_alpha_runtime.py:618` — `AlphaRuntimeTests.test_verify_a1_policy_deny_returns_verification_failed_not_internal_error`

### ALTO — `save_state()` aceitava regressão de `revision` com `expected_revision` ainda compatível [FECHADO na Round 18]

- Localização do fechamento: `core/state_store.py:971-988`, `tests/test_state_store.py:1366-1382`
- Descrição: o boundary canônico de persistência só validava que `expected_revision` ainda batia com a revisão atual em disco; ele não rejeitava um payload com `revision` menor que a já persistida.
- Como reproduzir: persistir `revision=0`, depois `save_state(revision=1, expected_revision=0)` e em seguida `save_state(revision=0, expected_revision=1)`.
- Causa raiz confirmada: a monotonicidade histórica da revisão ficava implícita nos chamadores que usam `_bump_revision(...)`, mas não era imposta pelo próprio `save_state()`.
- Debate: a oposição não encontrou um fluxo CLI suportado que explorasse o downgrade diretamente, mas também não falsificou o furo do boundary baixo nível; a correção vencedora foi endurecer o próprio `save_state()` e manter os chamadores observability-only com `revision` igual ao atual.
- Fechamento observado: `save_state()` agora carrega o estado atual sempre que `state.json` já existe e falha fechado com `state revision must not go backwards` quando o payload tenta regredir a revisão persistida.
- Teste que cristalizou o fechamento: `tests/test_state_store.py:1366` — `StateStoreTests.test_save_state_rejects_revision_regression_even_with_matching_expected_revision`

### MÉDIO — `apply` single-file recarregava `state.json` desnecessariamente antes da primeira mutação [FECHADO na Round 15]

- Localização do fechamento: `cli/commands/apply.py:266-279`, `tests/test_alpha_runtime.py:4394-4444`
- Descrição: o caminho single-file fazia o preflight completo com `validate_state()` e depois recarregava o mesmo estado para `read_sources()`, `read_agent_runtime()` e uma segunda `read_agent_runtime()`, mesmo sem batch multi-file.
- Como reproduzir: instrumentar `StateStore.load_state()` ao redor de `run_apply()` com uma única action `fs.create_file` e contar as hidratações do fluxo.
- Causa raiz confirmada: `run_apply()` montava `registered_paths` e `agent_runtime` por superfícies separadas, em vez de reaproveitar a leitura combinada já exposta por `StateStore.read_snapshot_and_runtime()`.
- Debate: os dois `ALTO` remanescentes foram adjudicados como `Grupo 6`; isso liberou o próximo slice executável de menor risco, o hotspot de custo em `apply`.
- Fechamento observado: `run_apply()` agora lê `snapshot + runtime` uma única vez no preflight single-file; o fluxo completo caiu de `6` para `4` chamadas de `load_state()`, e a contagem até o boundary da primeira `apply_action()` caiu de `4` para `2`.
- Teste que cristalizou o fechamento: `tests/test_alpha_runtime.py:4394` — `AlphaRuntimeTests.test_apply_single_file_uses_one_canonical_state_load_for_snapshot_and_runtime`

### MÉDIO — `verify` recarregava `state.json` no preflight e fazia o CLI depender de `_runtime_lock()` privado [FECHADO na Round 19]

- Localização do fechamento: `core/state_store.py:1717-1789`, `core/verification_runtime.py:373-399`, `cli/commands/verify.py:16-35`
- Descrição: `run_verify()` abria `with store._runtime_lock():`, chamava `validate_state()`, e depois fazia `read_agent_runtime()` para buscar o mesmo runtime já coberto pelo preflight, mantendo a duplicação de hidratação e acoplando a orquestração do CLI a um método privado do core.
- Como reproduzir: instrumentar `StateStore.load_state()` ao redor de `run_verify()` com um plano mínimo `A2` e um único comando `read_only`; o caminho feliz fazia `4` chamadas de `load_state()`, sendo `2` antes do primeiro `run_verification_commands()`.
- Causa raiz confirmada: o ciclo transacional de `verify` estava montado no CLI em vez de ficar no core, então o lock privado e o reload de runtime escapavam pela fronteira errada.
- Debate: a primeira proposta de simplesmente soltar o lock do CLI foi falsificada por risco de TOCTOU; a correção vencedora foi mover a transação para um helper do core, preservando a serialização inteira e eliminando o reload redundante.
- Fechamento observado: `verify` agora executa a transação completa por `execute_verification_cycle(...)`, o CLI não toca mais `_runtime_lock()` diretamente, o preflight reaproveita o runtime validado sem um `read_agent_runtime()` extra, o helper falha fechado se `root` e `StateStore` divergirem, e o branch de validação bloqueada ficou cristalizado sem executar comandos nem persistir `verification`.
- Testes que cristalizaram o fechamento:
  - `tests/test_verification_runtime.py:21` — `VerificationRuntimeTests.test_run_verify_uses_core_transaction_without_read_agent_runtime_reload`
  - `tests/test_verification_runtime.py:213` — `VerificationRuntimeTests.test_execute_verification_cycle_returns_without_commands_when_validation_fails`
  - `tests/test_verification_runtime.py:272` — `VerificationRuntimeTests.test_execute_verification_cycle_rejects_store_root_mismatch`
  - `tests/test_alpha_runtime.py:4559` — `AlphaRuntimeTests.test_verify_uses_one_canonical_runtime_reload_before_command_execution`

### MÉDIO — `verify` podia executar comandos antes de provar a posse da sessão ativa [FECHADO nesta sessão]

- Localização do fechamento: `core/verification_runtime.py:385-400`
- Descrição: o preflight transacional de `verify` validava o estado e executava `run_verification_commands(...)` antes de verificar se o caller ainda possuía a sessão ativa; a checagem de `expected_session_token` só acontecia em `update_agent_verification(...)`, depois do subprocesso.
- Como reproduzir: abrir uma sessão válida, persistir um plano com `required_command_ids`, e chamar `run_verify()` sem `session_token`; o comando chegava ao boundary de execução e só falhava ao tentar persistir a verificação.
- Causa raiz confirmada: a autoridade de ownership já existia em `StateStore._read_owned_active_session(...)`, mas o `execute_verification_cycle(...)` ainda não reaproveitava esse guard antes do primeiro subprocesso.
- Debate: a prova de parada confirmou o bypass em P2 e a lacuna de cobertura em P5; não houve falsificação do risco e a menor correção segura ficou contida no boundary do runtime, sem tocar `core/validation.py`.
- Fechamento observado: `execute_verification_cycle(...)` agora exige sessão ativa compatível com `expected_session_token` ainda sob o lock canônico, então `run_verify()` responde `session_token_required` antes de qualquer comando e preserva `verification.status == "idle"` quando a posse falha.
- Teste que cristalizou o fechamento: `tests/test_verification_runtime.py:285` — `VerificationRuntimeTests.test_run_verify_requires_session_token_before_running_commands`

### MÉDIO — falha em `prepare_project_sandbox()` abortava `verify` sem audit trail nem `verification_record` canônico [FECHADO nesta sessão]

- Localização do fechamento: `core/verification_runtime.py:138-158`, `core/verification_runtime.py:241-264`
- Descrição: quando o sandbox de `verify` falhava antes do primeiro subprocesso, o runtime convertia o `OSError` em `VerificationRuntimeError`, mas saía sem registrar `verify_failed` e sem persistir um resultado em `agent_runtime.verification`.
- Como reproduzir: forçar `prepare_project_sandbox()` a lançar `OSError` durante `run_verify()` com um plano válido e pelo menos um comando `allow_in_verify`.
- Causa raiz confirmada: o boundary já tinha tratamento canônico para falha de launch e para falha de persistência de artifacts pós-run, mas o branch pré-comando ainda saía antes de produzir qualquer evento ou record de verificação.
- Debate: a prova de parada em P3 confirmou a lacuna de auditabilidade; o menor patch seguro ficou restrito ao `verification_runtime`, reaproveitando o contrato atual de `verification.checks` sem tocar `core/validation.py`.
- Fechamento observado: a falha de sandbox agora registra `verify_failed` com `reason_code=sandbox_prepare_failed` e devolve um `verification_record` `failed` com `check-state` falho, que segue o mesmo caminho canônico de persistência já usado nos demais resultados de `verify`.
- Teste que cristalizou o fechamento: `tests/test_verification_runtime.py:347` — `VerificationRuntimeTests.test_run_verify_records_failed_verification_when_sandbox_prepare_fails`

### MÉDIO — `rollback` de `fs.move` podia deixar diretório vazio residual no destino [FECHADO nesta sessão]

- Localização do fechamento: `core/action_runtime.py:77-97`, `core/action_runtime.py:738-756`, `core/action_runtime.py:939-962`
- Descrição: quando `apply` de `fs.move` precisava materializar uma árvore nova para o destino, o `rollback` restaurava o arquivo na origem, mas deixava o diretório recém-criado vazio no workspace.
- Como reproduzir: aplicar `fs.move` de `draft.txt` para `notes/archive/draft.txt` com `overwrite=false` e depois rodar `cerebro rollback --action-id act-move`.
- Causa raiz confirmada: o `apply` já criava `target.parent` em [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:739>), mas o `rollback` só fazia `shutil.move(str(target), str(source))` e não limpava a árvore vazia resultante quando não havia `target_preimage_ref`.
- Debate: o slice ficou isolado no runtime de action; não exigiu `validation.py`, não alterou contrato persistido e a menor correção segura foi registrar os diretórios criados no `apply` e podá-los no `rollback` apenas se continuarem vazios.
- Fechamento observado: `fs.move` agora persiste `created_target_dirs` em `details` durante o `apply` e `rollback_action()` remove esses diretórios por best-effort quando o destino não precisa ser restaurado com preimage.
- Teste que cristalizou o fechamento: `tests/test_alpha_runtime.py:3049` — `AlphaRuntimeTests.test_rollback_move_prunes_empty_destination_tree_created_by_apply`

### MÉDIO — `rollback` de `fs.create_file` no caso `create-new` podia deixar diretório vazio residual [FECHADO nesta sessão]

- Localização do fechamento: `core/action_runtime.py:686-709`, `core/action_runtime.py:913-922`
- Descrição: quando `apply` de `fs.create_file` precisava materializar uma árvore nova para o destino, o `rollback` removia o arquivo criado, mas deixava a árvore recém-criada vazia no workspace.
- Como reproduzir: aplicar `fs.create_file` em `notes/archive/draft.txt` com `overwrite=false` e depois rodar `cerebro rollback --action-id act-create`.
- Causa raiz confirmada: o runtime já sabia podar diretórios vazios para `fs.move`, mas o branch `created_new` de `fs.create_file` só fazia `target.unlink()` e não registrava nem limpava os diretórios criados pelo `apply`.
- Debate: o slice ficou local ao runtime de actions; não exigiu `validation.py`, não alterou contrato externo e reaproveitou a mesma mecânica de pruning já consolidada no fechamento de `fs.move`.
- Fechamento observado: `fs.create_file` agora persiste `created_target_dirs` em `details` no caso `create-new`, e `rollback_action()` remove por best-effort esses diretórios quando ficarem vazios após o unlink do arquivo criado.
- Teste que cristalizou o fechamento: `tests/test_alpha_runtime.py:3106` — `AlphaRuntimeTests.test_rollback_create_new_prunes_empty_destination_tree_created_by_apply`

### MÉDIO — faltava regressão explícita para perda de `.cerebro/state.json` logo após `init` [FECHADO nesta sessão]

- Localização do fechamento: `tests/test_validate.py:888-902`
- Descrição: o runtime já tratava `state.json` ausente como `state_missing`, mas não havia teste cobrindo a sequência real `run_init()` seguido de perda do arquivo canônico antes do primeiro `validate`.
- Como reproduzir: rodar `cerebro init`, remover `.cerebro/state.json` e depois rodar `cerebro validate`.
- Causa raiz confirmada: lacuna de cobertura, não falha do runtime. O branch canônico já existe em `core/state_store.py:1723-1728` e a tradução user-facing já existe em `cli/output.py:28-48`.
- Debate: o item já vinha priorizado em `WEAKNESS_REPORT.md` como maior gap de cobertura cega; o menor patch seguro foi só cristalizar o comportamento real no teste de CLI.
- Fechamento observado: a regressão nova garante `exit_code == 1`, `state_missing`, mensagem amigável de diretório/`cerebro init` e ausência de `internal_error`.
- Teste que cristalizou o fechamento: `tests/test_validate.py:888` — `ValidateCommandTests.test_validate_reports_state_missing_after_initialized_state_file_is_deleted`

### MÉDIO — faltava um teste contínuo único para `bootstrap -> validate/analyze -> plan -> apply -> verify -> rollback` [FECHADO nesta sessão]

- Localização do fechamento: `tests/test_alpha_runtime.py:2185-2260`
- Descrição: o contrato operacional já estava bem coberto por partes, mas não havia um único teste que executasse o fluxo contínuo completo com comandos reais, posse de sessão explícita e invalidação final de `verification` após `rollback`.
- Como reproduzir: antes do fechamento, a cobertura relevante ficava espalhada entre `tests/test_bootstrap_scan.py`, `tests/test_validate.py` e `tests/test_alpha_runtime.py`, sem um round-trip único do começo ao fim.
- Causa raiz confirmada: lacuna de cobertura integrada, não bug novo de runtime. Os comandos reais já existiam e já eram testados isoladamente, mas faltava a prova do acoplamento operacional entre eles no mesmo fluxo.
- Debate: os `ALTO` remanescentes foram mantidos em `Grupo 6`; isso liberou o menor slice corretivo seguro desta rodada, que era cristalizar o fluxo contínuo num único teste sem tocar `core/validation.py` nem contrato persistido.
- Fechamento observado: a regressão nova executa `run_init()`, `run_validate()`, `run_analyze()` com `session_token`, `run_plan()`, `run_apply()`, `run_verify()` e `run_rollback()` no mesmo projeto temporário, e confirma ao final action `rolled_back`, `verification.status == "idle"` e `validation_passed`.
- Teste que cristalizou o fechamento: `tests/test_alpha_runtime.py:2185` — `AlphaRuntimeTests.test_continuous_flow_from_bootstrap_validate_analyze_plan_apply_verify_to_rollback`

### MÉDIO — `verify` estourava o ceiling validado ao combinar `32` comandos reais com o `check-state` sintético [FECHADO nesta sessão]

- Localização do fechamento: `core/verification_runtime.py:231-238`
- Descrição: o runtime aceitava um plano com `32` comandos `allow_in_verify`, mas o caminho de execução sempre acrescentava o `check-state` sintético e tentava persistir `33` entries em `verification.checks`, acima do limite canônico de `32`.
- Como reproduzir: persistir um plano válido com `32` comandos verificáveis e chamar `run_verify()` sem subset; o caminho terminava em `invalid_agent_verification_checks`.
- Causa raiz confirmada: o budget efetivo de `verify` era `31` comandos reais, mas o boundary de execução só descobria isso tarde demais, ao passar o `verification_record` já inflado para a validação do estado.
- Debate: a oposição não encontrou correção menor do que um guard de preflight no próprio runtime; o mediador aprovou o patch local porque ele não toca `core/validation.py` nem o contrato persistido.
- Fechamento observado: `run_verification_commands()` agora falha cedo com `VerificationRuntimeError` quando `len(selected) + 1` excede `MAX_VERIFICATION_CHECKS`, explica que um slot é reservado para `check-state`, e impede tanto a persistência inválida quanto o erro tardio `invalid_agent_verification_checks`.
- Teste que cristalizou o fechamento: `tests/test_verification_runtime.py:18` — `VerificationRuntimeTests.test_run_verify_fails_early_when_selected_commands_plus_state_gate_exceed_limit`

### MÉDIO — `runtime.lock` órfão com PID inválido podia esperar até timeout no Windows [FECHADO nesta sessão]

- Localização do fechamento: `core/state_store.py:4865-4882`
- Descrição: o recovery do lock dependia do probe `os.kill(pid, 0)` para decidir se o dono ainda estava ativo; no Windows, um PID inválido podia devolver `OSError [WinError 87]` e o runtime tratava isso como “talvez vivo”, mantendo o lock órfão até timeout.
- Como reproduzir: persistir `.cerebro/runtime.lock` com um PID inválido e chamar `validate_state()`; antes do fechamento, o caminho podia cair no mesmo timeout usado para contenção real.
- Causa raiz confirmada: `_pid_is_running()` tratava `OSError` genérico como owner ativo, sem distinguir o caso específico `WinError 87`, que neste host significa probe inválido para PID inexistente.
- Debate: não houve disputa estrutural; o menor patch seguro ficou restrito ao helper de probe no `StateStore`, e a cobertura nova também cristaliza o caso oposto em que timeout continua correto para owner PID ainda vivo.
- Fechamento observado: `_pid_is_running()` agora classifica `ProcessLookupError`, `errno.ESRCH` e `WinError 87` como owner inativo, permitindo que `_try_recover_stale_runtime_lock()` limpe o lock órfão; o timeout permanece para locks cujo owner PID ainda parece ativo.
- Testes que cristalizaram o fechamento:
  - `tests/test_state_store.py:2307` — `StateStoreTests.test_runtime_lock_recovers_stale_lock_when_pid_probe_is_invalid_parameter`
  - `tests/test_state_store.py:2320` — `StateStoreTests.test_runtime_lock_timeout_reports_stale_lock_guidance_when_owner_still_looks_alive`
  - `tests/test_validate.py:835` — `ValidateCommandTests.test_validate_command_reports_runtime_lock_timeout_as_operation_failed`
  - `tests/test_validate.py:906` — `ValidateCommandTests.test_resume_command_reports_runtime_lock_timeout_as_operation_failed`

### MÉDIO — `command_registry.commands[*].cwd` não tinha regressão direta cobrindo validator vs runtime [FECHADO nesta sessão]

- Localização do fechamento: `tests/test_validate.py`, `tests/test_action_runtime.py`, `tests/test_verification_runtime.py`
- Descrição: o boundary de `command_registry.commands[*].cwd` existia dividido entre camadas, mas sem regressão explícita que provasse o contrato real: o validator só exigia string não-vazia, enquanto `apply` e `verify` rejeitavam `cwd` escapando do root apenas no runtime.
- Como reproduzir: antes do fechamento, a suíte não tinha um teste direto que mostrasse `cwd=""` gerando `invalid_command_registry_command_cwd`, nem um teste que cristalizasse o caso `cwd="../escape"` sendo aceito pela validação e rejeitado mais tarde em `apply`/`verify`.
- Causa raiz confirmada: a cobertura estava indireta e não exercitava o split entre [core/validation.py](</d:/projetos_cli/cerebro/core/validation.py:442>), [core/action_runtime.py](</d:/projetos_cli/cerebro/core/action_runtime.py:838>) e [core/verification_runtime.py](</d:/projetos_cli/cerebro/core/verification_runtime.py:316>).
- Debate: não houve disputa estrutural; o slice vencedor foi só cobertura proporcional, sem alterar o contrato ainda inconsistente entre validator e runtime.
- Fechamento observado: a suíte agora prova o erro direto `invalid_command_registry_command_cwd` para `cwd` vazio, documenta que `cwd="../escape"` ainda passa na validação e cristaliza a rejeição fail-closed em `apply` e `verify` antes de qualquer subprocesso útil.
- Testes que cristalizaram o fechamento:
  - `tests/test_validate.py` — `ValidationFunctionTests.test_validate_state_rejects_empty_command_registry_cwd`
  - `tests/test_validate.py` — `ValidationFunctionTests.test_validate_state_accepts_command_registry_cwd_boundary_that_runtime_rejects_later`
  - `tests/test_action_runtime.py` — `ActionRuntimeCommandTests.test_exec_command_rejects_command_cwd_that_resolves_outside_root`
  - `tests/test_verification_runtime.py` — `VerificationRuntimeTests.test_run_verify_rejects_command_cwd_that_resolves_outside_root`

### MÉDIO — `core/command_sandbox.py` não tinha teste direto localizado [FECHADO nesta sessão]

- Localização do fechamento: `tests/test_command_sandbox.py`
- Descrição: o runtime dependia de `prepare_project_sandbox()`, `capture_tree_manifest()` e `summarize_manifest_diff()` para isolar `verify` e detectar mutação observável, mas a suíte não exercitava essas helpers diretamente.
- Como reproduzir: antes do fechamento, a busca em `tests/` só encontrava uso indireto via `verification_runtime`; não havia regressão explícita que provasse clone descartável do workspace nem que o diff de manifesto ignora churn puro de `mtime` em diretório.
- Causa raiz confirmada: lacuna de cobertura, não bug novo do core.
- Debate: não houve disputa estrutural; o menor patch seguro foi adicionar testes diretos sem tocar `core/`.
- Fechamento observado: a suíte agora prova que o sandbox clona o workspace sem retrocontaminar a árvore original e que o diff de manifesto ignora `mtime` de diretório, mas acusa drift real em arquivo.
- Testes que cristalizaram o fechamento:
  - `tests/test_command_sandbox.py` — `CommandSandboxTests.test_prepare_project_sandbox_clones_workspace_without_mutating_original_tree`
  - `tests/test_command_sandbox.py` — `CommandSandboxTests.test_capture_tree_manifest_diff_ignores_directory_mtime_churn_but_reports_file_drift`

### MÉDIO — `core/execution_policy.py` não tinha teste direto localizado [FECHADO nesta sessão]

- Localização do fechamento: `tests/test_execution_policy.py`
- Descrição: as regras centrais de policy já eram exercitadas indiretamente por `apply`, `verify` e `validate`, mas faltava uma regressão local que provasse diretamente o boundary de path mutável, o gate de execução de comandos e a regra canônica de approval exigido.
- Como reproduzir: antes do fechamento, a busca em `tests/` só encontrava consumo indireto por runtimes e validação; não havia um teste dedicado para `ensure_mutation_path_allowed()`, `ensure_command_allowed()`, `action_requires_approval()` e `required_action_approval_error()`.
- Causa raiz confirmada: lacuna de cobertura, não bug novo do core.
- Debate: não houve disputa estrutural; o menor patch seguro foi só cobertura proporcional sem tocar `core/`.
- Fechamento observado: a suíte agora prova rejeição de path fora do root, de path protegido e de source registrado; prova bloqueio de comandos por autonomia/argv/prefixo; e cristaliza a semântica explícita de approval requerido.
- Testes que cristalizaram o fechamento:
  - `tests/test_execution_policy.py` — `ExecutionPolicyTests.test_ensure_mutation_path_allowed_rejects_outside_protected_and_registered_paths`
  - `tests/test_execution_policy.py` — `ExecutionPolicyTests.test_ensure_command_allowed_enforces_autonomy_argv_and_blocklist`
  - `tests/test_execution_policy.py` — `ExecutionPolicyTests.test_action_requires_approval_ignores_invalid_entries_and_required_action_approval_error_is_explicit`

### MÉDIO — `core/runtime_event_window.py` não tinha teste direto localizado [FECHADO nesta sessão]

- Localização do fechamento: `tests/test_runtime_event_window.py`
- Descrição: o helper canônico que recorta a janela de eventos do plano mais recente já influenciava `discipline_runtime` e `decision_runtime`, mas não tinha regressão local que cristalizasse diretamente o boundary “último `plan_updated` vence”, a normalização de ruído não-dict e o fail-closed para input inválido.
- Como reproduzir: antes do fechamento, a busca em `tests/` só encontrava consumo indireto por `choose_next_task()`; não havia teste dedicado para `events_since_latest_plan_update()`.
- Causa raiz confirmada: lacuna de cobertura, não bug novo do core.
- Debate: não houve disputa estrutural; o menor patch seguro foi só cobertura proporcional em `tests/` e alinhamento factual em `docs/`.
- Fechamento observado: a suíte agora prova que o helper devolve apenas a cauda pertencente ao `plan_updated` mais recente, mantém todos os eventos normalizados quando não há boundary de plano e falha fechado para input não sequencial.
- Testes que cristalizaram o fechamento:
  - `tests/test_runtime_event_window.py` — `RuntimeEventWindowTests.test_events_since_latest_plan_update_returns_latest_plan_suffix`
  - `tests/test_runtime_event_window.py` — `RuntimeEventWindowTests.test_events_since_latest_plan_update_returns_all_normalized_events_without_plan_boundary`
  - `tests/test_runtime_event_window.py` — `RuntimeEventWindowTests.test_events_since_latest_plan_update_fail_closes_for_non_sequence_inputs`

### MÉDIO — `fs.move` com `from == to` podia parecer aplicado e envenenar o rollback [FECHADO nesta sessão]

- Localização do fechamento: `core/discipline_runtime.py`
- Descrição: uma action `fs.move` com origem e destino idênticos podia passar por `apply`, não alterar o workspace e ainda assim deixar um `action_record` `applied`; o rollback posterior então falhava com `original source path already exists and blocks rollback`.
- Como reproduzir: criar `draft.txt`, persistir uma action `fs.move` com `"from": "draft.txt"` e `"to": "draft.txt"`, rodar `cerebro apply` e depois `cerebro rollback --action-id ...`.
- Causa raiz confirmada: `evaluate_action_effectiveness()` bloqueava no-ops de `fs.create_file` e `fs.write_patch`, mas não reconhecia o no-op estrutural de `fs.move` com paths resolvidos idênticos.
- Debate: a varredura proativa confirmou o bug no fluxo real; o mediador aprovou o menor patch local no boundary de disciplina porque ele evita a mutação falsa sem tocar `core/validation.py` nem o contrato persistido.
- Fechamento observado: `evaluate_action_effectiveness()` agora rejeita `fs.move` same-path quando a origem existe, então `run_apply()` responde `action_no_effect`, registra `apply_blocked`, não cria `action_record` canônico e preserva o arquivo intacto.
- Testes que cristalizaram o fechamento:
  - `tests/test_runtime_units.py` — `RuntimeUnitTests.test_evaluate_action_effectiveness_blocks_same_path_move_when_source_exists`
  - `tests/test_alpha_runtime.py` — `AlphaRuntimeTests.test_apply_blocks_same_path_move_before_mutation_and_action_record`

### MÉDIO — compensação batch abortava no primeiro restore falho e deixava paths posteriores sem recovery [FECHADO nesta sessão]

- Localização do fechamento: `core/action_runtime.py`
- Descrição: quando `guarded_apply_batch()` ou `guarded_rollback_batch()` já estavam compensando um batch falho, a primeira exceção de `_restore_path_from_snapshot()` abortava o loop de restore; os caminhos restantes ficavam sem tentativa de recovery mesmo tendo snapshot válido.
- Como reproduzir: forçar falha no primeiro `_restore_path_from_snapshot()` durante a compensação de batch e observar que os paths seguintes permaneciam mutados.
- Causa raiz confirmada: a compensação iterava os restores em série dentro de um único `try`, então o primeiro `OSError` interrompia a restauração dos demais paths.
- Debate: a prova de parada `P3` reproduziu o bug; o menor patch seguro ficou no boundary de `core/action_runtime.py`, preservando fail-closed mas convertendo a compensação em best effort antes de propagar o erro.
- Fechamento observado: a compensação agora tenta restaurar todos os paths capturados, acumula os restores que ainda falharam e só então levanta `ActionRuntimeError` estável com contagem e primeiro erro; paths posteriores já recuperáveis voltam ao snapshot original.
- Testes que cristalizaram o fechamento:
  - `tests/test_alpha_runtime.py` — `AlphaRuntimeTests.test_multi_file_apply_batch_continues_best_effort_restore_after_first_restore_failure`
  - `tests/test_alpha_runtime.py` — `AlphaRuntimeTests.test_rollback_batch_continues_best_effort_restore_after_first_restore_failure`

### MÉDIO — approval/retry de `exec.command` podia sobreviver a drift do `command_registry` [FECHADO nesta sessão]

- Localização do fechamento: `core/action_runtime.py`, `core/discipline_runtime.py`, `cli/commands/apply.py`
- Descrição: uma action `exec.command` aprovada podia reaproveitar a mesma approval mesmo depois que o `command_registry` mudava o comando resolvido sob o mesmo `command_id`; o retry também continuava tratando o novo comando como se fosse a mesma tentativa.
- Como reproduzir: aprovar `exec.command` para `cmd-001`, alterar `argv` do mesmo `command_id` no `state.json` sem passar por `plan_updated` e rodar `cerebro apply` de novo.
- Causa raiz confirmada: o fingerprint de approval/retry era calculado só do payload normalizado (`kind + command_id`), enquanto a execução resolvia o comando real depois, a partir do `command_registry` atual.
- Debate: o fechamento local seguro foi tornar `exec.command` snapshot-aware no fingerprint/evidence e persistir a mesma assinatura do comando resolvido em `details`, sem tocar `schema.py` ou `validation.py`.
- Fechamento observado: approval e retry agora incorporam uma assinatura estável do snapshot resolvido do comando (`argv`, `cwd`, `timeout_ms`, `determinism`, `side_effect`, `risk`, `allow_in_verify`), então drift no registry muda o fingerprint, exige novo gate e deixa de reaproveitar approval antiga silenciosamente.
- Fechamento observado: se o `command_id` desaparecer do `command_registry`, `run_apply()` agora falha fechado antes de approval/retry com `unknown command_id`, sem criar nova approval nem executar subprocesso.
- Testes que cristalizaram o fechamento:
  - `tests/test_alpha_runtime.py` — `AlphaRuntimeTests.test_exec_command_requires_fresh_approval_when_registry_changes_without_replan`
  - `tests/test_alpha_runtime.py` — `AlphaRuntimeTests.test_exec_command_missing_registry_entry_blocks_before_approval_reuse`
  - `tests/test_runtime_units.py` — `RuntimeUnitTests.test_exec_command_retry_allows_registry_snapshot_drift_as_new_attempt`

### MÉDIO — teste isolado de `open_session()` oscilava por usar storage externo compartilhado [FECHADO nesta sessão]

- Localização do fechamento: `tests/test_state_store.py:1692-1726`
- Descrição: `StateStoreTests.test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails` isolava só o root temporário do projeto, mas comparava `claims_dir` e `live_proofs_dir` no storage externo do usuário.
- Como reproduzir: rodar `python -m unittest tests.test_state_store.StateStoreTests.test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails -v` repetidas vezes no mesmo host; o teste alternava entre `ok` e `FAIL` sem mudança de código.
- Causa raiz confirmada: o runtime continua resolvendo claims/live-proofs fora do projeto por padrão (`core/state_store.py:2550-2575`), e esse teste específico não sandboxava `CEREBRO_SESSION_CLAIMS_DIR` / `CEREBRO_SESSION_LIVE_PROOFS_DIR` antes de comparar listas before/after.
- Debate: proponente e mediador convergiram na menor correção local no próprio teste; a oposição não reproduziu bug determinístico do core e só confirmou o acoplamento ao path global.
- Fechamento observado: o teste agora executa dentro de diretórios temporários explícitos para claims/live-proofs, preserva a mesma asserção de rollback e deixou de oscilar no rerun isolado.
- Teste que cristalizou o fechamento: `tests/test_state_store.py:1692` — `StateStoreTests.test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails`

### MÉDIO — `open_session()` podia deixar `session_registry_mismatch` se a reversão de `state.json` também falhasse [FECHADO na Round 16]

- Localização do fechamento: `core/state_store.py:1154-1181`, `core/state_store.py:1399-1405`
- Descrição: quando a gravação final de `session.local.json` falhava depois de o registro canônico já estar persistido, e a tentativa subsequente de restaurar `pre_open_state` também falhava, `open_session()` saía com erro mas podia deixar `active_session_id`/`active_session_claim_id` ativos e os artifacts externos ainda presentes.
- Como reproduzir: forçar uma falha em `_write_json_atomic(self.session_path, ...)` e, na sequência, forçar a segunda gravação de `state.json` durante o rollback.
- Causa raiz confirmada: o boundary já tinha recovery para o split “registry active + session.local.json ausente”, mas o catch de `open_session()` abortava antes de reutilizar esse caminho quando o rollback de `state.json` falhava.
- Debate: a prova de parada convergiu no mesmo achado em P2 e P5; o slice vencedor foi o menor patch local no `StateStore`, sem tocar `core/validation.py`.
- Fechamento observado: `open_session()` agora tenta limpar o resíduo via `_recover_failed_open_session_registry_residue(...)` antes de propagar a falha composta, então a sessão continua abortando, mas o estado canônico volta para a forma válida sem sessão e `validate_state()` permanece verde.
- Teste que cristalizou o fechamento: `tests/test_state_store.py:1732` — `StateStoreTests.test_open_session_discards_registry_residue_when_state_restore_after_session_file_failure_also_fails`

### MÉDIO — `rollback` muta workspace sem gate explícito de approval [FECHADO na Round 10]

- Localização: `cli/commands/rollback.py:81-101`
- Descrição: o comando seleciona actions e chama `rollback_action(...)` sem uma checagem equivalente a `_resolve_action_approval`.
- Como reproduzir: aplicar uma action reversível aprovada e depois rodar `cerebro rollback --action-id ...`.
- Causa raiz confirmada: `rollback` depende de validação e guarda de batch, mas não de approval explícito do passo reverso.
- Debate: sem divergência.
- Fechamento observado: o runtime endureceu o contrato canônico já existente em vez de inventar uma segunda política de rollback. `approval_required_kinds` continua sendo a única fonte canônica, `core/validation.py` agora rejeita action sensível em `applied`/`rolled_back` sem `approval_id` aprovado, e `cli/commands/rollback.py` recusa reverter actions sensíveis cujo approval original não esteja íntegro e aprovado.
- Testes que cristalizam o fechamento:
  - `tests/test_validate.py:269` — `ValidationFunctionTests.test_validate_state_rejects_applied_sensitive_action_without_approval_id`
  - `tests/test_alpha_runtime.py:2107` — `AlphaRuntimeTests.test_rollback_blocks_sensitive_action_without_approved_original_approval`

### MÉDIO — `close_session()` podia deixar `session_not_registered` ou falhar no meio do fechamento [FECHADO]

- Localização do fechamento: `core/state_store.py:1032-1086`, `core/state_store.py:1175-1315`, `core/state_store.py:4120-4158`, `cli/commands/checkpoint.py:22-80`, `cli/commands/session_discard.py:12-74`
- Descrição: `close_session()` limpava o registro canônico antes de remover claim/live-proof e antes de apagar `session.local.json`, então uma falha no meio podia deixar `session_not_registered` ou travar o descarte in-band.
- Como reproduzir: provocar falha entre a limpeza de `active_session_id`/`active_session_claim_id` e a remoção final de `session.local.json`, ou tentar recuperar uma sessão já partida durante `checkpoint`/`session-discard`.
- Causa raiz confirmada: o fechamento da sessão ainda era uma sequência multi-passos sem rollback dos artifacts externos quando o unlink final falhava, e o caminho operacional não tinha um descarte explícito para limpar com segurança um resíduo `session_not_registered`.
- Debate: sem divergência.
- Fechamento observado: `close_session()` agora captura snapshots do registro e dos artifacts externos, restaura tudo se a remoção final de `session.local.json` falha, `update_checkpoint(..., close_session_on_success=True)` fecha a sessão dentro do mesmo fluxo persistente, e `session-discard` passou a limpar o resíduo recuperável sem fingir continuidade ininterrupta.
- Testes que cristalizaram o fechamento:
  - `tests/test_state_store.py:2142` — `StateStoreTests.test_discard_session_clears_stale_session_records_trace_without_bumping_revision`
  - `tests/test_validate.py:1153` — `ValidateCommandTests.test_session_discard_clears_stale_session_and_requires_explicit_reopen`
  - `tests/test_validate.py:1973` — `ValidateCommandTests.test_checkpoint_command_reports_operation_failed_without_mutating_state_when_session_close_fails`
  - `tests/test_validate.py:1012` — `ValidateCommandTests.test_import_context_reports_operation_failed_without_mutating_state_when_session_close_fails`
  - `tests/test_validate.py:1064` — `ValidateCommandTests.test_import_context_reports_operation_failed_without_losing_session_when_state_write_fails`
  - `tests/test_validate.py:2027` — `ValidateCommandTests.test_checkpoint_command_reports_operation_failed_without_losing_session_when_state_write_fails`
- Residual fechado nesta sessão: a janela remanescente de `_save_state_with_refreshed_session()` foi eliminada na Round 13 por meio do journal local `session.refresh.pending.json`.

### MÉDIO — `close_session()` podia engolir leitura inválida de `session.local.json` e seguir limpando a sessão [FECHADO nesta sessão]

- Localização: `core/state_store.py:1189-1267`
- Descrição: quando `_read_session_file()` levantava exceção inesperada ou retornava `session_errors`, `close_session()` zerava `session_data/session_errors` e seguia para limpar registry, claim/live-proof e `session.local.json`, escondendo o defeito de leitura e abrindo caminho para sucesso silencioso nos chamadores CLI.
- Como reproduzir: abrir uma sessão válida e forçar `_read_session_file()` a falhar durante `close_session()`, ou corromper `session.local.json` antes do fechamento.
- Causa raiz confirmada: o boundary de fechamento tratava falha de leitura como ausência tolerável de sidecar, em vez de tratá-la como precondição inválida para cleanup.
- Debate: sem divergência no fechamento; reviewer e architect concordaram que o menor patch seguro era fail-closed no próprio boundary, com trilha via `_record_trace_only_events()`.
- Fechamento observado: `close_session()` agora registra `session_close_failed` e levanta `StateStoreError` antes de limpar registry, claim ou live-proof quando a sessão não é legível/validável; `import-context` e `checkpoint` traduzem isso para `operation_failed` sem mutação parcial.
- Localização do fechamento: `core/state_store.py:1189-1267`
- Testes que cristalizaram o fechamento:
  - `tests/test_state_store.py:2347` — `StateStoreTests.test_close_session_fails_closed_and_records_trace_when_session_file_is_invalid`
  - `tests/test_validate.py:1064` — `ValidateCommandTests.test_import_context_reports_operation_failed_without_mutating_state_when_session_file_read_raises_during_close`
  - `tests/test_validate.py:2031` — `ValidateCommandTests.test_checkpoint_command_reports_operation_failed_without_mutating_state_when_session_file_read_raises_during_close`

### MÉDIO — `verify` parcial sai com código `0` [FECHADO na Round 9]

- Localização: `cli/commands/verify.py:107-142`
- Descrição: quando os checks executados passam mas a cobertura obrigatória fica incompleta, o comando imprime `verification_partial` e ainda retorna `0`.
- Como reproduzir: definir mais de um comando obrigatório e executar só um com `--command-id`.
- Causa raiz confirmada: o exit code só vira `1` quando algum check executado falha; cobertura parcial não altera o código de processo.
- Debate: sem divergência.
- Fechamento observado: `run_verify()` agora retorna `1` quando `verification_record["status"] == "passed"` mas `full_required_coverage` continua falso, preservando `verification_partial`, `pending_action_ids` e o estado persistido da verificação.
- Localização do fechamento: `cli/commands/verify.py:61-96`
- Testes que cristalizaram o fechamento:
  - `tests/test_alpha_runtime.py:1736` — `AlphaRuntimeTests.test_verify_subset_keeps_pending_actions_until_full_required_coverage_runs`
  - `tests/test_status_export.py:292` — `StatusExportTests.test_export_flags_incomplete_required_verification_coverage`

### MÉDIO — `verify` redundante pode mascarar drift fora do runtime [FECHADO na Round 9]

- Localização: `cli/commands/verify.py:17-40`
- Descrição: o bloqueio de verify redundante depende de `verification.status == passed`, ausência de pendências e subconjunto de comandos já cobertos, sem medir drift do workspace entre o verify anterior e o atual.
- Como reproduzir: passar em um verify, alterar o workspace fora do runtime, rodar `cerebro verify` de novo.
- Causa raiz confirmada: `_redundant_verify_reason()` não observa mudanças de estado reais fora de `pending_action_ids`.
- Debate: sem divergência.
- Fechamento observado: o bloqueio redundante foi removido do caminho de `run_verify()`, então drift fora do runtime não é mais mascarado; reruns completos e subsets explícitos voltam a ser permitidos quando o workspace mudou externamente.
- Localização do fechamento: `cli/commands/verify.py:16-38`
- Testes que cristalizaram o fechamento:
  - `tests/test_alpha_runtime.py:4330` — `AlphaRuntimeTests.test_verify_allows_rerun_after_workspace_drift_outside_runtime`
  - `tests/test_alpha_runtime.py:4351` — `AlphaRuntimeTests.test_verify_allows_explicit_subset_rerun_after_workspace_drift_outside_runtime`

### MÉDIO — default file-backed abriu disclosure e override de paths não documentados [FECHADO na Round 9]

- Localização: `core/state_store.py:2216-2218`, `core/state_store.py:2749-2755`, `core/state_store.py:2869-2875`, `docs/operations/OPERATIONS_BASELINE.md:89-91`
- Descrição: com backend file-backed como default, erros de leitura/ausência de claim/live-proof persistem caminhos absolutos externos em mensagens de validação, e env vars podem redirecionar os artifacts para qualquer diretório resolvido pelo processo.
- Como reproduzir: definir `CEREBRO_SESSION_CLAIMS_DIR`/`CEREBRO_SESSION_LIVE_PROOFS_DIR` para caminho externo e provocar `session_claim_missing` ou `session_live_proof_missing`.
- Causa raiz confirmada: localização absoluta entra diretamente nas mensagens de erro e os overrides não têm boundary adicional.
- Debate: sem divergência.
- Fechamento observado: o backend file-backed continua aceitando overrides trusted-only, mas as mensagens persistidas passaram a expor apenas descritores redigidos (`session_claims/<claim_id>.json`, `session_live_proofs/<proof_id>.json`) em vez de paths absolutos resolvidos.
- Localização do fechamento: `core/state_store.py:2539-2566`, `core/state_store.py:3013-3019`, `core/state_store.py:3133-3139`
- Teste que cristalizou o fechamento: `tests/test_state_store.py:1874` — `StateStoreTests.test_file_backed_session_missing_errors_redact_external_paths`

### MÉDIO — falha antes do manifest final deixa archive sem manifest e retry perde a trilha de commit [FECHADO na Round 9]

- Localização: `core/state_store.py:1734-1775`, `core/state_store.py:1802-1808`
- Descrição: se a retenção mover artifacts e regravar `events.jsonl`, mas falhar antes de gravar `trash/retention/.../manifest.json`, o retry posterior encontra “no eligible cleanup candidates” e não conclui a trilha auditável daquele archive.
- Como reproduzir: forçar falha em `_write_json_atomic()` na primeira escrita de `trash/retention/.../manifest.json`.
- Causa raiz confirmada: o commit de retenção não tem journal/recovery step separado para manifest pendente.
- Debate: sem divergência.
- Fechamento observado: `apply_retention()` agora grava `manifest.pending.json` no próprio archive antes das mutações destrutivas e o rerun finaliza o mesmo archive pendente sem recalcular candidatos nem duplicar a trilha do cleanup.
- Localização do fechamento: `core/state_store.py:1742-1868`, `core/state_store.py:2005-2061`
- Testes que cristalizaram o fechamento:
  - `tests/test_validate.py:524` — `ValidateCommandTests.test_validate_retention_apply_rerun_is_safe_after_manifest_write_failure`
  - `tests/test_validate.py:591` — `ValidateCommandTests.test_validate_retention_apply_fails_when_retention_trace_append_degrades_and_rerun_is_safe`

## Problemas descartados pelo debate

- Nenhum conflito real apareceu entre os cinco agentes da onda 1, então não houve debate formal A/B/C.
- A única formulação estreitada na confirmação focada foi a do problema de retenção: o sistema não registra “estado saudável falso”; ele registra sucesso do `retention-apply` com `trace_status=degraded` e log potencialmente corrompido.

## Lacunas de cobertura

- `C1` [FECHADO na Round 9]: `core/validation.py:315` agora tem teste direto para `plan.current_task_id` órfão em `tests/test_validate.py:225` — `test_validate_state_rejects_orphan_current_task_id`.
- `C2` [FECHADO na Round 9]: `core/validation.py:892` agora tem teste direto para ciclo em `agent_runtime.plan.tasks[*].depends_on` em `tests/test_validate.py:238` — `test_validate_state_rejects_plan_task_cycles`.
- `C3` [FECHADO na Round 10]: o validator agora rejeita tanto action `applied` ligada a approval `rejected` quanto action sensível `applied` com `approval_id` ausente; cobertura direta em `tests/test_validate.py:254` e `tests/test_validate.py:269`.
- `C4` [FECHADO na Round 9]: a integridade de `verification.required_command_ids` agora tem testes diretos para `command_id` desconhecido e não permitido em `tests/test_validate.py:291` e `tests/test_validate.py:300`.
- `C5` [FECHADO na Round 9]: `core/validation.py:1020` agora tem teste direto para `owner_claim_id` vazio em `tests/test_validate.py:312` — `test_validate_session_rejects_empty_owner_claim_id`.
- `C6` [FECHADO na Round 9]: o boundary de `sources[].path` agora tem teste direto para path absoluto, traversal e separador inválido em `tests/test_validate.py:325` — `test_validate_state_rejects_invalid_source_path_boundaries`.
- `C7` [FECHADO nesta sessão]: `tests/test_analyze.py` agora cobre o caminho padrão sem `session_token` e a emissão explícita sob `emit_session_token=True`; cobertura direta em `tests/test_analyze.py:43`, `tests/test_analyze.py:94` e `tests/test_analyze.py:124`.
- `C8` [FECHADO nesta sessão]: `tests/test_validate.py` agora substitui os mocks estreitos de `StateStore.close_session`/`StateStore.save_state` por falhas reais de `Path.unlink` e `os.replace`, cristalizando rollback efetivo nos chamadores CLI `import-context` e `checkpoint`; cobertura direta em `tests/test_validate.py:1012`, `tests/test_validate.py:1064`, `tests/test_validate.py:1973` e `tests/test_validate.py:2027`.
- `C9` [FECHADO nesta sessão]: o ramo exato em que `_read_session_file()` explode dentro de `close_session()` agora está cristalizado também no CLI de `checkpoint`, além do core e de `import-context`; cobertura direta em `tests/test_state_store.py:2347`, `tests/test_validate.py:1064` e `tests/test_validate.py:2031`.

## Próximos passos

- Não há `CRÍTICO` confirmado aberto; o crítico de `exec.command` pós-mutação foi fechado na Round 11.
- Permanece `ALTO` aberto em `WEAKNESS_REPORT.md`: o gap de approval por efeito em `fs.create_file overwrite=true`.
- O item de approval por efeito continua reproduzível, mas saiu da trilha corretiva imediata porque a menor correção segura cruza `core/validation.py`; ele fica bloqueado para `Grupo 6` até decisão arquitetural explícita.
- Os riscos `MÉDIO` de `verify` parcial, `verify` redundante após drift, disclosure de paths file-backed e manifest pendente de retenção foram fechados na Round 9 com regressão cristalizada em teste.
- O residual corretivo de rollback approval foi fechado na Round 10; o gap posterior que continua aberto é o de effect-level approval em `fs.create_file overwrite=true`.
- Os residuais abertos e aceitos no estado atual são estes:
- gap de policy: `fs.create_file` com `overwrite=true` ainda sobrescreve arquivo existente sem approval explícito; o achado está em `docs/operations/WEAKNESS_REPORT.md` e segue bloqueado pelo freeze documental.
- `same-user tamper or restore` do authority store externo file-backed, ainda aceito como boundary residual em `docs/operations/OPERATIONS_BASELINE.md:90`.
- bypass residual de `verify` por tamper transitório perfeitamente restaurado, efeitos fora do root ou drift totalmente oculto, ainda aceito em `docs/operations/OPERATIONS_BASELINE.md:119-123`.
- ausência de garantia de atomicidade perfeita em `apply` e `rollback` contra writers externos arbitrários durante a execução, ainda aceita em `docs/operations/OPERATIONS_BASELINE.md:126-129` e `docs/operations/OPERATIONS_BASELINE.md:157`.
- Itens de backlog ainda abertos (`T102`, `T105`, `T106`) permanecem bloqueados por freeze/arquitetura; nesta sessão, o item de approval por efeito segue em `Grupo 6`.
