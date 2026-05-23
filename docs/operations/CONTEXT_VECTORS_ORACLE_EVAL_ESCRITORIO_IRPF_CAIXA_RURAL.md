# Context Vectors Oracle Eval — escritorio_irpf_caixa_rural

- project_root: `D:\projetos_cli\escritorio\IRPF e Caixa Rural`
- indexed_files: 202
- skipped_files: 3136
- state_status: absent
- state_change: none
- oracle_cases: 6
- recall_at_1: 1.000
- recall_at_3: 1.000
- all_cases_passed_at_3: true
- scoring: deterministic sparse vector similarity plus bounded path/heading metadata cues
- authority: non-authoritative; advisory evidence only

## Verdict

All oracle cases found their expected paths within top 3.

## Cases

### structure-general

- query: estrutura geral escritorio regra separacao sistemas contribuintes dados clientes irpf atividade rural
- expected_path: `README_ESTRUTURA_GERAL.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the root office structure document that separates systems from contributor/client data.
- top_hits:
  - `README_ESTRUTURA_GERAL.md`
    - score: 0.8519
    - source_status: unregistered
    - heading: # Estrutura Geral do Escritorio
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/JEAN_PAUL_MARTINS_CORREIA/99_REFERENCIAS_E_MAPAS/00_MAPA_DO_CLIENTE.md`
    - score: 0.7241
    - source_status: unregistered
    - heading: # Cliente Mestre
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/IRACY_APARECIDA_ARAUJO/99_REFERENCIAS_E_MAPAS/00_MAPA_DO_CLIENTE.md`
    - score: 0.7182
    - source_status: unregistered
    - heading: # Cliente Mestre
  - `CONTRIBUINTES/00_RELATORIO_MIGRACAO_E_ANALISE_GERAL.md`
    - score: 0.7128
    - source_status: unregistered
    - heading: # Relatorio de Migracao e Analise Geral
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/ALTINO_MICKUS/99_REFERENCIAS_E_MAPAS/00_MAPA_DO_CLIENTE.md`
    - score: 0.6987
    - source_status: unregistered
    - heading: # Cliente Mestre

### official-document-structure

- query: orientacao oficial estrutura documental xml danfe pdf documento fonte camada operacional deduplicacao
- expected_path: `ORIENTACAO_OFICIAL_ESTRUTURA_DOCUMENTAL.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the official documentary-structure guidance for XML, DANFE/PDF, source documents, and deduplication.
- top_hits:
  - `ORIENTACAO_OFICIAL_ESTRUTURA_DOCUMENTAL.md`
    - score: 0.7313
    - source_status: unregistered
    - heading: # Orientacao Oficial Para Estrutura Documental
  - `IRPF/_SISTEMA/01_METODOLOGIA/CAMADA_DE_EXTRACAO_E_INFERENCIA_DOCUMENTAL.md`
    - score: 0.6608
    - source_status: unregistered
    - heading: # Camada de Extracao e Inferencia Documental
  - `IRPF/_SISTEMA/04_KIT_PORTATIL_PARA_NOVO_CLIENTE/04_REFERENCIAS_DO_SISTEMA/CAMADA_DE_EXTRACAO_E_INFERENCIA_DOCUMENTAL.md`
    - score: 0.6582
    - source_status: unregistered
    - heading: # Camada de Extracao e Inferencia Documental
  - `IRPF/_SISTEMA/01_METODOLOGIA/PIPELINE_OPERACIONAL_OFICIAL_DO_CASO.md`
    - score: 0.5959
    - source_status: unregistered
    - heading: ## Etapa 1. Inicializacao
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/JEAN_PAUL_MARTINS_CORREIA/03_IRPF/03_ENTREGA/01_RESUMO_EXECUTIVO/02_RESUMO_FISCAL_ECONOMICO_DANFE_PDF.md`
    - score: 0.5940
    - source_status: unregistered
    - heading: # Resumo Fiscal e Documental - JEAN PAUL MARTINS CORREIA

### master-organization

- query: organizacao mestra executada arvore final irpf atividade rural contribuintes regra operacional
- expected_path: `ORGANIZACAO_MESTRA_EXECUTADA.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the root record of the executed master organization.
- top_hits:
  - `ORGANIZACAO_MESTRA_EXECUTADA.md`
    - score: 0.6996
    - source_status: unregistered
    - heading: # Organizacao Mestra Executada
  - `CONTRIBUINTES/00_GESTAO_MESTRA/README_GESTAO_MESTRA.md`
    - score: 0.6716
    - source_status: unregistered
    - heading: # Gestao Mestra de Contribuintes
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/IRACY_APARECIDA_ARAUJO/03_IRPF/02_PROCESSAMENTO/02_RELATORIOS_TECNICOS/README_ORGANIZACAO.md`
    - score: 0.6349
    - source_status: unregistered
    - heading: ## Estrutura criada
  - `CONTRIBUINTES/01_IRPF/CLIENTES/IRACY_APARECIDA_ARAUJO__CPF_11399970259/02_PROCESSAMENTO/02_RELATORIOS_TECNICOS/README_ORGANIZACAO.md`
    - score: 0.6329
    - source_status: unregistered
    - heading: ## Estrutura criada
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/IRACY_APARECIDA_ARAUJO/03_IRPF/02_PROCESSAMENTO/02_RELATORIOS_TECNICOS/README_PLANILHA_BASE_CAIXA_RURAL.md`
    - score: 0.6315
    - source_status: unregistered
    - heading: ## Como usar

### contributor-management

- query: gestao mestra contribuintes indice mestre clientes mapa dominios matriz clientes memoria navegacao
- expected_path: `CONTRIBUINTES/00_GESTAO_MESTRA/README_GESTAO_MESTRA.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the management surface for contributors rather than a specific client's report.
- top_hits:
  - `CONTRIBUINTES/00_GESTAO_MESTRA/README_GESTAO_MESTRA.md`
    - score: 0.7723
    - source_status: unregistered
    - heading: # Gestao Mestra de Contribuintes
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/README_CADASTRO_MESTRE.md`
    - score: 0.6968
    - source_status: unregistered
    - heading: # Cadastro Mestre de Clientes
  - `CONTRIBUINTES/00_GESTAO_MESTRA/02_MAPA_DE_DOMINIOS.md`
    - score: 0.6847
    - source_status: unregistered
    - heading: # Mapa de Dominios
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/IRACY_APARECIDA_ARAUJO/03_IRPF/02_PROCESSAMENTO/02_RELATORIOS_TECNICOS/README_PLANILHA_BASE_CAIXA_RURAL.md`
    - score: 0.5879
    - source_status: unregistered
    - heading: ## Como usar
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/IRACY_APARECIDA_ARAUJO/03_IRPF/02_PROCESSAMENTO/02_RELATORIOS_TECNICOS/README_ORGANIZACAO.md`
    - score: 0.5852
    - source_status: unregistered
    - heading: ## Estrutura criada

### irpf-system

- query: sistema irpf metodologia pipeline operacional oficial contrato ingestao modelos entregaveis novo cliente
- expected_path: `IRPF/README_SISTEMA.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the IRPF system entry despite many contributor XML/PDF files appearing earlier in traversal.
- top_hits:
  - `IRPF/README_SISTEMA.md`
    - score: 0.7629
    - source_status: unregistered
    - heading: ## Objetivo
  - `IRPF/_SISTEMA/02_MODELOS/MODELO_MEMORIA_TECNICA_CLIENTE.md`
    - score: 0.6501
    - source_status: unregistered
    - heading: ## Informacoes fixas
  - `IRPF/_SISTEMA/04_KIT_PORTATIL_PARA_NOVO_CLIENTE/README_KIT_PORTATIL.md`
    - score: 0.6500
    - source_status: unregistered
    - heading: ## Finalidade
  - `IRPF/_SISTEMA/04_KIT_PORTATIL_PARA_NOVO_CLIENTE/04_REFERENCIAS_DO_SISTEMA/CONTRATO_INGESTAO_V1.md`
    - score: 0.6439
    - source_status: unregistered
    - heading: # Contrato de Ingestao v1
  - `IRPF/_SISTEMA/04_KIT_PORTATIL_PARA_NOVO_CLIENTE/05_MODELO_DE_CASO_PRONTO/README_MODELO_DE_CASO_PRONTO.md`
    - score: 0.6438
    - source_status: unregistered
    - heading: ## Como usar

### client-registry

- query: cadastro mestre clientes dossie central cliente documentos fiscais irpf atividade rural mapas memoria
- expected_path: `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/README_CADASTRO_MESTRE.md`
- rank: 1
- passed_at_1: true
- passed_at_3: true
- rationale: Must find the client master registry surface, not one individual client folder.
- top_hits:
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/README_CADASTRO_MESTRE.md`
    - score: 0.8245
    - source_status: unregistered
    - heading: # Cadastro Mestre de Clientes
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/IRACY_APARECIDA_ARAUJO/03_IRPF/02_PROCESSAMENTO/02_RELATORIOS_TECNICOS/README_ORGANIZACAO.md`
    - score: 0.7027
    - source_status: unregistered
    - heading: ## Estrutura criada
  - `CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/IRACY_APARECIDA_ARAUJO/03_IRPF/02_PROCESSAMENTO/02_RELATORIOS_TECNICOS/README_PLANILHA_BASE_CAIXA_RURAL.md`
    - score: 0.6768
    - source_status: unregistered
    - heading: ## Como usar
  - `IRPF/_SISTEMA/02_MODELOS/MODELO_MEMORIA_TECNICA_CLIENTE.md`
    - score: 0.6700
    - source_status: unregistered
    - heading: ## Informacoes fixas
  - `IRPF/_SISTEMA/04_KIT_PORTATIL_PARA_NOVO_CLIENTE/04_REFERENCIAS_DO_SISTEMA/MAPA_MESTRE_DO_SERVICO.md`
    - score: 0.6622
    - source_status: unregistered
    - heading: ## Objetivo do sistema
