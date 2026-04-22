# MANUAL — Current surface drift tripwire (slice 2)

## Status

- `implemented on 2026-04-21`
- `measured on curated dataset`
- `externally validated as narrow-Cerebro-specific`
- `not promoted`

This document now records the implemented contract for the
`detect_current_surface_drift` slice under
`experiments/operational_signals/suggestions/`.
It still does not authorize widening the suggestion layer by itself.

## Intent

Detectar quando múltiplos docs canônicos declaram estados correntes divergentes ("camada vigente" inconsistente entre `README.md`, `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, `PHASE_CLOSURE.md`).

Complementa `detect_stale_system_state` (intra-file) → esta é inter-file.

## Defaults decididos

| ponto | default |
|---|---|
| escopo canônico | 4 arquivos: `README.md`, `docs/operations/SYSTEM_STATE.md`, `docs/operations/OPPORTUNITY_MAP.md`, `docs/operations/PHASE_CLOSURE.md` |
| fato extraído (v1) | **test count** (`Last suite result: N tests`) |
| interface | case-based (múltiplos inputs), igual padrão 2b |
| failure_mode | `CONTEXT_AMBIGUOUS` (já no enum) |
| threshold | reusar `MIN_ABSOLUTE_DRIFT=5`, `MEDIUM=10`, `HIGH=50` de 2a |
| scope guard | silenciar se <2 docs presentes ou <2 counts extraíveis |

## Arquivos

- `experiments/operational_signals/suggestions/rules.py` — regra + extratores
- `experiments/operational_signals/suggestions/dataset_surface_drift.toml`
- `experiments/operational_signals/suggestions/evaluate.py` — registry
- `experiments/operational_signals/suggestions/tests/test_rules.py`
- `experiments/operational_signals/suggestions/tests/test_harness.py` (se necessário)
- `docs/operations/OPERATIONAL_INSUFFICIENCY_SIGNALS.md` — round 2d
- `docs/operations/SYSTEM_STATE.md` + `docs/operations/OPPORTUNITY_MAP.md`

## Regra (assinatura)

```python
def detect_current_surface_drift(
    *, case: dict[str, Any], now: datetime | None = None,
) -> Suggestion | None:
```

Case schema:

```toml
[[case]]
id = "cerebro-2026-04-21"
label = "positive"
label_reason = "README declara 550, SYSTEM_STATE declara 730"
expected_confidence = "high"
readme_text          = "..."
system_state_text    = "..."
opportunity_map_text = ""
phase_closure_text   = ""
```

Todos os `*_text` são opcionais. String vazia = ausente.

## Algoritmo

1. Coletar textos não-vazios em `sources = {name: text for name, text in case if text.strip()}`.
2. Scope guard: `len(sources) >= 2` — senão `return None`.
3. Para cada texto, extrair **primeiro** match de `SUITE_RESULT_RE` (reusar regex existente em `rules.py`).
4. Filtrar fontes sem count: `counts = {name: n for name, n in extracted if n is not None}`.
5. Guard: `len(counts) >= 2` — senão `return None`.
6. `max_drift = max(counts.values()) - min(counts.values())`.
7. Silenciar se `max_drift < MIN_ABSOLUTE_DRIFT`.
8. Confidence: reusar `classify_confidence(max_drift)`.
9. `supporting_signals`: tupla `(f"{name}_suite_count={n}", ...)` + `f"max_pairwise_drift={max_drift}"`.
10. `reason_flags = ("cross_doc_surface_drift_detected", "suite_count_mismatch_across_docs")`.

## Reuso obrigatório

- `SUITE_RESULT_RE` (já em `rules.py`)
- `classify_confidence`
- `_id_fragment`
- Dataclass `Suggestion` (frozen)

## Normalização

Não aplicável v1 (extração regex pura).

## Dataset

Mínimo 10 casos:
- 4 positivos: drift entre 2, 3, 4 fontes
- 4 negativos: counts concordantes
- 2 guard: só 1 fonte presente → silêncio

Schema TOML espelha 2b com 4 campos `*_text` no lugar de `text`/`exports_text`.

## Harness

`_apply_rule` já suporta case-based via `inspect.signature`. Zero mudança.

`_normalize_case` precisa aceitar os 4 campos `*_text` como strings opcionais:

```python
for field in ("readme_text", "system_state_text", "opportunity_map_text", "phase_closure_text"):
    value = raw.get(field)
    if value is not None and not isinstance(value, str):
        raise DatasetError(f"{case_id}: {field} must be a string")
    case_dict[field] = value if isinstance(value, str) else ""
```

`evaluate.py`: registrar `detect_current_surface_drift` com dataset `dataset_surface_drift.toml`, outputs `report_surface_drift_latest.{md,json}`.

## Thresholds

- `ACCEPT_PRECISION = 0.70`
- `ACCEPT_RECALL = 0.60`
- `ITERATE_PRECISION = 0.60`

## Testes obrigatórios

- drift real entre 2 docs → emite, confidence correta
- drift entre 3+ docs → emite, `max_pairwise_drift` correto
- counts concordantes → silêncio
- <2 fontes presentes → silêncio
- <2 counts extraíveis → silêncio
- drift abaixo de `MIN_ABSOLUTE_DRIFT` → silêncio
- `supporting_signals` contém uma linha por fonte
- `source_artifact` derivado de `case["id"]`
- contract guards: sem import de `core`/`cli`, sem write em `.cerebro/`

## Validação externa

1. Rodar contra docs reais do Cérebro em commits diferentes (via `git show`).
2. Rodar contra 4 corpora conhecidos se mantiverem padrão similar.
3. Se nenhum externo tiver o padrão cross-doc, classificar como **narrow-Cerebro-specific** e documentar — não é falha, é escopo declarado.

## Reframe externo (lição 2b)

Regra é estruturalmente dependente de docs estilo Cérebro. Mede ruído + silêncio correto fora do padrão. Não mede cobertura universal. `marginal` externo é compatível com aceitação interna **se** documentado como narrow.

## Gates finais

```
python -m unittest discover -s tests -v
python -m unittest tests.test_architecture -v
```

Verdict harness esperado: `accept_for_staged_promotion` no dataset curado.

## Invariantes

- `authority = "derived-advisory-only"`
- `human_review_required = True`
- Nunca ler `.cerebro/`
- Nunca importar `core/`/`cli/`
- `FIXED_EVAL_TIMESTAMP` obrigatório

## Report behavior

Diferenciar:
- `insufficient_sources` (silêncio por scope guard)
- `sources_agree` (silêncio = TN)
- `drift_detected` (emissão)

## Expansão futura (não implementar agora)

Após v1 validar:
- comparar posture keyword (`freeze` vs `active`)
- comparar current queue mode
- comparar current next item

Cada expansão = dataset novo + validação externa nova. Não empilhar.

## Critério de parada

1. Gates verdes
2. Validação externa executada
3. Verdict em doc canônico
4. Aceitação do operador

Se externo falhar → `narrow-scope-validated`, mantém, não expande.

## Resultado implementado

Arquivos implementados:

- `experiments/operational_signals/suggestions/rules.py`
- `experiments/operational_signals/suggestions/dataset_surface_drift.toml`
- `experiments/operational_signals/suggestions/evaluate.py`
- `experiments/operational_signals/suggestions/tests/test_rules.py`
- `experiments/operational_signals/suggestions/tests/test_harness.py`

Resultado medido em 2026-04-21:

- verdict do dataset curado: `accept_for_staged_promotion`
- tamanho do dataset: `10`
- casos avaliados: `10`
- precision / recall / F1: `1.0 / 1.0 / 1.0`

Validação externa em 2026-04-21:

- classificação: `narrow-Cerebro-specific`
- estados reais do Cerebro checados: working tree + commits `47802bf`, `65b16e5`, `2e9e95f`, `942756f`
- padrão observado: os `5` casos ficaram silenciosos porque só `1/4` docs expunha `Last suite result` extraível
- corpora externos (`estoque_pioneira`, `rpg_caminhada`, `IRPF e Caixa Rural`, `Resolução Humaita Codex`): `0` emissões
