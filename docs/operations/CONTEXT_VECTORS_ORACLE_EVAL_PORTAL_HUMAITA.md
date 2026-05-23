# Context Vectors Oracle Eval — portal_humaita

- project_root: `D:\projetos_cli\Portal\Resolução Humaita Codex`
- indexed_files: 491
- skipped_files: 270
- state_status: invalid: state validation failed
- state_change: none
- oracle_cases: 6
- recall_at_1: 0.500
- recall_at_3: 1.000
- critical_continuity_result: pass
- scoring: deterministic sparse vector similarity plus bounded path/heading metadata cues
- authority: non-authoritative; advisory evidence only

## Verdict

The vector layer found the expected next-real-work document within top 3.

## Cases

### project-entry

- query: ponto de entrada vigente start here leitura obrigatoria memoria retomada dossie canon
- expected_path: `Entrada - Inicio do Projeto.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the explicit current entry point instead of older loose root files or historical reports.
- top_hits:
  - `Entrada - Inicio do Projeto.md`
    - score: 0.7161
    - source_status: unregistered
    - heading: # Start Here
  - `Memoria - Retomada 2026-04-06.md`
    - score: 0.6967
    - source_status: unregistered
    - heading: # Retomada 2026-04-06
  - `00_PAINEL_VIGENTE/Entrada - Contexto do Projeto.md`
    - score: 0.6942
    - source_status: unregistered
    - heading: # Contexto do Projeto
  - `01_TRABALHO_VIGENTE/04_RASCUNHOS_RETIFICACAO/2025-08_DOSSIE_CORRECAO.md`
    - score: 0.6545
    - source_status: unregistered
    - heading: # Dossie de Correcao 2025/08
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/REGRA_OBRIGATORIA_DE_EVIDENCIA_2026-04-11.md`
    - score: 0.6364
    - source_status: unregistered
    - heading: # Regra Obrigatoria de Evidencia 2026-04-11

### live-panel

- query: painel vigente status ponto de parada nao abrir pva nao transmitir proximo uso recomendado
- expected_path: `00_PAINEL_VIGENTE/Status - Painel Vigente.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the live panel/status surface that states the current PVA posture and pending work.
- top_hits:
  - `00_PAINEL_VIGENTE/Status - Painel Vigente.md`
    - score: 0.6882
    - source_status: unregistered
    - heading: # Painel Vigente
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/CHECKLIST_PRE_PVA.md`
    - score: 0.6602
    - source_status: unregistered
    - heading: # Checklist Pré-PVA — Trilha Segura Conservadora
  - `00_PAINEL_VIGENTE/Conceito - Criterios de Regularizacao.md`
    - score: 0.6253
    - source_status: unregistered
    - heading: # Conceito - Criterios de Regularizacao
  - `00_PAINEL_VIGENTE/Conceito - Matriz de Controle por Competencia.md`
    - score: 0.6232
    - source_status: unregistered
    - heading: # Conceito - Matriz de Controle por Competencia
  - `01_TRABALHO_VIGENTE/Status - Trabalho Vigente.md`
    - score: 0.6204
    - source_status: unregistered
    - heading: # Trabalho Vigente

### next-real-work

- query: checklist pre pva 28 arquivos trilha segura erros impeditivos validacao tecnica pendente
- expected_path: `01_TRABALHO_VIGENTE/03_RELATORIOS/CHECKLIST_PRE_PVA.md`
- rank: 2
- passed_at_1: false
- passed_at_3: true
- rationale: Must find the operational checklist for the next real work: manual PVA validation of the current safe track.
- top_hits:
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/CHECKLIST_VALIDACAO_PVA_2026-04-11.md`
    - score: 0.6971
    - source_status: unregistered
    - heading: # Checklist de Validacao PVA 2026-04-11
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/CHECKLIST_PRE_PVA.md`
    - score: 0.6759
    - source_status: unregistered
    - heading: # Checklist Pré-PVA — Trilha Segura Conservadora
  - `00_PAINEL_VIGENTE/Conceito - Validacao Pre-PVA.md`
    - score: 0.5935
    - source_status: unregistered
    - heading: # Conceito - Validacao Pre-PVA
  - `01_TRABALHO_VIGENTE/04_RASCUNHOS_RETIFICACAO/TRILHA_SEGURA_PRE_PVA_2026-04-02/2023-10_EFD_REAPURADA_COM_AM020003.txt`
    - score: 0.5245
    - source_status: unregistered
    - heading: |0000|017|1|01102023|31102023|PORTAL COMERCIO E DISTRIBUIDORA LTDA|14419272000305||AM|054521998|1301704|||A|1|
  - `01_TRABALHO_VIGENTE/04_RASCUNHOS_RETIFICACAO/TRILHA_SEGURA_PRE_PVA_SEM_121_2023-09_2026-04-02/2023-10_EFD_REAPURADA_COM_AM020003.txt`
    - score: 0.5244
    - source_status: unregistered
    - heading: |0000|017|1|01102023|31102023|PORTAL COMERCIO E DISTRIBUIDORA LTDA|14419272000305||AM|054521998|1301704|||A|1|

### human-validation-dossier

- query: readme dossie validacao humana ordem de leitura evidencia conclusoes contaminadas bloqueio real pva classificacao
- expected_path: `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/README.md`
- rank: 3
- passed_at_1: false
- passed_at_3: true
- rationale: Must find the current evidence dossier index, not a single historical or contaminated analysis note.
- top_hits:
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/REGISTRO_OPERACIONAL_COLETA_2026-04-11.md`
    - score: 0.6672
    - source_status: unregistered
    - heading: # Registro Operacional — Coleta de Evidencia Externa
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/REGRA_OBRIGATORIA_DE_EVIDENCIA_2026-04-11.md`
    - score: 0.6624
    - source_status: unregistered
    - heading: # Regra Obrigatoria de Evidencia 2026-04-11
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/README.md`
    - score: 0.6485
    - source_status: unregistered
    - heading: # Dossie de Validacao Humana 2026-04-11
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/RESET_CONCLUSOES_CONTAMINADAS_2026-04-11.md`
    - score: 0.6343
    - source_status: unregistered
    - heading: # Reset de Conclusoes Contaminadas 2026-04-11
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/ANALISE_DARS_PAGOS_X_APROVEITADOS_ATE_2025_12_2026-04-11.md`
    - score: 0.6322
    - source_status: unregistered
    - heading: # Analise DARs Pagos x Aproveitados ate `12/2025`

### canon-order

- query: canon operacional ordem trilha oficial vigente documento manda hoje ordem execucao verdade operacional
- expected_path: `01_TRABALHO_VIGENTE/03_RELATORIOS/CANON_OPERACIONAL_E_ORDEM_2026-04-06.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the current canon/order document that defines what commands the project today.
- top_hits:
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/CANON_OPERACIONAL_E_ORDEM_2026-04-06.md`
    - score: 0.7323
    - source_status: unregistered
    - heading: # Canon Operacional e Ordem 2026-04-06
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/BLOQUEIO_EXECUCAO_CORRETIVA_2026-04-11.md`
    - score: 0.5577
    - source_status: unregistered
    - heading: # Bloqueio de Execucao Corretiva 2026-04-11
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/REGISTRO_OPERACIONAL_COLETA_2026-04-11.md`
    - score: 0.5519
    - source_status: unregistered
    - heading: # Registro Operacional — Coleta de Evidencia Externa
  - `01_TRABALHO_VIGENTE/04_RASCUNHOS_RETIFICACAO/2024_DOSSIE_EXECUCAO.md`
    - score: 0.5361
    - source_status: unregistered
    - heading: # Dossie de Execucao 2024
  - `01_TRABALHO_VIGENTE/04_RASCUNHOS_RETIFICACAO/TRILHA_SEGURA_PRE_PVA_SEM_121_2023-09_2026-04-02/2024-07_EFD_REAPURADA_COM_AM020003.txt`
    - score: 0.5358
    - source_status: unregistered
    - heading: |0000|018|0|01072024|31072024|PORTAL COMERCIO E DISTRIBUIDORA LTDA|14419272000305||AM|054521998|1301704|||A|1|

### source-hierarchy

- query: hierarquia fontes fonte verdade atual trilha oficial canon checklist memoria retomada
- expected_path: `01_TRABALHO_VIGENTE/03_RELATORIOS/HIERARQUIA_DE_FONTES_DO_PROJETO.md`
- rank: 2
- passed_at_1: false
- passed_at_3: true
- rationale: Must find the Portal source-authority document rather than the embedded old Cerebro methodology folder.
- top_hits:
  - `Memoria - Retomada 2026-04-06.md`
    - score: 0.6989
    - source_status: unregistered
    - heading: # Retomada 2026-04-06
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/HIERARQUIA_DE_FONTES_DO_PROJETO.md`
    - score: 0.6566
    - source_status: unregistered
    - heading: # Hierarquia De Fontes Do Projeto
  - `00_PAINEL_VIGENTE/Conceito - Hierarquia de Fontes.md`
    - score: 0.6321
    - source_status: unregistered
    - heading: # Conceito - Hierarquia de Fontes
  - `05_GOVERNANCA/00_MANUAL_CONTINUIDADE/Memoria - Retomada Imediata 2026-03-24.md`
    - score: 0.5931
    - source_status: unregistered
    - heading: # Retomada Imediata - 2026-03-24
  - `01_TRABALHO_VIGENTE/03_RELATORIOS/CANON_OPERACIONAL_E_ORDEM_2026-04-06.md`
    - score: 0.5808
    - source_status: unregistered
    - heading: # Canon Operacional e Ordem 2026-04-06
