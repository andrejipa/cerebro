# Experimental Recall Evaluation — Round 2

- experimental: `true`
- authority: `derived-assistive`
- non-authoritative: `true`
- read-only: `true`

## Aggregate Metrics By Variant

### Variant A

- Recall@3: `0.3021`
- Precision@3: `0.1875`
- Hit@3: `0.4375`
- MRR: `0.3385`
- Historical error: `0.0000`
- Lateral doc error: `0.0000`
- Code/doc confusion: `0.0000`

### Variant B

- Recall@3: `0.3021`
- Precision@3: `0.1875`
- Hit@3: `0.4375`
- MRR: `0.3385`
- Historical error: `0.0000`
- Lateral doc error: `0.0000`
- Code/doc confusion: `0.0000`

### Variant C

- Recall@3: `0.0833`
- Precision@3: `0.0625`
- Hit@3: `0.1875`
- MRR: `0.1250`
- Historical error: `0.0000`
- Lateral doc error: `0.0625`
- Code/doc confusion: `0.0000`

### Variant D

- Recall@3: `0.1146`
- Precision@3: `0.0417`
- Hit@3: `0.1250`
- MRR: `0.0573`
- Historical error: `0.0000`
- Lateral doc error: `0.0625`
- Code/doc confusion: `0.0000`

## By Project

### Variant A

- IRPF e Caixa Rural: Recall@3 `0.2500`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.1458`
- estoque_pioneira: Recall@3 `0.3333`, Precision@3 `0.2500`, Hit@3 `0.5000`, MRR `0.3333`
- rpg_caminhada: Recall@3 `0.5000`, Precision@3 `0.3333`, Hit@3 `0.7500`, MRR `0.6250`
- Resolução Humaita Codex: Recall@3 `0.1250`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.2500`

### Variant B

- IRPF e Caixa Rural: Recall@3 `0.2500`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.1458`
- estoque_pioneira: Recall@3 `0.3333`, Precision@3 `0.2500`, Hit@3 `0.5000`, MRR `0.3333`
- rpg_caminhada: Recall@3 `0.5000`, Precision@3 `0.3333`, Hit@3 `0.7500`, MRR `0.6250`
- Resolução Humaita Codex: Recall@3 `0.1250`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.2500`

### Variant C

- IRPF e Caixa Rural: Recall@3 `0.1250`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.1250`
- estoque_pioneira: Recall@3 `0.0833`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.2500`
- rpg_caminhada: Recall@3 `0.1250`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.1250`
- Resolução Humaita Codex: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`

### Variant D

- IRPF e Caixa Rural: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- estoque_pioneira: Recall@3 `0.0833`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.0833`
- rpg_caminhada: Recall@3 `0.2500`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.0833`
- Resolução Humaita Codex: Recall@3 `0.1250`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0625`

## By Scope

### Variant A

- code: Recall@3 `0.5000`, Precision@3 `0.3333`, Hit@3 `0.5000`, MRR `0.2500`
- documentation: Recall@3 `0.2949`, Precision@3 `0.1795`, Hit@3 `0.4615`, MRR `0.3782`
- historical: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`

### Variant B

- code: Recall@3 `0.5000`, Precision@3 `0.3333`, Hit@3 `0.5000`, MRR `0.2500`
- documentation: Recall@3 `0.2949`, Precision@3 `0.1795`, Hit@3 `0.4615`, MRR `0.3782`
- historical: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`

### Variant C

- code: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- documentation: Recall@3 `0.1026`, Precision@3 `0.0769`, Hit@3 `0.2308`, MRR `0.1538`
- historical: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`

### Variant D

- code: Recall@3 `0.5000`, Precision@3 `0.1667`, Hit@3 `0.5000`, MRR `0.1667`
- documentation: Recall@3 `0.0641`, Precision@3 `0.0256`, Hit@3 `0.0769`, MRR `0.0449`
- historical: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`

## By Query Type

### Variant A

- canonical_state: Recall@3 `0.4333`, Precision@3 `0.2667`, Hit@3 `0.8000`, MRR `0.5333`
- code_logic: Recall@3 `0.5000`, Precision@3 `0.3333`, Hit@3 `0.5000`, MRR `0.2500`
- continuity: Recall@3 `0.2917`, Precision@3 `0.2500`, Hit@3 `0.5000`, MRR `0.5000`
- historical_lookup: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- routing: Recall@3 `0.1250`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0625`

### Variant B

- canonical_state: Recall@3 `0.4333`, Precision@3 `0.2667`, Hit@3 `0.8000`, MRR `0.5333`
- code_logic: Recall@3 `0.5000`, Precision@3 `0.3333`, Hit@3 `0.5000`, MRR `0.2500`
- continuity: Recall@3 `0.2917`, Precision@3 `0.2500`, Hit@3 `0.5000`, MRR `0.5000`
- historical_lookup: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- routing: Recall@3 `0.1250`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0625`

### Variant C

- canonical_state: Recall@3 `0.1667`, Precision@3 `0.1333`, Hit@3 `0.4000`, MRR `0.3000`
- code_logic: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- continuity: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- historical_lookup: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- routing: Recall@3 `0.1250`, Precision@3 `0.0833`, Hit@3 `0.2500`, MRR `0.1250`

### Variant D

- canonical_state: Recall@3 `0.1667`, Precision@3 `0.0667`, Hit@3 `0.2000`, MRR `0.1167`
- code_logic: Recall@3 `0.5000`, Precision@3 `0.1667`, Hit@3 `0.5000`, MRR `0.1667`
- continuity: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- historical_lookup: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`
- routing: Recall@3 `0.0000`, Precision@3 `0.0000`, Hit@3 `0.0000`, MRR `0.0000`

## Failure Analysis

- embeddings_helped: `C:irpf-002`
- embeddings_hurt: `C:irpf-001, C:est-002, C:rpg-001, C:rpg-003, C:hum-001, D:irpf-001, D:est-002, D:rpg-001, D:rpg-004, D:hum-001`
- lexical_better: `C:irpf-001, C:est-002, C:rpg-001, C:rpg-003, C:hum-001, D:irpf-001, D:est-002, D:rpg-001, D:rpg-004, D:hum-001`
- doc_beats_code: `none`
- historical_pull: `none`
