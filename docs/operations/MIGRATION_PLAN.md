# Migration Plan — External Cerebro Model

## Status de implementação

- `FATIA 1 — --project-root global em cli/main.py`: concluída em `2026-04-18`.
  - Dispatcher global aceita `--project-root` antes e depois do subcomando em `cli/main.py:32-57` e `cli/main.py:320-322`.
  - `plan --input-file` agora resolve relativo ao root lógico em `cli/commands/plan.py:105` e `cli/commands/_plan_input.py:11-61`.
  - Cobertura mínima adicionada em `tests/test_cli.py:224-344` e `tests/test_alpha_runtime.py:199-225`.
- `FATIA 2 — Menu de contexto ao abrir`: concluída em `2026-04-18`.
  - `cli/main.py` agora intercepta `argv` vazio antes do parser, falha fechado sem TTY e converte o menu em dispatch explícito para `analyze` com `cwd` ou `--project-root`: `cli/main.py:32-55`, `cli/main.py:344-355`.
  - Cobertura do menu adicionada em `tests/test_cli.py:286-385`, incluindo modo desenvolvimento, gerenciamento de projeto, seleção inválida, `project_root` vazio, ausência de terminal e `main(None)`.
- `FATIA 3 — Registro de projetos`: concluída em `2026-04-18`.
  - `cli/project_registry.py` introduz o catálogo opcional em `~/.cerebro/projects.toml`, com leitura normalizada, escrita atômica e serialização explícita de writers concorrentes via lock irmão do arquivo.
  - `cli/main.py` agora lista projetos registrados, permite selecionar entrada existente ou registrar root novo e sempre materializa o resultado como `--project-root ... analyze`.
  - Cobertura do fluxo adicionada em `tests/test_cli.py:345-541`, incluindo registro inicial, seleção de projeto já registrado, falha fechada com TOML inválido e concorrência entre writers do registry.
- Próxima fatia canônica: `FATIA 4 — Dashboard de estado ao abrir`.
- Pendências ainda não iniciadas nesta trilha: `FATIA 4` a `FATIA 6`.

## Estado atual confirmado

- O CLI oficial ainda ancora todo comando em `Path.cwd()` no dispatcher global: `cli/main.py:315`.
- Apenas `bootstrap-scan` aceita root explícito hoje, via `--root`, e a própria help afirma que esse root vale só para o scan: `cli/main.py:238-242`.
- O handler de `bootstrap-scan` faz override local do `cwd` com `Path(args.root).resolve()`: `cli/commands/bootstrap_scan.py:282-283`.
- O runtime canônico já é por projeto-root. `StateStore` recebe `root`, resolve `Path(root).resolve()`, e deriva `.cerebro`, `state.json`, `session.local.json` e `runtime.lock` desse root: `core/state_store.py:120-127`.
- A identidade de sessão já está vinculada ao root resolvido. `root_sha256` é `sha256(str(self.root))`: `core/state_store.py:2568-2570`.
- Claims e live proofs externos validam o mesmo `root_sha256` contra o root atual: `core/state_store.py:3065-3074`, `core/state_store.py:3163-3174`.
- O estado canônico continua em `<project-root>/.cerebro`; não há `project_root` persistido no `state.json`: `core/schema.py:63-86`.
- O comportamento operacional atual já foi usado em `estoque_pioneira`, `Portal` e `rpg_caminhada`: `docs/operations/REAL_OPERATION_REPORT.md:75-97`.
- O limite real ainda ativo é operacional: `bootstrap-scan --root` ajuda a localizar o projeto, mas o restante do fluxo continua preso ao diretório atual: `docs/operations/REAL_OPERATION_REPORT.md:142-148`.

## Modelo proposto

Cerebro instalado fora dos projetos e operando sobre eles por root explícito.

- CLI com `--project-root` opt-in.
- `default = cwd` para preservar compatibilidade.
- Estado canônico permanece dentro do projeto gerenciado em `<project-root>/.cerebro`.
- Dois `AGENTS.md` com propósitos distintos:
  - `AGENTS.md` do Cerebro: engenharia do próprio runtime.
  - `AGENTS.md` do projeto gerenciado: operação local do projeto via Cerebro.

## Gap real (o que falta)

Ordenado por esforço, menor primeiro.

1. Concluído — adicionar seleção explícita de root no dispatcher global.
   - Evidência implementada: `cli/main.py:32-57`, `cli/main.py:320-322`.
   - Resultado: `--project-root` funciona antes e depois do subcomando, com `cwd` preservado como default.

2. Concluído — corrigir o caso adjacente de `plan --input-file`.
   - Evidência implementada: `cli/commands/plan.py:105`, `cli/commands/_plan_input.py:11-61`.
   - Resultado: `Path(input_file)` relativo agora ancora no root lógico recebido pelo comando.

3. Concluído — cobrir o novo comportamento com testes opt-in.
   - Evidência implementada: `tests/test_cli.py:224-344`, `tests/test_alpha_runtime.py:199-225`.
   - Cobertura adicionada:
     - `cwd` continua default do dispatcher;
     - `--project-root` funciona antes e depois do subcomando;
     - `plan --input-file` lê do project root explícito;
     - `bootstrap-scan --root` continua dominante sobre o root global.

4. Concluído — adicionar menu de contexto ao abrir.
   - Evidência implementada: `cli/main.py:32-55`, `cli/main.py:344-355`.
   - Resultado:
     - sem argumentos, o CLI oferece `(1) Desenvolvimento` e `(2) Gerenciar projeto`;
     - a opção `1` despacha `analyze` no `cwd`;
     - a opção `2` materializa `--project-root` explícito e reusa o mesmo dispatcher;
     - sem terminal, seleção inválida ou `project_root` vazio, o fluxo falha fechado.

5. Concluído — adicionar registro global opcional de projetos.
   - Evidência implementada: `cli/project_registry.py:1-140`, `cli/main.py:33-92`, `tests/test_cli.py:345-541`.
   - Resultado:
     - o menu `(2) Gerenciar projeto` lista projetos já conhecidos do usuário;
     - roots novos são persistidos em `~/.cerebro/projects.toml` como metadata opcional;
     - selecionar projeto existente apenas rematerializa `--project-root`, sem transferir autoridade para fora do dispatcher;
     - writes concorrentes no registry são serializados para não perder atualização silenciosamente.

6. Ajustar textos que hoje descrevem o `cwd` como única autoridade.
   - Evidência: `cli/main.py:61`, `cli/main.py:238`, `cli/output.py:42`, `cli/output.py:48`.
   - Implementação: trocar wording para “project root” quando o root vier de argumento; manter a semântica atual quando não vier.

7. Separar claramente instruções de engenharia vs operação.
   - Evidência: `AGENTS.md:3-8`, `AGENTS.md:34-50`, `AGENTS.md:136-187`.
   - Implementação: manter `AGENTS.md` do Cerebro e criar template mínimo de `AGENTS.md` para projetos gerenciados.

## Slice mínimo aprovado pelos debates

Consenso dos debates 1 e 2:

- `cli/main.py`
  - adicionar `--project-root` no parser raiz;
  - resolver o root uma vez;
  - manter `cwd` como default compatível.
- `cli/commands/_plan_input.py`
  - alinhar `--input-file` ao mesmo root.
- testes mínimos cobrindo o modo opt-in.

Razão:

- O plumbing já aceita `root` injetado em todos os handlers: `cli/main.py:315`.
- `StateStore(root)` já usa esse root como autoridade única: `core/state_store.py:120-127`.
- Fazer só o dispatcher criaria um contrato parcialmente verdadeiro, porque `plan --input-file` continuaria ancorado no `cwd`: `cli/commands/_plan_input.py:59`.

## Riscos confirmados

Por severidade.

- Médio — concorrência no registry global podia perder atualização sem erro.
  - Confirmado e corrigido nesta fatia ao serializar o read-modify-write em `cli/project_registry.py`.
  - Evidência: `cli/project_registry.py:37-83`, `tests/test_cli.py:492-541`.

- Médio — mis-targeting operacional.
  - Com `--project-root`, o operador pode apontar para outro workspace sem trocar de diretório.
  - Isso não cria privilégio novo, mas amplia a superfície de erro humano e wrappers.
  - Evidência: hoje o alvo é implícito em `cli/main.py:315`; com root explícito, todo o runtime passaria a obedecer esse root.

- Baixo — footgun de consistência entre comandos/sessão.
  - Misturar comandos com roots diferentes pode fazer a sessão falhar fechada por mismatch de `root_sha256`.
  - Evidência: `core/state_store.py:3065-3074`, `core/state_store.py:3163-3174`.

- Baixo — drift de help e mensagens se o patch parar cedo.
  - O código aceitaria root explícito, mas a UX continuaria dizendo “current directory”.
  - Evidência: `cli/main.py:61`, `cli/main.py:238`, `cli/output.py:42`, `cli/output.py:48`.

## Riscos descartados

- Path traversal via `--project-root`.
  - Descartado porque `StateStore` resolve `Path(root).resolve()` antes de derivar `.cerebro` e `runtime.lock`: `core/state_store.py:120-127`.

- Quebra do binding de claims/proofs.
  - Descartado se o mesmo root resolvido for propagado até `StateStore`.
  - Evidência: `core/state_store.py:1131-1144`, `core/state_store.py:2568-2570`, `core/state_store.py:3065-3074`, `core/state_store.py:3163-3174`.

- Colisão de lock entre projetos distintos.
  - Descartado porque o lock continua em `<root>/.cerebro/runtime.lock`: `core/state_store.py:127`, `core/state_store.py:4651-4684`.

- Invalidação automática de `state.json` existente.
  - Descartado porque o schema não persiste `project_root` absoluto: `core/schema.py:63-86`.

## Template de AGENTS.md para projetos gerenciados

Versão mínima derivada do Debate 3.

Seções obrigatórias:

1. O que é este projeto.
2. Qual é o root operacional.
3. Gate de contexto:
   - “estou fazendo engenharia no Cerebro ou operando um projeto via Cerebro?”
   - Base: `docs/operations/AGENT_PROTOCOL.md:26-30`.
4. Modo de entrada:
   - `bootstrap` vs `continuous work`.
   - Base: `docs/operations/OPERATIONS_BASELINE.md:29-31`.
5. Entrypoint canônico:
   - projeto inicializado: `cerebro analyze`;
   - projeto novo: `init -> import-context -> checkpoint -> validate`.
   - Base: `docs/operations/PROTOCOL_SUPERVISOR_AUTONOMOUS.md:752-754`.
6. Fontes canônicas locais do projeto.
7. Fronteiras arquiteturais do projeto gerenciado.
8. Gates de teste/verificação do projeto gerenciado.
9. Regras de approval/verify/rollback que importam para aquele domínio.
10. Formato de fechamento com decisão, evidência e risco residual.

O que o operador colocaria em `estoque_pioneira`:

- root do projeto;
- 2-5 arquivos humanos canônicos iniciais;
- arquitetura local real;
- como rodar os testes daquele projeto;
- critérios de aprovação para mudanças sensíveis;
- backlog/board local, se existir.

## Compatibilidade com projetos existentes

- `estoque_pioneira`, `Portal` e `rpg_caminhada` continuam funcionando sem mudança se `--project-root` for opt-in e o default continuar `cwd`.
  - Evidência: `docs/operations/REAL_OPERATION_REPORT.md:75-97`, `cli/main.py:315`.
- Não há migração de schema exigida para esses projetos.
  - Evidência: `core/schema.py:63-86`.
- Sessões existentes continuam válidas quando `--project-root` resolve para o mesmo root absoluto usado hoje.
  - Evidência: `core/state_store.py:120`, `core/state_store.py:2568-2570`, `core/state_store.py:3065-3074`, `core/state_store.py:3163-3174`.
- Cuidado manual:
  - não alternar entre `cwd` e `--project-root` apontando para roots diferentes dentro da mesma sessão;
  - não assumir que mover/renomear o projeto preserva a mesma identidade de sessão, porque o binding é por path resolvido.

## Recomendação

Implementar agora, em fatia pequena.

Razão:

- O modelo externo já está perto do alvo e não exige mudança de schema para a meta mínima.
- O menor slice seguro é pequeno, local e verificável.
- Os riscos confirmados são operacionais e controláveis com `opt-in`, `default = cwd` e testes de regressão.
- O principal cuidado real já está isolado: `cli/commands/_plan_input.py:59`.
