from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evidencebench.datasets_v4 import load_doctrine_items, load_matter_tasks
from evidencebench.models_v4 import (
    DoctrineGrounding,
    DoctrineResponse,
    MatterFinding,
    MatterResponse,
)
from evidencebench.runner_v4 import MatterWorkspace
from evidencebench.release_v4 import build_release_manifest
from evidencebench.scoring_v4 import score_doctrine_item, score_matter_task
from evidencebench.statistics_v4 import summarize_suite
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


if __name__ == "__main__":
    unittest.main()
