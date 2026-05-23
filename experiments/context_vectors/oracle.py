from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .evals import EvaluationCase, EvaluationResult, evaluate_queries
from .index import QueryHit, VectorIndex, build_vector_index, query_index


@dataclass(frozen=True)
class OracleCase:
    id: str
    query: str
    expected_path: str
    rationale: str


@dataclass(frozen=True)
class OracleCaseResult:
    case: OracleCase
    hits: tuple[QueryHit, ...]

    @property
    def rank(self) -> int | None:
        for index, hit in enumerate(self.hits, start=1):
            if hit.relative_path == self.case.expected_path:
                return index
        return None

    @property
    def passed_at_1(self) -> bool:
        return self.rank == 1

    @property
    def passed_at_3(self) -> bool:
        rank = self.rank
        return rank is not None and rank <= 3


@dataclass(frozen=True)
class OracleEvaluationReport:
    label: str
    project_root: str
    index: VectorIndex
    cases: tuple[OracleCaseResult, ...]
    summary: EvaluationResult
    state_change: str = "none"

    @property
    def critical_continuity_passed(self) -> bool:
        for result in self.cases:
            if result.case.id == "next-real-work":
                return result.passed_at_3
        return False

    @property
    def has_critical_continuity_case(self) -> bool:
        return any(result.case.id == "next-real-work" for result in self.cases)

    @property
    def all_cases_passed_at_3(self) -> bool:
        return all(result.passed_at_3 for result in self.cases)


RPG_CAMINHADA_ORACLE_CASES: tuple[OracleCase, ...] = (
    OracleCase(
        id="next-real-work",
        query="estado atual proximo passo real implementar edge functions schema ja existe supabase",
        expected_path="cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md",
        rationale="Must find the continuity file that prevents a stale conclusion that schema/formulas still need to be created.",
    ),
    OracleCase(
        id="deployment-level",
        query="nivel de implantacao atual etapa obrigatoria antes de leitura operacional",
        expected_path="cerebro_base/NIVEL_DE_IMPLANTACAO_ATUAL.md",
        rationale="Must find the implantation-level gate called out by the project's own CEREBRO.md flow.",
    ),
    OracleCase(
        id="return-map",
        query="mapa de retorno pendencias vigentes proximas acoes retomada",
        expected_path="cerebro_base/04_MAPA_DE_RETORNO_ATUAL.md",
        rationale="Must find the file that describes active pending work and return path.",
    ),
    OracleCase(
        id="source-hierarchy",
        query="hierarquia de fontes fonte confiavel conflito diagnostico continuidade",
        expected_path="cerebro_base/03_HIERARQUIA_DE_FONTES.md",
        rationale="Must surface the document that defines source authority and the known conflict.",
    ),
)

CEREBRO_SELF_ORACLE_CASES: tuple[OracleCase, ...] = (
    OracleCase(
        id="live-system-state",
        query="system state estado vivo atual suite gate posture freeze next_action runtime continuity",
        expected_path="docs/operations/SYSTEM_STATE.md",
        rationale="Must find the live system snapshot rather than older historical ledgers.",
    ),
    OracleCase(
        id="live-next-action",
        query="opportunity map next item technology lane hybrid scoring next action",
        expected_path="docs/operations/OPPORTUNITY_MAP.md",
        rationale="Must find the human-facing next-action projection.",
    ),
    OracleCase(
        id="machine-queue",
        query="observation center machine primary queue unresolved work single flight overlap policy",
        expected_path="docs/operations/observation_center.toml",
        rationale="Must find the machine-primary queue surface.",
    ),
    OracleCase(
        id="content-layering",
        query="content aware filesystem analysis belongs in experiments extensions read only bootstrap_scan content blind",
        expected_path="docs/handoffs/HANDOFF_CONTENT_AWARE_ANALYSIS_LAYERING.md",
        rationale="Must find the handoff that codifies the current content-analysis layering rule.",
    ),
)

PORTAL_HUMAITA_ORACLE_CASES: tuple[OracleCase, ...] = (
    OracleCase(
        id="project-entry",
        query="ponto de entrada vigente start here leitura obrigatoria memoria retomada dossie canon",
        expected_path="Entrada - Inicio do Projeto.md",
        rationale="Must find the explicit current entry point instead of older loose root files or historical reports.",
    ),
    OracleCase(
        id="live-panel",
        query="painel vigente status ponto de parada nao abrir pva nao transmitir proximo uso recomendado",
        expected_path="00_PAINEL_VIGENTE/Status - Painel Vigente.md",
        rationale="Must find the live panel/status surface that states the current PVA posture and pending work.",
    ),
    OracleCase(
        id="next-real-work",
        query="checklist pre pva 28 arquivos trilha segura erros impeditivos validacao tecnica pendente",
        expected_path="01_TRABALHO_VIGENTE/03_RELATORIOS/CHECKLIST_PRE_PVA.md",
        rationale="Must find the operational checklist for the next real work: manual PVA validation of the current safe track.",
    ),
    OracleCase(
        id="human-validation-dossier",
        query="readme dossie validacao humana ordem de leitura evidencia conclusoes contaminadas bloqueio real pva classificacao",
        expected_path="01_TRABALHO_VIGENTE/03_RELATORIOS/DOSSIE_VALIDACAO_HUMANA_2026-04-11/README.md",
        rationale="Must find the current evidence dossier index, not a single historical or contaminated analysis note.",
    ),
    OracleCase(
        id="canon-order",
        query="canon operacional ordem trilha oficial vigente documento manda hoje ordem execucao verdade operacional",
        expected_path="01_TRABALHO_VIGENTE/03_RELATORIOS/CANON_OPERACIONAL_E_ORDEM_2026-04-06.md",
        rationale="Must find the current canon/order document that defines what commands the project today.",
    ),
    OracleCase(
        id="source-hierarchy",
        query="hierarquia fontes fonte verdade atual trilha oficial canon checklist memoria retomada",
        expected_path="01_TRABALHO_VIGENTE/03_RELATORIOS/HIERARQUIA_DE_FONTES_DO_PROJETO.md",
        rationale="Must find the Portal source-authority document rather than the embedded old Cerebro methodology folder.",
    ),
)

ESCRITORIO_IRPF_CAIXA_RURAL_ORACLE_CASES: tuple[OracleCase, ...] = (
    OracleCase(
        id="structure-general",
        query="estrutura geral escritorio regra separacao sistemas contribuintes dados clientes irpf atividade rural",
        expected_path="README_ESTRUTURA_GERAL.md",
        rationale="Must find the root office structure document that separates systems from contributor/client data.",
    ),
    OracleCase(
        id="official-document-structure",
        query="orientacao oficial estrutura documental xml danfe pdf documento fonte camada operacional deduplicacao",
        expected_path="ORIENTACAO_OFICIAL_ESTRUTURA_DOCUMENTAL.md",
        rationale="Must find the official documentary-structure guidance for XML, DANFE/PDF, source documents, and deduplication.",
    ),
    OracleCase(
        id="master-organization",
        query="organizacao mestra executada arvore final irpf atividade rural contribuintes regra operacional",
        expected_path="ORGANIZACAO_MESTRA_EXECUTADA.md",
        rationale="Must find the root record of the executed master organization.",
    ),
    OracleCase(
        id="contributor-management",
        query="gestao mestra contribuintes indice mestre clientes mapa dominios matriz clientes memoria navegacao",
        expected_path="CONTRIBUINTES/00_GESTAO_MESTRA/README_GESTAO_MESTRA.md",
        rationale="Must find the management surface for contributors rather than a specific client's report.",
    ),
    OracleCase(
        id="irpf-system",
        query="sistema irpf metodologia pipeline operacional oficial contrato ingestao modelos entregaveis novo cliente",
        expected_path="IRPF/README_SISTEMA.md",
        rationale="Must find the IRPF system entry despite many contributor XML/PDF files appearing earlier in traversal.",
    ),
    OracleCase(
        id="client-registry",
        query="cadastro mestre clientes dossie central cliente documentos fiscais irpf atividade rural mapas memoria",
        expected_path="CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/README_CADASTRO_MESTRE.md",
        rationale="Must find the client master registry surface, not one individual client folder.",
    ),
)


def evaluate_oracle(
    root: str | Path,
    cases: tuple[OracleCase, ...] = RPG_CAMINHADA_ORACLE_CASES,
    *,
    label: str = "rpg_caminhada",
    max_files: int = 800,
    hit_limit: int = 5,
) -> OracleEvaluationReport:
    index = build_vector_index(root, max_files=max_files)
    case_results: list[OracleCaseResult] = []
    eval_cases: list[EvaluationCase] = []
    for case in cases:
        hits = query_index(index, case.query, limit=hit_limit)
        case_results.append(OracleCaseResult(case=case, hits=hits))
        eval_cases.append(EvaluationCase(query=case.query, expected_path=case.expected_path))

    return OracleEvaluationReport(
        label=label,
        project_root=str(Path(root).resolve()),
        index=index,
        cases=tuple(case_results),
        summary=evaluate_queries(index, eval_cases),
    )


def render_oracle_markdown(report: OracleEvaluationReport) -> str:
    lines: list[str] = []
    lines.append(f"# Context Vectors Oracle Eval — {report.label}")
    lines.append("")
    lines.append(f"- project_root: `{report.project_root}`")
    lines.append(f"- indexed_files: {report.index.trace.indexed_files}")
    lines.append(f"- skipped_files: {report.index.trace.skipped_files}")
    lines.append(f"- state_status: {report.index.trace.state_status}")
    lines.append(f"- state_change: {report.state_change}")
    lines.append(f"- oracle_cases: {report.summary.total}")
    lines.append(f"- recall_at_1: {report.summary.recall_at_1:.3f}")
    lines.append(f"- recall_at_3: {report.summary.recall_at_3:.3f}")
    if report.has_critical_continuity_case:
        lines.append(
            f"- critical_continuity_result: {'pass' if report.critical_continuity_passed else 'fail'}"
        )
    else:
        lines.append(f"- all_cases_passed_at_3: {str(report.all_cases_passed_at_3).lower()}")
    lines.append("- scoring: deterministic sparse vector similarity plus bounded path/heading metadata cues")
    lines.append("- authority: non-authoritative; advisory evidence only")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    if report.has_critical_continuity_case and report.critical_continuity_passed:
        lines.append(
            "The vector layer found the expected next-real-work document within top 3."
        )
    elif report.has_critical_continuity_case:
        lines.append(
            "The vector layer did not find the expected next-real-work document within top 3."
        )
    elif report.all_cases_passed_at_3:
        lines.append("All oracle cases found their expected paths within top 3.")
    else:
        lines.append("One or more oracle cases did not find their expected paths within top 3.")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    for result in report.cases:
        rank = "miss" if result.rank is None else str(result.rank)
        lines.append(f"### {result.case.id}")
        lines.append("")
        lines.append(f"- query: {result.case.query}")
        lines.append(f"- expected_path: `{result.case.expected_path}`")
        lines.append(f"- rank: {rank}")
        lines.append(f"- passed_at_1: {str(result.passed_at_1).lower()}")
        lines.append(f"- passed_at_3: {str(result.passed_at_3).lower()}")
        lines.append(f"- rationale: {result.case.rationale}")
        lines.append("- top_hits:")
        if result.hits:
            for hit in result.hits:
                lines.append(f"  - `{hit.relative_path}`")
                lines.append(f"    - score: {hit.score:.4f}")
                lines.append(f"    - source_status: {hit.source_status}")
                lines.append(f"    - heading: {hit.heading or '(no heading detected)'}")
        else:
            lines.append("  - _no hits_")
        lines.append("")
    return "\n".join(lines)
