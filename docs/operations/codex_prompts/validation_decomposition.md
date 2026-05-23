# Codex Prompt — _validate_agent_runtime_block Structural Decomposition

## Context

- Repo: Cerebro (runtime determinístico, governado por AGENTS.md)
- Target: `_validate_agent_runtime_block` em core/validation.py:192 — 865 linhas numa função só
- Classificação: manutenção estrutural (reduzir densidade cognitiva)
- NÃO é: melhoria, cleanup, consolidação, modernização
- Postura atual: freeze deliberado sobre crescimento canonical especulativo
- Qualquer edit em core/ exige formal resume trigger aprovado pelo operador

## Authority pins (ler antes de agir)

- AGENTS.md
- docs/operations/SYSTEM_STATE.md
- docs/operations/OPPORTUNITY_MAP.md
- docs/reference/ARCHITECTURE_BOUNDARIES.md
- docs/operations/STATESTORE_DECOMPOSITION_PLAN.md (precedente de formato)

## Objective (estreito)

Reduzir linhas e densidade cognitiva de `_validate_agent_runtime_block` via extração de helpers per-block no mesmo arquivo, preservando comportamento observável exato.

## Non-objectives explícitos

- NÃO refatorar para clareza de nomes
- NÃO consolidar mensagens de erro duplicadas
- NÃO melhorar tipos de erro
- NÃO criar novo módulo
- NÃO introduzir @dataclass, NamedTuple, TypedDict, Protocol, ABC, context object
- NÃO mudar assinatura pública de `_validate_agent_runtime_block`
- NÃO tocar qualquer outra função ou módulo
- NÃO aplicar mudanças "já que estou aqui"

## Execution model — duas fases com gate estrito entre elas

### Phase A — Plan (docs-only, boundary atual, sem trigger)

Sem mudança de código. Deliverables:

1. `docs/operations/VALIDATION_DECOMPOSITION_PLAN.md`
   Seções obrigatórias:
   - Scope statement (framing explícito: manutenção, não melhoria)
   - Fan-out classification table: por sub-bloco identificável:
     * nome
     * line range
     * locals lidos
     * locals escritos
     * estado externo acessado
     * error codes emitidos
     * dependências implícitas com blocos anteriores
   - Proposed slice order: ordenado por fan-out ascendente e isolamento descendente; primeiro slice deve ter zero dependência em laters
   - Characterization tests requeridos antes da slice 1:
     * aggregate error-order pin (variações malformadas, captura da lista emitida exata)
     * golden-file por variação
     * localização: tests/test_validate_error_ordering.py (arquivo novo)
   - Per-slice protocol (ver guardrails)
   - Stop conditions

2. `docs/operations/FORMAL_RESUME_TRIGGER_VALIDATION_DECOMPOSITION.md` (draft, não aprovado)
   - superfície autorizada: core/validation.py + tests/test_validate_error_ordering.py
   - stop conditions
   - failure handling

### Phase A stop condition

Após plan + trigger draft escritos: PARAR.
Não abrir o trigger. Não tocar core/. Não criar arquivo de teste.

Reportar ao operador:
- arquivos produzidos
- número de sub-blocos identificados
- candidato a primeiro slice
- gate status

Aguardar autorização explícita (trigger aprovado) antes de Phase B.

### Phase B — Execução (trigger-gated, um slice por commit)

Só após operador aprovar o trigger.

#### Commit preparatório (antes de qualquer extração)
- commit 1: adicionar characterization tests em tests/test_validate_error_ordering.py
- capturar ordering e texto de erro atual para pelo menos um payload malformado por bloco
- gate: AGENTS-equivalente + python -m unittest tests.test_architecture -v
- título: `tests(validate): pin aggregate error ordering for _validate_agent_runtime_block`
- PARAR e aguardar revisão do operador antes do commit 2

#### Slice commits (um por sub-bloco)
Para cada slice:
1. extrair bloco para função privada `_validate_<block>_block` no mesmo arquivo
2. preservar nomes de locals verbatim
3. preservar append-order da lista de errors
4. preservar early-return (se houver)
5. NÃO mudar nenhum texto de erro
6. NÃO mudar nenhum error code
7. NÃO consolidar validações duplicadas
8. helper recebe só o necessário (args primitivos ou sub-dict)
9. gate: AGENTS-equivalente + tests.test_architecture + tests.test_validate + tests.test_validate_error_ordering
10. título: `refactor(validate): extract _validate_<block>_block (slice N/M)`
11. PARAR e aguardar operador antes do próximo slice

## Guardrails (proibido)

- criar qualquer novo arquivo em core/
- criar qualquer novo arquivo de teste exceto test_validate_error_ordering.py
- introduzir @dataclass, NamedTuple, TypedDict, Protocol, ABC
- introduzir context/accumulator object
- renomear qualquer local existente
- mudar qualquer texto de erro existente
- mudar qualquer error code existente
- reordenar validações existentes
- consolidar validações "quase duplicadas"
- marcar slice completo sem gate AGENTS-equivalente verde
- pular characterization tests
- batching de múltiplos slices em um commit
- tocar qualquer função além de `_validate_agent_runtime_block` e helpers dele
- tocar qualquer arquivo fora da whitelist:
  * core/validation.py
  * tests/test_validate_error_ordering.py
  * docs/operations/VALIDATION_DECOMPOSITION_PLAN.md
  * docs/operations/FORMAL_RESUME_TRIGGER_VALIDATION_DECOMPOSITION.md
  * docs/operations/SYSTEM_STATE.md
  * docs/operations/OPPORTUNITY_MAP.md

## Stop conditions (halt obrigatório)

Parar imediatamente e documentar quando qualquer uma destas for true:
- characterization test revela comportamento pré-existente difícil de fixar
- slice requer rearranjar fluxo além de extração simples
- slice requer passar mais de ~6 args primitivos (sinal: bloco não é separável limpamente)
- qualquer gate fica vermelho
- slice requer tocar arquivo fora da whitelist
- slice requer renomear ou restruturar testes
- análise de fan-out revela shared mutable state implícito entre blocos

Ao halt:
- NÃO forçar o slice
- registrar blocker no VALIDATION_DECOMPOSITION_PLAN.md com file:line
- aguardar decisão do operador

## Output format (por iteração)

PHASE: A | B
ITERATION: <n>
MODE: PLAN | CHARACTERIZATION_TESTS | SLICE | HALT

ACTIONS:
- file: <path>
- change: <add|modify|delete>
- summary: <one-line>

VERIFICATION:
- agents_gate: <tests_total>/<failures>/<skips>
- architecture_gate: <tests_total>/<failures>
- targeted_suites: <suite: result>

STATE:
- slices_completed: <n>/<total>
- slices_remaining: <list>
- worktree: clean | dirty

NEXT:
- await_operator: yes | no
- if yes: <que decisão é necessária>
- if no: <próxima ação>

## Done criteria

Phase A done quando:
- plan file escrito
- trigger draft escrito
- nenhum arquivo referencia trabalho futuro especulativo
- fan-out classification completa
- operador tem informação para decidir

Phase B done quando:
- todos slices autorizados commitados
- characterization tests ainda verdes
- AGENTS-equivalente verde
- architecture gate verde
- body de `_validate_agent_runtime_block` é sequência de chamadas a helpers OU
- alguns slices halted e documentados (completude parcial registrada)

## Final output

SUMMARY:
- phases_completed: A | A+B
- plan_file: <path>
- trigger_file: <path>
- trigger_status: drafted | approved | consumed | halted
- characterization_tests_added: <count>
- slices_committed: <n>/<total>
- slices_halted: <list com razão>
- files_changed:
  - <path>: <+lines/-lines>
- tests_delta: <before> -> <after>
- final_gate: <tests_total>/<failures>/<skips>
- architecture_gate: <tests_total>/<failures>
- requires_trigger_for_continuation: yes | no
- next_recommended_step: <one-line>
