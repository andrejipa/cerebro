from __future__ import annotations

import json
import unittest

from core.domain_input_adapter import DomainInputAdapterError, DomainInputAmbiguityError, adapt_domain_input


class DomainInputAdapterTests(unittest.TestCase):
    def test_adapt_simple_comma_list(self) -> None:
        adapted = adapt_domain_input("comprar arroz, leite, pao", input_kind="list")

        self.assertEqual(adapted["input_kind"], "list")
        self.assertEqual(adapted["goal"], "Complete listed items")
        self.assertEqual([task["title"] for task in adapted["tasks"]], ["comprar arroz", "leite", "pao"])
        self.assertEqual(adapted["verify_commands"], [])

    def test_adapt_single_task(self) -> None:
        adapted = adapt_domain_input("Revisar agenda semanal")

        self.assertEqual(adapted["input_kind"], "task")
        self.assertEqual(adapted["goal"], "Revisar agenda semanal")
        self.assertEqual(len(adapted["tasks"]), 1)
        self.assertEqual(adapted["tasks"][0]["id"], "task-001")

    def test_adapt_single_bullet_as_single_task_without_marker(self) -> None:
        adapted = adapt_domain_input("- Comprar arroz", input_kind="task")

        self.assertEqual(adapted["input_kind"], "task")
        self.assertEqual(adapted["goal"], "Comprar arroz")
        self.assertEqual(adapted["tasks"][0]["title"], "Comprar arroz")

    def test_adapt_structured_plan(self) -> None:
        adapted = adapt_domain_input(
            "\n".join(
                [
                    "goal: Corrigir runtime",
                    "summary: Patch governado",
                    "verify: python -m unittest discover -s tests -v",
                    "- Atualizar exporter | id=task-edit | working_set=extensions/status_export/exporter.py | acceptance=tests verdes",
                    "- Rodar validacao | depends=task-edit | acceptance=saida revisada",
                ]
            )
        )

        self.assertEqual(adapted["input_kind"], "structured")
        self.assertEqual(adapted["goal"], "Corrigir runtime")
        self.assertEqual(adapted["summary"], "Patch governado")
        self.assertEqual(adapted["verify_commands"], ["python -m unittest discover -s tests -v"])
        self.assertEqual(adapted["tasks"][0]["id"], "task-edit")
        self.assertEqual(adapted["tasks"][0]["working_set"], ["extensions/status_export/exporter.py"])
        self.assertEqual(adapted["tasks"][1]["depends_on"], ["task-edit"])

    def test_auto_rejects_ambiguous_multi_item_polite_prose(self) -> None:
        with self.assertRaises(DomainInputAdapterError):
            adapt_domain_input("organiza isso, por favor")

    def test_auto_reports_ambiguity_for_comma_separated_items(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("comprar arroz, leite, pao")

        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["list", "task"],
        )

    def test_auto_reports_ambiguity_for_single_bullet(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("- Comprar arroz")

        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "list"],
        )

    def test_auto_keeps_pipe_note_as_plain_list_item_when_not_metadata(self) -> None:
        adapted = adapt_domain_input("- Revisar agenda | se der hoje\n- Pagar contas")

        self.assertEqual(adapted["input_kind"], "list")
        self.assertEqual(
            [task["title"] for task in adapted["tasks"]],
            ["Revisar agenda | se der hoje", "Pagar contas"],
        )

    def test_rejects_vague_single_task_input(self) -> None:
        with self.assertRaises(DomainInputAdapterError):
            adapt_domain_input("organiza isso")

    def test_rejects_vague_single_task_input_with_trailing_punctuation(self) -> None:
        with self.assertRaises(DomainInputAdapterError):
            adapt_domain_input("organiza isso.")

    def test_rejects_malformed_structured_input(self) -> None:
        with self.assertRaises(DomainInputAdapterError):
            adapt_domain_input(
                "\n".join(
                    [
                        "goal: Primeiro objetivo",
                        "goal: Objetivo duplicado",
                        "- Tarefa 1",
                    ]
                ),
                input_kind="structured",
            )

    def test_rejects_structured_vague_task_title(self) -> None:
        with self.assertRaises(DomainInputAdapterError):
            adapt_domain_input("task: organiza isso", input_kind="structured")

    def test_auto_reports_ambiguity_for_inline_metadata_task(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("Comprar arroz | acceptance=feito")

        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["structured", "task"],
        )

    def test_auto_reports_ambiguity_for_mixed_bullet_metadata_list(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("- Task A | id=alpha\n- Task B")

        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["list", "structured"],
        )

    def test_auto_reports_ambiguity_for_compound_instruction(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("review and merge")

        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "rewrite-as-list"],
        )

    def test_auto_reports_ambiguity_for_long_compound_instruction(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("review the code and merge after final manual signoff")

        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "rewrite-as-list"],
        )

    def test_auto_reports_semantic_ambiguity_for_broad_organizational_input(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("organizar semana")

        self.assertEqual(context.exception.ambiguity_type, "semantic")
        self.assertEqual(context.exception.ambiguity_level, "high")
        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "list", "structured"],
        )

    def test_auto_reports_semantic_ambiguity_for_broad_review_input(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("revisar projeto")

        self.assertEqual(context.exception.ambiguity_type, "semantic")
        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "list", "structured"],
        )

    def test_auto_reports_semantic_ambiguity_for_broad_month_closing_input(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("preparar fechamento do mes")

        self.assertEqual(context.exception.ambiguity_type, "semantic")
        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "list", "structured"],
        )

    def test_auto_reports_semantic_ambiguity_for_qualified_trip_planning_input(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("planejar viagem internacional")

        self.assertEqual(context.exception.ambiguity_type, "semantic")
        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "list", "structured"],
        )

    def test_auto_reports_semantic_ambiguity_for_qualified_backlog_input(self) -> None:
        with self.assertRaises(DomainInputAmbiguityError) as context:
            adapt_domain_input("arrumar backlog urgente")

        self.assertEqual(context.exception.ambiguity_type, "semantic")
        self.assertEqual(
            [item["kind"] for item in context.exception.interpretations],
            ["task", "list", "structured"],
        )

    def test_auto_keeps_specific_technical_task_without_semantic_block(self) -> None:
        adapted = adapt_domain_input("Revisar parser runtime")

        self.assertEqual(adapted["input_kind"], "task")
        self.assertEqual(adapted["tasks"][0]["title"], "Revisar parser runtime")

    def test_rejects_structured_verify_without_governed_working_set(self) -> None:
        with self.assertRaises(DomainInputAdapterError):
            adapt_domain_input(
                "\n".join(
                    [
                        "goal: compras",
                        "verify: python -m unittest",
                        "- comprar arroz",
                        "- comprar leite",
                    ]
                ),
                input_kind="structured",
            )

    def test_adaptation_is_deterministic(self) -> None:
        raw = "- Ler capitulo 1\n- Resolver exercicios"
        first = adapt_domain_input(raw, input_kind="list")
        second = adapt_domain_input(raw, input_kind="list")

        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )
