# Cerebro — Instruções para Agentes

## Contexto rápido — leia antes de tudo

| O quê | Onde |
|---|---|
| Postura atual | Freeze deliberado — ver `docs/operations/FREEZE_POLICY.md` |
| Fila ativa | `docs/operations/observation_center.toml` |
| Estado do sistema | `docs/operations/SYSTEM_STATE.md` (Current Snapshot) |
| Próxima revisão obrigatória | `docs/operations/freeze_review.toml` → `next_review_due` |
| Bugs abertos | `docs/operations/BUG_REPORT.md` (Current Snapshot) |

> Itens resolvidos estão em `observation_center_archive.toml` — não consultado em operação normal.
> Histórico de snapshots em `SYSTEM_STATE_HISTORY.md` e `OPPORTUNITY_MAP_HISTORY.md`.

## O que é este projeto

Runtime de engenharia contínua com estado canônico, execução
disciplinada, rollback, approval, DAG, verify, auditabilidade
e coordenação multiagente. O sistema está em **freeze deliberado**
— crescimento de features bloqueado, manutenção corretiva permitida.

## Verificação obrigatória antes de qualquer trabalho

``` 
@'
import errno, os, sys, tempfile, unittest
from pathlib import Path

workspace = Path(r'D:\projetos_cli\ambiente_cerebro\cerebro')
for name in ('.tmp_test', '.tmp_claims', '.tmp_live_proofs'):
    (workspace / name).mkdir(exist_ok=True)
os.environ['TEMP'] = str((workspace / '.tmp_test').resolve())
os.environ['TMP'] = os.environ['TEMP']
os.environ['CEREBRO_SESSION_CLAIMS_DIR'] = str((workspace / '.tmp_claims').resolve())
os.environ['CEREBRO_SESSION_LIVE_PROOFS_DIR'] = str((workspace / '.tmp_live_proofs').resolve())

def _sandbox_mkdtemp(suffix=None, prefix=None, dir=None):
    prefix, suffix, dir, output_type = tempfile._sanitize_params(prefix, suffix, dir)
    names = tempfile._get_candidate_names()
    if output_type is bytes:
        names = map(os.fsencode, names)
    for _ in range(tempfile.TMP_MAX):
        name = next(names)
        path = os.path.join(dir, prefix + name + suffix)
        sys.audit('tempfile.mkdtemp', path)
        try:
            os.mkdir(path, 0o777)
        except FileExistsError:
            continue
        except PermissionError:
            if os.name == 'nt' and os.path.isdir(dir) and os.access(dir, os.W_OK):
                continue
            raise
        return os.path.abspath(path)
    raise FileExistsError(errno.EEXIST, 'No usable temporary directory name found')

tempfile.mkdtemp = _sandbox_mkdtemp
suite = unittest.defaultTestLoader.discover('tests')
result = unittest.TextTestRunner(verbosity=1).run(suite)
print(f'SUMMARY ran={result.testsRun} failures={len(result.failures)} errors={len(result.errors)} skipped={len(result.skipped)}')
raise SystemExit(0 if result.wasSuccessful() else 1)
'@ | python -
```

Se houver falha: **pare tudo e corrija antes de continuar**.
Suíte vermelha = estado inválido = nada pode avançar.

Neste shell/sandbox, o comando bruto `python -m unittest discover -s tests -v`
não é a fonte de verdade por causa do `tempfile.mkdtemp(..., 0o700)` no
Windows. Use o runner equivalente acima com `TEMP/TMP` e authority overrides
locais.

## Como este projeto trabalha — leia isto

O Cerebro opera em **loop autônomo com memória externa**.
O contexto do agente reseta entre iterações.
A memória persiste via arquivos — não via contexto.

Leia sempre antes de começar:
1. triggers formais ativos em `docs/operations/` — boundary vivo e stop conditions
2. `docs/operations/observation_center.toml` — fila estruturada de observações ainda resolvíveis
3. `docs/operations/SYSTEM_STATE.md` — estado atual
4. `docs/operations/OPPORTUNITY_MAP.md` — projeção humana do próximo passo
5. planos vivos específicos do trabalho corrente
6. `docs/operations/BUG_REPORT.md` — problemas abertos
7. `docs/operations/PHASE_CLOSURE.md` — o que já foi encerrado
8. `docs/operations/FREEZE_POLICY.md` — o que está bloqueado

Se `OPPORTUNITY_MAP.md` não existe: execute Modo Bootstrap abaixo.

Use `docs/operations/observation_center.toml` como fila canônica legível por
máquina. `SYSTEM_STATE.md` e `OPPORTUNITY_MAP.md` continuam sendo projeções
humanas do estado vivo. Um trigger formal ativo pode estreitar ou reabrir um
boundary específico dentro do freeze; quando trigger, centro e projeções
divergirem, a iteração vira reconciliação-first e nenhum novo slice começa
antes desse fechamento. Sempre que surgir um item ainda resolvível, registre ou
atualize esse item no centro antes de resumi-lo nos snapshots narrativos.

## Arquitetura — nunca viole estas fronteiras

```
core/          ← autoridade única sobre estado canônico
cli/           ← orquestração fina do core
extensions/    ← consumidores read-only, sem autoridade
tests/         ← cobertura proporcional a cada mudança
docs/          ← documenta comportamento real, não intenção
```

Nunca: extension adquire autoridade sobre core.
Nunca: CLI toca `state.json` diretamente.
Nunca: segunda fonte de verdade.
Nunca: toque `core/schema.py` sem decisão de arquitetura explícita
documentada.
Sem trigger formal ativo, limite mutações a `docs/` e a este arquivo. Com
trigger formal ativo, siga exatamente a whitelist e as stop conditions do
trigger; não extrapole o boundary reaberto.

## Comandos de teste

```bash
python -m unittest discover -s tests -v        # runner bruto; neste shell use o gate equivalente acima
python -m unittest tests.test_state_store -v   # módulo de estado
python -m unittest tests.test_validate -v      # retenção e validate
python -m unittest tests.test_action_runtime -v # actions
python -m unittest tests.test_architecture -v  # contrato arquitetural
```

## Escala de esforço

**NÍVEL 1** — diagnóstico, leitura, correção documental
Execute diretamente. Sem subagentes. Máximo 10 ações.

**NÍVEL 2** — mudança pontual em módulo isolado
`researcher` → `implementer` → `verifier`. Serial.

**NÍVEL 3** — fluxo crítico ou múltiplos módulos
`researcher` + `reviewer` paralelo → `implementer` (trilha única)
→ `verifier` → `documenter` paralelo.

Regras de thread: máximo 5 simultâneos. Feche concluídos antes
de abrir novos. Nunca spawne para nível 1 ou 2.

## Subagentes disponíveis em .codex/agents/

| Agente | Quando usar |
|---|---|
| `researcher` | mapear evidência antes de qualquer mudança |
| `reviewer` | avaliar risco e freeze antes de implementar |
| `architect` | impacto estrutural e contratos entre módulos |
| `implementer` | executar slice aprovado |
| `verifier` | confirmar resultado após implementação |
| `documenter` | atualizar docs após mudança nível 2 ou 3 |
| `red_teamer` | bypass, no-ops, regressões silenciosas |
| `test_engineer` | lacunas de cobertura e testes frágeis |
| `perf_analyst` | hotspots de custo |
| `security_reviewer` | superfícies de risco e disclosure |
| `reliability_engineer` | rollback, recovery, idempotência |
| `debug_investigator` | causa raiz de crash ou erro conhecido |
| `planner` | DAG de tarefas com dependências |

Esses labels descrevem helpers e especializações de análise.
Eles não ampliam o conjunto de papéis canônicos do runtime.
Ao registrar um achado, trate o label do helper como alias
operacional não-canônico e preserve os sete papéis canônicos.

## Debate entre agentes — quando acionar

Obrigatório quando:
- dois caminhos defensáveis sem dominância clara
- mudança toca `apply`, `verify`, `rollback`, `session`, `schema`
- `researcher` e `reviewer` divergem
- risco de falso consenso

Formato: spawne os dois divergentes com escopo restrito.
"Tentem quebrar o argumento um do outro. Concluam: posição
vencedora + razão + o que mudaria para a perdedora se tornar válida."
Desempate: use o helper estrutural `architect` apenas como
parecer técnico não-canônico. O registro final deve continuar
nos sete papéis canônicos. Se ainda ficar inconclusivo,
marque como decisão humana necessária.

## Nunca faça isto

- Modificar `core/` fora do boundary autorizado por trigger formal ativo ou
  decisão de arquitetura explícita
- Violar o freeze sem Formal Resume Trigger satisfeito
- Declarar melhoria sem teste ou evidência rastreável
- Declarar idempotência sem teste que force o mesmo segundo
- Usar `except: pass` sem registro em audit
- Deixar `state.json` em escrita parcial
- Tratar mudança de shape ou ordem de validação não explicitamente coberta como
  "segura" só porque os testes existentes passaram
- Avançar ao próximo slice sem o anterior verde
- Deixar a suíte vermelha ao encerrar

## Approval gate — três caminhos formais

Quando uma ação chega ao gate de aprovação humana, há três respostas válidas:

1. **Aprovar** — execute exatamente como proposto.
2. **Rejeitar** — não execute. Registre o motivo no campo `rejection_context`
   do action file antes de encerrar o slice. O agente lê esse campo no próximo
   ciclo de planejamento para não repetir a mesma proposta.
3. **Editar antes de executar** — o humano modifica o arquivo de ação
   (ex.: ajusta parâmetros, restringe escopo, corrige comando) e só então
   confirma execução. O agente trata a versão editada como a ação canônica;
   o diff entre original e editado fica registrado no audit trail.

Aprovação binária sem contexto de rejeição é o padrão mínimo.
Edit-before-execute é o padrão preferido quando o problema é de escopo,
não de intenção.

## Padrão de correção consolidado

Descoberto nos rounds 8-9. Use sempre:
1. Corrija no menor boundary operacional possível
2. Falhe fechado — nunca silenciosamente
3. Registre via audit já existente
4. Adicione teste que force exatamente o modo de falha
5. Prefira rollback a retry cego
6. Se uma alteração passar nos testes mas ainda puder ter mudado shape ou ordem
   de validação fora da cobertura explícita, trate como risco e pare

## Loop autônomo — como operar

```
TODA ITERAÇÃO:
1. Localize triggers formais ativos
2. Leia `docs/operations/observation_center.toml`
3. Leia `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md` e os planos vivos relevantes
4. Se trigger, centro e projeções divergirem, faça reconciliação first
5. Confirme suíte verde quando um slice real sobreviver à triagem
6. Declare o único slice desta iteração (seja específico)
7. Execute com o nível de esforço correto
8. Atualize `observation_center.toml` e `OPPORTUNITY_MAP.md` com resultado
9. Confirme suíte verde novamente
10. Atualize `SYSTEM_STATE.md`
11. Encerre limpo

PRIORIDADE:
1. Suíte vermelha → corrija antes de tudo
2. divergência viva entre trigger, centro e projeções → reconcilie antes de implementar
3. CRÍTICO aberto → ataque imediatamente
4. ALTO aberto → em seguida
5. observação `open` com boundary autorizado → execute pela ordem do centro
6. MELHORIA → por ordem do mapa
7. Fila vazia → prova de parada (P1-P5)
8. Prova limpa → encerramento formal
```

## Modo Bootstrap — se OPPORTUNITY_MAP não existe

Spawne em paralelo: `architect`, `researcher`, `red_teamer`,
`perf_analyst`, `test_engineer`. Cada um analisa seu eixo.
Após debates necessários, `documenter` cria `OPPORTUNITY_MAP.md`
e `SYSTEM_STATE.md`. Só então inicie o loop.

## Prova de parada — quando a fila estiver vazia

Feche agentes anteriores. Spawne em paralelo:
- `perf_analyst` — P1: novo hotspot de custo?
- `red_teamer` — P2: nova superfície de bypass?
- `reliability_engineer` — P3: cenário de falha novo?
- `architect` — P4: duplicação ou acoplamento novo?
- `test_engineer` — P5: teste frágil ou edge case?

Todos nível 0 → encerre formalmente.
Qualquer achado → adicione ao mapa e continue.

## Encerramento formal

Só encerre quando:
- Fila CRÍTICO e ALTO vazias
- 5 ciclos de prova de parada sem achado relevante
- gate obrigatório acima verde (`python -m unittest discover -s tests -v` equivalente neste shell)
- `python -m unittest tests.test_architecture -v` verde
- `PHASE_CLOSURE.md` atualizado com evidência rastreável

Após encerramento: `cerebro analyze` para trabalho operacional.
Retorne ao loop apenas quando Formal Resume Trigger satisfeito.

## Papéis canônicos

Use apenas: `Orchestrator`, `Planner`, `Researcher`, `Implementer`,
`Reviewer`, `Verifier`, `Documenter`.

Labels históricos (`Guardião`, `Comprovador`, `Orquestrador`,
`Executor`, `Testador`, `Auditor`) são não-canônicos.

## Formato de fechamento — obrigatório em toda iteração

```
ITERAÇÃO [N] — [item] — NÍVEL [1/2/3]
MODO: [BOOTSTRAP/EXECUÇÃO/PROVA DE PARADA/ENCERRAMENTO]
AGENTES: [lista com veredicto + debates com conclusão]
RESULTADO: [concluído/bloqueado/revertido]
EVIDÊNCIA: [arquivo:linha + teste que prova]
SUÍTE: [N antes → N depois, N falhas]
ROLLBACK: [sim/não + razão]
OPPORTUNITY_MAP: [próximo item na fila]
```
