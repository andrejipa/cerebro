from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from core.state_store import StateStore

from experiments.context_vectors import (
    DEFAULT_MAX_HEAD_BYTES,
    CEREBRO_SELF_ORACLE_CASES,
    ESCRITORIO_IRPF_CAIXA_RURAL_ORACLE_CASES,
    EvaluationCase,
    PORTAL_HUMAITA_ORACLE_CASES,
    build_vector_index,
    cosine_similarity,
    embed_text,
    evaluate_queries,
    evaluate_oracle,
    query_index,
    render_oracle_markdown,
)
from experiments.context_vectors.index import ContextVectorError


def _init_sources(root: Path, paths: list[str]) -> None:
    run_init(root, None)
    store = StateStore(root)
    store.register_sources(paths)
    store.update_checkpoint(
        {
            "goal": "Goal",
            "summary": "Summary",
            "next_step": "Next",
            "constraints": [],
        }
    )
    store.validate_state()


class ContextVectorTests(unittest.TestCase):
    def test_embed_text_is_deterministic_and_similarity_is_ordered(self) -> None:
        first = embed_text("current project state and continuity memory")
        second = embed_text("current project state and continuity memory")
        unrelated = embed_text("database migration and sql schema")

        self.assertEqual(first, second)
        self.assertGreater(cosine_similarity(first, second), cosine_similarity(first, unrelated))

    def test_cached_vectors_cannot_be_mutated_by_callers(self) -> None:
        vector = embed_text("current project state and continuity memory immutable")
        bucket = next(iter(vector.weights))

        with self.assertRaises(TypeError):
            vector.weights[bucket] = 0.0  # type: ignore[index]

        again = embed_text("current project state and continuity memory immutable")
        self.assertGreater(cosine_similarity(vector, again), 0.99)

    def test_query_ranks_expected_context_document_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# App\n\nGeneral setup notes.\n", encoding="utf-8")
            (root / "04_MEMORIA_CONTINUIDADE_ATUAL.md").write_text(
                "# Memoria de continuidade atual\n\nSchema v1.1.0 exists. Next step: implement Edge Functions.",
                encoding="utf-8",
            )
            (root / "schema.sql").write_text("create table player_state(id uuid primary key);", encoding="utf-8")

            index = build_vector_index(root)
            hits = query_index(index, "estado atual continuidade next step edge functions", limit=3)

            self.assertEqual(hits[0].relative_path, "04_MEMORIA_CONTINUIDADE_ATUAL.md")
            self.assertEqual(index.trace.state_status, "absent")
            self.assertEqual(index.trace.state_change, "none")

    def test_path_token_match_can_lift_named_operational_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs = root / "docs" / "operations"
            docs.mkdir(parents=True)
            (docs / "OPPORTUNITY_MAP.md").write_text("# Opportunity Map\n\nNext item projection.", encoding="utf-8")
            (root / "notes.md").write_text(
                "# Generic\n\nnext item technology lane hybrid scoring next action " * 20,
                encoding="utf-8",
            )

            index = build_vector_index(root)
            hits = query_index(index, "opportunity map next item technology lane", limit=2)

            self.assertEqual(hits[0].relative_path, "docs/operations/OPPORTUNITY_MAP.md")

    def test_live_surface_cues_lift_current_entry_over_stale_session_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            current = root / "00_PAINEL_VIGENTE"
            current.mkdir()
            (current / "Status - Painel Vigente.md").write_text(
                "# Painel Vigente\n\nEstado atual, trilha oficial, PVA pendente.",
                encoding="utf-8",
            )
            old = root / "05_GOVERNANCA" / "00_MANUAL_CONTINUIDADE"
            old.mkdir(parents=True)
            (old / "Memoria - Contexto Atual da Sessao.md").write_text(
                "# Contexto Atual\n\nEstado atual, trilha oficial, PVA pendente. " * 8,
                encoding="utf-8",
            )

            index = build_vector_index(root)
            hits = query_index(index, "estado atual painel vigente trilha oficial pva", limit=2)

            self.assertEqual(hits[0].relative_path, "00_PAINEL_VIGENTE/Status - Painel Vigente.md")

    def test_general_surface_cues_lift_shallow_readme_over_deep_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            system = root / "IRPF"
            system.mkdir()
            (system / "README_SISTEMA.md").write_text("# Sistema IRPF\n\nEntrada do sistema.", encoding="utf-8")
            deep = system / "_SISTEMA" / "01_METODOLOGIA"
            deep.mkdir(parents=True)
            (deep / "CONTRATO_INGESTAO_V1.md").write_text(
                "# Contrato de Ingestao v1\n\nsistema irpf metodologia pipeline operacional oficial contrato ingestao modelos entregaveis novo cliente "
                * 4,
                encoding="utf-8",
            )

            index = build_vector_index(root)
            hits = query_index(index, "sistema irpf metodologia pipeline operacional oficial", limit=2)

            self.assertEqual(hits[0].relative_path, "IRPF/README_SISTEMA.md")

    def test_client_registry_cues_lift_master_readme_over_individual_client_maps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            registry = root / "CONTRIBUINTES" / "01_CADASTRO_MESTRE_CLIENTES"
            registry.mkdir(parents=True)
            (registry / "README_CADASTRO_MESTRE.md").write_text(
                "# Cadastro Mestre de Clientes\n\nDossie central, documentos fiscais, IRPF e atividade rural.",
                encoding="utf-8",
            )
            client_map = registry / "CLIENTE_A" / "99_REFERENCIAS_E_MAPAS"
            client_map.mkdir(parents=True)
            (client_map / "00_MAPA_DO_CLIENTE.md").write_text(
                "# Cliente Mestre\n\ncadastro mestre clientes dossie central cliente documentos fiscais irpf atividade rural mapas memoria "
                * 4,
                encoding="utf-8",
            )

            index = build_vector_index(root)
            hits = query_index(index, "cadastro mestre clientes dossie central cliente documentos fiscais", limit=2)

            self.assertEqual(
                hits[0].relative_path,
                "CONTRIBUINTES/01_CADASTRO_MESTRE_CLIENTES/README_CADASTRO_MESTRE.md",
            )

    def test_registered_source_status_uses_public_state_when_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Registered\n", encoding="utf-8")
            (root / "NOTES.md").write_text("# Unregistered\n", encoding="utf-8")
            _init_sources(root, ["README.md"])

            index = build_vector_index(root)
            statuses = {doc.relative_path: doc.source_status for doc in index.documents}

            self.assertEqual(index.trace.state_status, "valid")
            self.assertEqual(index.trace.registered_source_count, 1)
            self.assertEqual(statuses["README.md"], "registered")
            self.assertEqual(statuses["NOTES.md"], "unregistered")

    def test_invalid_legacy_state_falls_back_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            runtime = root / ".cerebro"
            runtime.mkdir()
            state = runtime / "state.json"
            state.write_text('{"version": "1", "revision": 1, "sources": []}', encoding="utf-8")
            (root / "README.md").write_text("# Project\n", encoding="utf-8")
            before = state.read_bytes()

            index = build_vector_index(root)

            self.assertTrue(index.trace.state_status.startswith("invalid:"))
            self.assertEqual(state.read_bytes(), before)
            self.assertEqual(index.trace.state_change, "none")

    def test_binary_symlink_and_vendor_files_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Project\n", encoding="utf-8")
            (root / "blob.md").write_bytes(b"\x00\x01binary")
            vendor = root / "node_modules"
            vendor.mkdir()
            (vendor / "README.md").write_text("# Should not index\n", encoding="utf-8")
            local_archive = root / "_local" / "legacy"
            local_archive.mkdir(parents=True)
            (local_archive / "SYSTEM_STATE.md").write_text("# Stale archive\n", encoding="utf-8")
            try:
                (root / "link.md").symlink_to(root / "README.md")
            except OSError:
                pass

            index = build_vector_index(root)
            paths = {doc.relative_path for doc in index.documents}

            self.assertEqual(paths, {"README.md"})
            self.assertGreaterEqual(index.trace.skipped_files, 1)

    def test_archival_temp_and_nested_cerebro_dirs_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Project\n", encoding="utf-8")
            archive = root / "90_HISTORICO_PRE_DOSSIE"
            archive.mkdir()
            (archive / "STATUS.md").write_text("# Stale status\n", encoding="utf-8")
            sensitive_history = root / "04_HISTORICO_SENSIVEL_BACKUP_FISCAL"
            sensitive_history.mkdir()
            (sensitive_history / "README.md").write_text("# Backup history\n", encoding="utf-8")
            temp = root / "98_TEMPORARIOS_DESCARTE_TECNICO"
            temp.mkdir()
            (temp / "notes.md").write_text("# Temporary notes\n", encoding="utf-8")
            nested = root / "cerebro" / "cerebro_base"
            nested.mkdir(parents=True)
            (nested / "03_HIERARQUIA_DE_FONTES.md").write_text("# Old Cerebro hierarchy\n", encoding="utf-8")

            index = build_vector_index(root)
            paths = {doc.relative_path for doc in index.documents}

            self.assertEqual(paths, {"README.md"})

    def test_hidden_text_files_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Project\n", encoding="utf-8")
            (root / ".secret.toml").write_text("token = 'do-not-index'\n", encoding="utf-8")

            index = build_vector_index(root)
            paths = {doc.relative_path for doc in index.documents}

            self.assertEqual(paths, {"README.md"})
            self.assertGreaterEqual(index.trace.skipped_files, 1)

    def test_head_caps_prevent_tail_only_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            body = "# Safe head\n" + ("padding " * 8000) + "\nTAIL_UNIQUE_EDGE_FUNCTIONS_MARKER"
            (root / "large.md").write_text(body, encoding="utf-8")
            (root / "small.md").write_text("# Edge Functions\nimplement edge functions here", encoding="utf-8")

            index = build_vector_index(root, max_head_bytes=DEFAULT_MAX_HEAD_BYTES)
            hits = query_index(index, "TAIL_UNIQUE_EDGE_FUNCTIONS_MARKER", limit=2)

            self.assertNotEqual(hits[0].relative_path, "large.md")

    def test_max_files_counts_indexable_text_candidates_not_binary_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            noisy = root / "a-noise"
            noisy.mkdir()
            for index in range(8):
                (noisy / f"blob-{index}.pdf").write_bytes(b"%PDF ignored")
            later = root / "z-system"
            later.mkdir()
            (later / "README.md").write_text("# System\n\npipeline operacional oficial", encoding="utf-8")

            index = build_vector_index(root, max_files=1)
            paths = {doc.relative_path for doc in index.documents}

            self.assertEqual(paths, {"z-system/README.md"})

    def test_evaluate_queries_reports_recall_and_missing_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "continuity.md").write_text("# Continuidade\nNext step: Edge Functions", encoding="utf-8")
            (root / "domain.md").write_text("# Regras do dominio\nfitness RPG proof levels", encoding="utf-8")

            index = build_vector_index(root)
            result = evaluate_queries(
                index,
                [
                    EvaluationCase(query="retomada edge functions", expected_path="continuity.md"),
                    EvaluationCase(query="missing topic", expected_path="missing.md"),
                ],
            )

            self.assertEqual(result.total, 2)
            self.assertEqual(result.hits_at_1, 1)
            self.assertEqual(result.hits_at_3, 1)
            self.assertEqual([case.expected_path for case in result.missing], ["missing.md"])

    def test_oracle_report_marks_critical_continuity_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            base = root / "cerebro_base"
            base.mkdir()
            (base / "04_MEMORIA_CONTINUIDADE_ATUAL.md").write_text(
                "# Memoria de continuidade atual\n\nSchema v1.1.0 exists. Next step: implement Edge Functions.",
                encoding="utf-8",
            )
            (base / "NIVEL_DE_IMPLANTACAO_ATUAL.md").write_text(
                "# Nivel de implantacao atual\n\nLeitura obrigatoria antes da operacao.",
                encoding="utf-8",
            )
            (base / "04_MAPA_DE_RETORNO_ATUAL.md").write_text(
                "# Mapa de retorno atual\n\nPendencias vigentes e proximas acoes.",
                encoding="utf-8",
            )
            (base / "03_HIERARQUIA_DE_FONTES.md").write_text(
                "# Hierarquia de fontes\n\nDefine fonte confiavel e conflito entre diagnostico e continuidade.",
                encoding="utf-8",
            )
            (base / "04_DIAGNOSTICO_INICIAL_ATUAL.md").write_text(
                "# Diagnostico inicial\n\nEstado zero e schema ainda nao criado.",
                encoding="utf-8",
            )

            report = evaluate_oracle(root)
            rendered = render_oracle_markdown(report)

            self.assertEqual(report.label, "rpg_caminhada")
            self.assertTrue(report.critical_continuity_passed)
            self.assertIn("- state_change: none", rendered)
            self.assertIn("- critical_continuity_result: pass", rendered)
            self.assertIn("cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md", rendered)

    def test_oracle_report_exposes_critical_continuity_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Empty project\n", encoding="utf-8")

            report = evaluate_oracle(root)
            rendered = render_oracle_markdown(report)

            self.assertFalse(report.critical_continuity_passed)
            self.assertIn("- critical_continuity_result: fail", rendered)
            self.assertIn("- rank: miss", rendered)

    def test_oracle_renderer_uses_project_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True)
            (root / "docs" / "operations" / "SYSTEM_STATE.md").write_text(
                "# System State\n\nCurrent Snapshot gate posture freeze next_action runtime continuity.",
                encoding="utf-8",
            )

            report = evaluate_oracle(
                root,
                (CEREBRO_SELF_ORACLE_CASES[0],),
                label="cerebro_self",
            )
            rendered = render_oracle_markdown(report)

            self.assertEqual(report.label, "cerebro_self")
            self.assertIn("# Context Vectors Oracle Eval — cerebro_self", rendered)
            self.assertIn("- all_cases_passed_at_3: true", rendered)
            self.assertIn("docs/operations/SYSTEM_STATE.md", rendered)

    def test_portal_oracle_cases_exercise_live_surfaces(self) -> None:
        expected = {case.expected_path for case in PORTAL_HUMAITA_ORACLE_CASES}

        self.assertIn("Entrada - Inicio do Projeto.md", expected)
        self.assertIn("00_PAINEL_VIGENTE/Status - Painel Vigente.md", expected)
        self.assertIn("01_TRABALHO_VIGENTE/03_RELATORIOS/CHECKLIST_PRE_PVA.md", expected)
        self.assertIn("01_TRABALHO_VIGENTE/03_RELATORIOS/CANON_OPERACIONAL_E_ORDEM_2026-04-06.md", expected)

    def test_escritorio_oracle_cases_exercise_office_surfaces(self) -> None:
        expected = {case.expected_path for case in ESCRITORIO_IRPF_CAIXA_RURAL_ORACLE_CASES}

        self.assertIn("README_ESTRUTURA_GERAL.md", expected)
        self.assertIn("ORIENTACAO_OFICIAL_ESTRUTURA_DOCUMENTAL.md", expected)
        self.assertIn("IRPF/README_SISTEMA.md", expected)

    def test_rejects_missing_root_and_invalid_limits(self) -> None:
        with self.assertRaises(ContextVectorError):
            build_vector_index("Z:/definitely/not/here")
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                build_vector_index(tmp_dir, max_files=0)
            index = build_vector_index(tmp_dir)
            with self.assertRaises(ValueError):
                query_index(index, "anything", limit=0)


if __name__ == "__main__":
    unittest.main()
