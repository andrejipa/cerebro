# Codex Prompt — Cerebro Heartbeat Loop

## Objective

Conduzir o trabalho local-first do Cerebro até o máximo estado concluído
permitido pelo estado vivo do repositório, em rodadas recorrentes de
aproximadamente `20` minutos, sempre com no máximo `1` slice por rodada,
validação real, reconciliação documental e parada limpa.

## Strategic Direction

Filtrar sempre pelo estado vivo do repositório.

A direção atual autorizada é:

1. continuar a campanha de decomposição de `core/validation.py` no boundary já aberto
2. executar `1` slice por rodada
3. prosseguir automaticamente pelos slices autorizados até o slice `11`, desde que os gates permaneçam verdes e não haja bloqueio real
4. parar obrigatoriamente no checkpoint manual antes do slice `12`
5. manter a infraestrutura `100% local-first`
6. usar `docs/operations/observation_center.toml` como fila canônica legível por máquina
7. tratar `SYSTEM_STATE.md` e `OPPORTUNITY_MAP.md` como projeções humanas do centro
8. preservar `single_flight`, `overlap_policy = wait` e idempotência por rodada
9. não implementar a promoção para SQLite sem novo trigger formal ativo autorizando isso
10. não tocar nada remoto/distribuído:
   - Cloudflare
   - Temporal
   - coordenação remota
   - filas ou locks fora do workspace

## Source Of Truth

Leia sempre antes de agir:

- `AGENTS.md`
- triggers formais ativos em `docs/operations/`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- planos vivos relevantes, incluindo `VALIDATION_DECOMPOSITION_PLAN.md`
- `git status`
- evidência local relevante

## Authority Order

Use esta ordem de autoridade:

1. `AGENTS.md`
2. triggers formais ativos
3. `docs/operations/observation_center.toml`
4. `docs/operations/SYSTEM_STATE.md`
5. `docs/operations/OPPORTUNITY_MAP.md`
6. planos específicos vivos
7. código e testes

Um trigger formal ativo pode estreitar ou reabrir um boundary específico dentro
do freeze. Se `AGENTS.md`, o trigger ativo, `observation_center.toml`,
`SYSTEM_STATE.md` e `OPPORTUNITY_MAP.md` divergirem, a rodada vira
reconciliação-first e nenhum slice de implementação começa antes desse
fechamento.

## Round Model

- você está em heartbeat loop recorrente
- cada rodada tem orçamento de aproximadamente `20` minutos
- execute no máximo `1` slice por rodada
- não espere revisão humana entre slices enquanto:
  - o boundary atual continuar autorizando
  - o plano vivo continuar apontando continuidade automática
  - os gates permanecerem verdes
  - o checkpoint manual ainda não tiver sido alcançado
- checkpoint manual obrigatório:
  - parar antes do slice `12`
  - não iniciar slice `12` automaticamente

## Required Initial Reconciliation

No começo de cada rodada, determine explicitamente:

- boundary atual para `docs/`, `tests/`, `core/`, `cli/`
- trigger ativo e status
- item ativo real
- slice atual
- se existe checkpoint manual pendente
- se há restos de `1`, `2` ou `3` passos atrás que precisam ser resolvidos
  antes do próximo slice

Se houver inconsistência viva entre trigger, `observation_center.toml`,
`SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md` e o estado real do workspace, esta
rodada é de reconciliação docs-only e para depois do fechamento limpo.

## Selection Heuristic

Escolha o próximo trabalho nesta ordem:

1. inconsistência viva entre trigger, `observation_center.toml`,
   `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md` e estado real
2. observação `open` de maior prioridade com boundary autorizado
3. slice ativa explicitamente aberta da campanha de validation decomposition
4. resto parcial da rodada anterior
5. proof-of-stop ou reconciliação mínima, se não houver slice autorizada

Para a campanha atual:

- continuar mecanicamente para o próximo slice autorizado
- preferir sempre o próximo slice do plano vivo
- não reabrir discussão estratégica a cada rodada
- não pular slices
- não agrupar múltiplos slices na mesma rodada

## Slice Policy

Uma rodada válida deve:

- executar exatamente `1` slice pequena
- tocar apenas os arquivos necessários
- preservar invariantes do plano da campanha
- validar com testes focais + gates definidos
- atualizar docs/estado ao final
- parar limpa

## Allowed Autonomy

Você tem permissão para seguir sozinho até o fim do escopo atualmente
autorizado, sem pedir revisão humana a cada rodada, desde que:

- permaneça dentro do boundary atual
- siga o plano vivo da campanha
- não abra novo escopo
- não mude a arquitetura para algo não local
- não chegue ao checkpoint manual antes do slice `12`

## Local-First Policy

Não implementar nem preparar runtime remoto/distribuído.

Não introduzir dependências em:

- Cloudflare
- Temporal
- coordenação distribuída
- filas externas
- locks externos
- qualquer serviço fora do workspace local

## SQLite Policy

A promoção de `observation_center.toml` para ledger SQLite local é:

- desejável no futuro
- compatível com local-first
- mas bloqueada agora

Só pode entrar em execução se um trigger formal ativo autorizar explicitamente:

- schema inicial
- `observations`
- `observation_dependencies`
- `round_runs`
- `round_events`
- `leases`
- `projections`

Até esse trigger existir:

- não implementar
- não preparar código
- não abrir boundary por conta própria
- apenas manter isso como follow-on bloqueado se aparecer no estado vivo

## Validation

Após cada slice:

- rodar os testes focais da slice
- rodar o gate AGENTS-equivalente quando a rodada tocar runtime ou docs
  operacionais relevantes
- rodar `python -m unittest tests.test_architecture -v` sempre que a rodada
  tocar `AGENTS.md`, `docs/operations/`, trigger, plano vivo, boundary, ou
  quando o trigger/plano ativo exigir isso

Para a campanha ativa de validation decomposition, a validação obrigatória é:

- `python -m unittest tests.test_validate_error_ordering -v`
- `python -m unittest tests.test_validate -v`
- `python -m unittest tests.test_architecture -v`
- gate AGENTS-equivalente

Registrar sempre:

- total de testes
- falhas
- `errors`
- `skips`

## Docs And Projections

Ao final de cada rodada, se houve progresso real:

- atualizar `docs/operations/observation_center.toml`
- atualizar `docs/operations/SYSTEM_STATE.md`
- atualizar `docs/operations/OPPORTUNITY_MAP.md`
- atualizar trigger/plano vivo se aplicável
- manter coerência entre centro canônico e projeções humanas

## Mandatory Stop Conditions

Parar imediatamente se:

- o próximo slice exigir boundary não autorizado
- houver divergência real de contrato
- surgir necessidade de SQLite sem trigger formal ativo
- surgir necessidade de qualquer tecnologia não local
- o plano vivo mandar checkpoint manual
- chegar ao ponto imediatamente anterior ao slice `12`
- houver risco de escopo escorregar
- o orçamento da rodada estiver acabando sem fechamento seguro

## Required Output Format

HEARTBEAT ROUND:
- mode:
- active_item:
- active_slice:
- boundary:
- trigger_status:
- checkpoint_status:

PLAN:
- selected_slice:
- files_to_touch:
- invariants:
- validation_plan:

EXECUTION:
- changes_made:
- blockers:

VALIDATION:
- focused_tests:
- full_gate:
- architecture_gate:

DOCS:
- files_updated:
- observation_center_reconciled:
- projections_reconciled:

STOP:
- outcome:
- boundary_final:
- next_correct_step:
- next_slice_if_any:
- needs_human_review:
- reason_for_stop:

## Final Rule

Continue sozinho de forma inteligente enquanto houver slice autorizada e
segura. Não peça revisão humana desnecessariamente. Mas não ultrapasse
checkpoint manual, boundary ativo ou contrato local-first.
