from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidencebench.datasets_v4 import load_doctrine_items, load_matter_tasks
from evidencebench.models_v4 import (
    DoctrineItemScore,
    DoctrineGrounding,
    DoctrineResponse,
    MatterDeliverableMetadata,
    MatterFinding,
    MatterResponse,
    MatterTask,
)
from evidencebench.runner_v4 import (
    CostBudgetExceeded,
    MatterWorkspace,
    RunCostBudget,
    _generation_parameters,
    doctrine_prompt,
    run_doctrine,
)
from evidencebench.release_v4 import build_release_manifest
from evidencebench.scoring_v4 import score_doctrine_item, score_matter_task
from evidencebench.statistics_v4 import summarize_doctrine, summarize_suite
from evidencebench.validation_v4 import (
    validate_doctrine_items,
    validate_matter_tasks,
)


ROOT = Path(__file__).resolve().parents[1]
DOCTRINE = ROOT / "data" / "v4" / "dev" / "doctrine.jsonl"
MATTER = ROOT / "data" / "v4" / "dev" / "matter"


class V4ValidationTests(unittest.TestCase):
    def test_development_data_validates(self) -> None:
        self.assertEqual(validate_doctrine_items(DOCTRINE), [])
        self.assertEqual(validate_matter_tasks(MATTER), [])

    def test_draft_data_cannot_be_official(self) -> None:
        doctrine_errors = validate_doctrine_items(DOCTRINE, official=True)
        matter_errors = validate_matter_tasks(MATTER, official=True)
        self.assertTrue(any("must be APPROVED" in item for item in doctrine_errors))
        self.assertTrue(any("must be APPROVED" in item for item in matter_errors))

    def test_development_manifest_commits_to_data_and_protocol(self) -> None:
        manifest = build_release_manifest(DOCTRINE, MATTER, official=False)
        self.assertEqual(manifest["release_status"], "development")
        self.assertEqual(manifest["doctrine"]["count"], 8)
        self.assertEqual(manifest["matter"]["count"], 2)
        self.assertEqual(len(manifest["protocol"]["sha256"]), 64)
        with self.assertRaises(ValueError):
            build_release_manifest(DOCTRINE, MATTER, official=True)


class V4ScoringTests(unittest.TestCase):
    def test_perfect_doctrine_response_scores_one(self) -> None:
        item = load_doctrine_items(DOCTRINE)[3]
        response = DoctrineResponse(
            item_id=item.id,
            ruling="exclude",
            issue_codes=["FRE_602_PERSONAL_KNOWLEDGE"],
            authorities=["FRE 602"],
            grounding=[
                DoctrineGrounding(
                    "FRE_602_PERSONAL_KNOWLEDGE", ["F1", "F2", "F3"]
                )
            ],
            confidence=1.0,
        )
        score = score_doctrine_item(item, response)
        self.assertEqual(score.doctrine_score, 1.0)
        self.assertEqual(score.invalid_authorities, [])

    def test_invalid_authority_is_not_silently_dropped(self) -> None:
        item = load_doctrine_items(DOCTRINE)[3]
        response = DoctrineResponse(
            item_id=item.id,
            ruling="exclude",
            issue_codes=["FRE_602_PERSONAL_KNOWLEDGE"],
            authorities=["FRE 602", "Rule banana"],
            grounding=[
                DoctrineGrounding(
                    "FRE_602_PERSONAL_KNOWLEDGE", ["F1", "F2", "F3"]
                )
            ],
            confidence=1.0,
        )
        score = score_doctrine_item(item, response)
        self.assertEqual(score.invalid_authorities, ["Rule banana"])
        self.assertEqual(score.authority_precision, 0.5)
        self.assertLess(score.doctrine_score, 1.0)

    def test_perfect_matter_response_scores_one(self) -> None:
        _, task = load_matter_tasks(MATTER)[0]
        response = MatterResponse(
            task_id=task.id,
            findings=[
                MatterFinding(
                    issue_code="FRE_901_DISTINCTIVE_CHARACTERISTICS",
                    disposition="sufficient",
                    fact_ids=["F2", "F3", "F4"],
                    record_refs=["record.txt"],
                    authorities=["FRE 901(a)", "FRE 901(b)(4)"],
                )
            ],
            deliverables=["findings.json"],
        )
        score = score_matter_task(task, response)
        self.assertEqual(score.matter_score, 1.0)
        self.assertTrue(score.complete_task)

    def test_suite_has_one_overall_score_and_sensitivity(self) -> None:
        doctrine_item = load_doctrine_items(DOCTRINE)[3]
        doctrine = score_doctrine_item(
            doctrine_item,
            DoctrineResponse(
                doctrine_item.id,
                "exclude",
                ["FRE_602_PERSONAL_KNOWLEDGE"],
                ["FRE 602"],
                [
                    DoctrineGrounding(
                        "FRE_602_PERSONAL_KNOWLEDGE", ["F1", "F2", "F3"]
                    )
                ],
                1.0,
            ),
        )
        _, matter_task = load_matter_tasks(MATTER)[0]
        matter = score_matter_task(
            matter_task,
            MatterResponse(
                matter_task.id,
                [
                    MatterFinding(
                        "FRE_901_DISTINCTIVE_CHARACTERISTICS",
                        "sufficient",
                        ["F2", "F3", "F4"],
                        ["record.txt"],
                        ["FRE 901(a)", "FRE 901(b)(4)"],
                    )
                ],
                ["findings.json"],
            ),
        )
        summary = summarize_suite([doctrine], [matter])
        self.assertEqual(summary["overall_score"], 1.0)
        self.assertEqual(summary["overall_score_100"], 100.0)
        self.assertIn("doctrine_40_matter_60", summary["weight_sensitivity"])

    def test_extra_matter_findings_reduce_precision(self) -> None:
        task = MatterTask.from_dict(
            {
                "schema_version": "4.0",
                "track": "matter",
                "id": "M-PRECISION",
                "family_id": "M-PRECISION",
                "domain": "D10_AUTHENTICATION_IDENTIFICATION",
                "jurisdiction": "federal",
                "title": "Precision test",
                "task_type": "admissibility_memo",
                "instructions": "Resolve the record.",
                "documents": [{"path": "record.txt", "sha256": "0" * 64}],
                "deliverables": ["findings.json"],
                "criteria": [
                    {
                        "id": "L1",
                        "dimension": "legal",
                        "title": "Correct result",
                        "issue_code": "AUTH",
                        "expected_disposition": "admit",
                    },
                    {
                        "id": "A1",
                        "dimension": "authority",
                        "title": "Correct authority",
                        "issue_code": "AUTH",
                        "required_authority_groups": [["FRE 901(a)"]],
                        "accepted_authorities": ["FRE 901(a)"],
                    },
                    {
                        "id": "F1",
                        "dimension": "fact",
                        "title": "Correct fact and record",
                        "issue_code": "AUTH",
                        "required_fact_ids": ["F1"],
                        "required_record_refs": ["record.txt"],
                    },
                    {
                        "id": "D1",
                        "dimension": "deliverable",
                        "title": "Structured findings",
                        "deliverable": "findings.json",
                        "min_bytes": 10,
                        "required_sections": ["findings"],
                    },
                ],
                "gold_findings": [
                    {
                        "issue_code": "AUTH",
                        "accepted_dispositions": ["admit"],
                        "required_fact_ids": ["F1"],
                        "accepted_fact_ids": ["F1"],
                        "required_record_refs": ["record.txt"],
                        "accepted_record_refs": ["record.txt"],
                        "required_authority_groups": [["FRE 901(a)"]],
                        "accepted_authorities": ["FRE 901(a)"],
                    }
                ],
                "corpus_version": "test",
                "review": {"status": "DRAFT"},
                "coverage_cell": "test",
            }
        )
        response = MatterResponse(
            task_id=task.id,
            findings=[
                MatterFinding(
                    "AUTH",
                    "admit",
                    ["F1"],
                    ["record.txt"],
                    ["FRE 901(a)"],
                ),
                MatterFinding(
                    "UNSUPPORTED",
                    "exclude",
                    ["F99"],
                    ["other.txt"],
                    ["FRE 403"],
                ),
            ],
            deliverables=["findings.json"],
            deliverable_metadata=[
                MatterDeliverableMetadata(
                    path="findings.json",
                    bytes=100,
                    sha256="0" * 64,
                    sections=["findings"],
                )
            ],
        )
        score = score_matter_task(task, response)
        self.assertAlmostEqual(score.legal_precision, 0.5)
        self.assertAlmostEqual(score.authority_precision, 0.5)
        self.assertAlmostEqual(score.factual_precision, 0.5)
        self.assertAlmostEqual(score.legal_recall, 1.0)
        self.assertFalse(score.complete_task)

    def test_doctrine_uses_family_first_domain_macro_average(self) -> None:
        def record(item: str, family: str, domain: str, value: float) -> DoctrineItemScore:
            return DoctrineItemScore(
                item_id=item,
                family_id=family,
                domain=domain,
                outcome_accuracy=value,
                issue_precision=value,
                issue_recall=value,
                issue_f1=value,
                authority_precision=value,
                authority_recall=value,
                authority_f1=value,
                grounding_precision=value,
                grounding_recall=value,
                grounding_f1=value,
                calibration=value,
                invalid_authorities=[],
                hallucinated_authorities=[],
                unsupported_authorities=[],
                doctrine_score=value,
                status="ok",
            )

        summary = summarize_doctrine(
            [
                record("A1", "F1", "D01", 1.0),
                record("A2", "F1", "D01", 0.0),
                record("A3", "F2", "D01", 1.0),
                record("B1", "F3", "D02", 0.0),
            ]
        )
        self.assertEqual(summary["item_mean_score"], 0.5)
        self.assertEqual(summary["family_mean_score"], 0.5)
        self.assertEqual(summary["doctrine_score"], 0.375)


class MatterWorkspaceTests(unittest.TestCase):
    def test_workspace_separates_read_and_write_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            documents = root / "documents"
            outputs = root / "outputs"
            documents.mkdir()
            (documents / "record.txt").write_text("needle")
            workspace = MatterWorkspace(documents, outputs)
            result = workspace.execute("search_documents", {"query": "needle"})
            self.assertEqual(result["matches"][0]["path"], "record.txt")
            workspace.execute(
                "write_output",
                {"path": "findings.json", "content": '{"findings":[]}'},
            )
            self.assertTrue((outputs / "findings.json").is_file())
            with self.assertRaises(ValueError):
                workspace.execute(
                    "write_output", {"path": "../escape.txt", "content": "no"}
                )

    def test_workspace_exposes_canonical_text_only_through_declared_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            documents = root / "documents"
            outputs = root / "outputs"
            canonical = documents / "_canonical"
            canonical.mkdir(parents=True)
            (documents / "record.docx").write_bytes(b"not used")
            (canonical / "record.txt").write_text("canonical needle")
            workspace = MatterWorkspace(
                documents,
                outputs,
                document_paths=["record.docx"],
                canonical_paths={"record.docx": "_canonical/record.txt"},
            )
            self.assertEqual(
                workspace.execute("list_documents", {})["documents"],
                ["record.docx"],
            )
            self.assertEqual(
                workspace.execute(
                    "read_document", {"path": "record.docx"}
                )["content"],
                "canonical needle",
            )
            self.assertEqual(
                workspace.execute(
                    "read_documents", {"paths": ["record.docx"]}
                )["documents"][0]["content"],
                "canonical needle",
            )
            with self.assertRaises(ValueError):
                workspace.execute(
                    "read_document", {"path": "_canonical/record.txt"}
                )


class PromptTests(unittest.TestCase):
    def test_state_doctrine_prompt_uses_state_law(self) -> None:
        item = load_doctrine_items(DOCTRINE)[0]
        state_item = item.__class__.from_dict(
            {
                **item.to_dict(),
                "jurisdiction": "california",
            }
        )
        prompt = doctrine_prompt(state_item)
        self.assertIn("controlling evidence law of California", prompt)
        self.assertNotIn("Apply the Federal Rules of Evidence", prompt)

    def test_generation_parameters_support_reasoning_without_temperature(self) -> None:
        self.assertEqual(
            _generation_parameters({}),
            {"temperature": 0, "seed": 20260304},
        )
        self.assertEqual(
            _generation_parameters(
                {
                    "temperature": None,
                    "reasoning": {"effort": "high"},
                    "provider_route": {"allow_fallbacks": False},
                }
            ),
            {
                "seed": 20260304,
                "reasoning": {"effort": "high"},
                "provider": {"allow_fallbacks": False},
            },
        )

    def test_cost_budget_uses_openrouter_reported_cost(self) -> None:
        budget = RunCostBudget(1.0)
        budget.record({"usage": {"cost": 0.4}})
        budget.ensure_available()
        budget.record({"usage": {"cost": "0.6"}})
        with self.assertRaises(CostBudgetExceeded):
            budget.ensure_available()

    def test_doctrine_run_resumes_without_repeating_paid_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            items = root / "items.jsonl"
            output = root / "responses.jsonl"
            manifest.write_text(
                json.dumps(
                    {
                        "provider": "openrouter",
                        "model_id": "test/model",
                        "tools_enabled": False,
                        "max_run_cost_usd": 1,
                    }
                )
            )
            items.write_text(DOCTRINE.read_text().splitlines()[0] + "\n")
            response = {
                "id": "generation-1",
                "model": "test/model",
                "provider": "Test",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "ruling": "exclude",
                                    "issue_codes": [],
                                    "authorities": [],
                                    "grounding": [],
                                    "confidence": 0.5,
                                    "explanation": "test",
                                }
                            )
                        }
                    }
                ],
                "usage": {"cost": 0.01},
            }
            with patch(
                "evidencebench.runner_v4._request", return_value=response
            ) as request:
                first = run_doctrine(manifest, items, output)
                second = run_doctrine(manifest, items, output)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(first["items"], 1)
            self.assertEqual(second["resumed_items"], 1)
            self.assertEqual(len(output.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
