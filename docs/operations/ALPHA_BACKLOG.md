# Alpha Backlog

Backlog de continuidade para endurecimento do Alpha operacional. Os gates criticos abaixo foram fechados em fatias pequenas, reversiveis e testadas.

## Grupo 1 - Rollback Real e Recovery

### Subgrupo 1.1 - Restore completo
- [x] Restaurar `fs.create_file`.
- [x] Restaurar `fs.write_patch` por preimage com checagem de divergencia.
- [x] Restaurar `fs.move` com volta ao path original e restore opcional do alvo sobrescrito.
- [x] Restaurar `fs.delete_soft` a partir de `.cerebro/trash/`.

### Subgrupo 1.2 - Rollback por lote
- [x] Suportar `batch_id` em `apply`.
- [x] Reverter lote em ordem reversa com `cerebro rollback --batch-id`.

### Subgrupo 1.3 - Integracao com recovery
- [x] Persistir `rollback_ref` e `rollback_points` no estado canonico.
- [x] Atualizar auditoria e estado de acao durante rollback.

### Subgrupo 1.4 - Testes
- [x] Cobrir rollback por lote fim a fim.
- [x] Cobrir reversibilidade de acoes mutaveis suportadas.

## Grupo 2 - Aprovacao e Controle de Execucao

### Subgrupo 2.1 - Estados formais
- [x] Materializar `pending`, `approved` e `rejected` em `agent_runtime.approvals`.

### Subgrupo 2.2 - Gate antes de acao sensivel
- [x] Bloquear `fs.write_patch`, `fs.move`, `fs.delete_soft` e `exec.command` quando exigirem aprovacao.
- [x] Criar approval pendente automaticamente no primeiro bloqueio.

### Subgrupo 2.3 - Integracao com policy
- [x] Integrar `approval_required_kinds` em `execution_policy`.
- [x] Expor comando canonico `cerebro approve`.

### Subgrupo 2.4 - Testes
- [x] Cobrir fluxo `apply -> approval pending -> approve -> apply`.
- [x] Cobrir bloqueio por approval rejeitado ou pendente.

## Grupo 3 - Plano e DAG Operacional

### Subgrupo 3.1 - Dependencias entre tasks
- [x] Validar referencias de `depends_on`.
- [x] Bloquear tasks prontas quando dependencias nao estao concluídas.

### Subgrupo 3.2 - Aciclicidade
- [x] Validar DAG e rejeitar ciclos no plano.

### Subgrupo 3.3 - Estados formais de task
- [x] Materializar `ready`, `blocked`, `running`, `done`, `failed`.
- [x] Promover task para `done` apenas apos verificacao bem sucedida.

### Subgrupo 3.4 - Execucao segura
- [x] Vincular acoes a `task_id`.
- [x] Atualizar `current_task_id` e `plan.status` a cada transicao relevante.

## Grupo 4 - Command Registry Operacional

### Subgrupo 4.1 - Estrutura
- [x] Consolidar `agent_runtime.command_registry.commands`.

### Subgrupo 4.2 - Metadados
- [x] Persistir `determinism`, `side_effect`, `risk` e `allow_in_verify`.

### Subgrupo 4.3 - Execucao via registry
- [x] Executar `exec.command` apenas por `command_id`.
- [x] Executar `verify` apenas por comandos registrados e permitidos.

### Subgrupo 4.4 - Testes
- [x] Cobrir registry em `plan`, `apply` e `verify`.

## Grupo 5 - Verificacao Avancada

### Subgrupo 5.1 - Gates obrigatorios
- [x] Registrar gate estrutural `state`.
- [x] Executar gates de comando registrados.

### Subgrupo 5.2 - Verificacao por lote
- [x] Cobrir todas as `pending_action_ids` do lote verificado.

### Subgrupo 5.3 - Registro estruturado
- [x] Persistir `required_command_ids`, `pending_action_ids`, checks e artefatos.

### Subgrupo 5.4 - Bloqueio por falha
- [x] Bloquear novas mutacoes quando a verificacao falhou e ainda existem acoes pendentes.

## Grupo 6 - Invariantes do Sistema

### Subgrupo 6.1 - Estado canonico
- [x] Validar schema expandido com `command_registry`, `approvals`, `actions`, `verification`, `memory` e `audit`.

### Subgrupo 6.2 - Plano e execucao
- [x] Validar referencias cruzadas entre task, action, approval e verification.
- [x] Validar coerencia de status entre tasks, approvals e acoes.

### Subgrupo 6.3 - Validacao continua
- [x] Canonicalizar shape legado antes de validar.
- [x] Persistir sempre no shape canonico atual.

### Subgrupo 6.4 - Testes
- [x] Cobrir compatibilidade de leitura do shape legado do Alpha inicial.

## Grupo 7 - Testes de Integracao Completa

### Subgrupo 7.1 - Fluxo plan -> apply -> verify
- [x] Cobrir fluxo completo com command registry.

### Subgrupo 7.2 - Fluxo com rollback
- [x] Cobrir rollback por lote apos mutacoes reais.

### Subgrupo 7.3 - Fluxo com falha controlada
- [x] Cobrir bloqueio de `apply` apos `verify` falhar.

### Subgrupo 7.4 - Cenarios multi-acao
- [x] Cobrir lote compartilhado por multiplas acoes.

## Grupo 8 - Hardening do Core

### Subgrupo 8.1 - Reducao de acoplamento
- [x] Separar helpers de runtime de acao e verificacao fora da CLI.

### Subgrupo 8.2 - Responsabilidades
- [x] Concentrar transicoes canonicas em `StateStore`.
- [x] Manter a CLI como orquestracao fina do core.

### Subgrupo 8.3 - Atomicidade
- [x] Preservar escrita atomica do estado.
- [x] Preservar lock de runtime e monotonicidade de `revision`.

### Subgrupo 8.4 - Pontos unicos de falha
- [x] Eliminar dependencia do contrato antigo `verification.commands`.
- [x] Garantir compatibilidade de leitura para shape legado do Alpha inicial.

## Pos-Alpha

Itens nao bloqueantes para o gate Alpha atual:
- restaurar snapshots/checkpoints de runtime completos, alem de rollback por acao;
- enriquecer `memory.notes` com revalidacao automatica e expiracao ativa;
- introduzir dispatcher de fila e orchestration multi-lote acima da CLI atual.
