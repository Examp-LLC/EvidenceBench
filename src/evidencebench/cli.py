from __future__ import annotations

import argparse
import json
from pathlib import Path

from .datasets import load_questions, read_jsonl
from .exporters import export_web
from .models import ModelResponse
from .runner import run
from .scoring import aggregate, score_item
from .validation import validate_questions
from .datasets_v4 import load_doctrine_items, load_matter_tasks, read_jsonl as read_jsonl_v4
from .models_v4 import (
    DoctrineItemScore,
    DoctrineResponse,
    MatterResponse,
    MatterTaskScore,
)
from .runner_v4 import run_doctrine, run_matter
from .release_v4 import build_release_manifest
from .scoring_v4 import score_as_dict, score_doctrine_item, score_matter_task
from .statistics_v4 import summarize_doctrine, summarize_matter, summarize_suite
from .validation_v4 import (
    audit_doctrine_overlap,
    validate_doctrine_items,
    validate_matter_tasks,
)


def _validate(args: argparse.Namespace) -> int:
    errors = validate_questions(args.questions)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"valid: {args.questions}")
    return 0


def _score(args: argparse.Namespace) -> int:
    questions = load_questions(args.questions)
    responses = {item["question_id"]: ModelResponse.from_dict(item) for item in read_jsonl(args.responses)}
    scores = [score_item(question, responses.get(question.id, ModelResponse(question.id, None, "", [], "missing"))) for question in questions]
    result = aggregate(scores, questions)
    result["items"] = [score.__dict__ for score in scores]
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered)
    else:
        print(rendered, end="")
    return 0


def _run(args: argparse.Namespace) -> int:
    print(json.dumps(run(args.manifest, args.questions, args.output), indent=2))
    return 0


def _export(args: argparse.Namespace) -> int:
    export_web(args.manifest, args.output)
    print(f"exported: {args.output}")
    return 0


def _write_or_print(payload: dict, output: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(rendered)
    else:
        print(rendered, end="")


def _validate_v4(args: argparse.Namespace) -> int:
    if args.track == "doctrine":
        errors = validate_doctrine_items(
            args.input, official=args.official, candidate=args.candidate
        )
    else:
        errors = validate_matter_tasks(
            args.input, official=args.official, candidate=args.candidate
        )
    if errors:
        print("\n".join(errors))
        return 1
    print(f"valid v4 {args.track}: {args.input}")
    return 0


def _score_v4(args: argparse.Namespace) -> int:
    responses = read_jsonl_v4(args.responses)
    if args.track == "doctrine":
        items = load_doctrine_items(args.input)
        by_id = {
            record["item_id"]: DoctrineResponse.from_dict(record)
            for record in responses
        }
        scores = [
            score_doctrine_item(
                item,
                by_id.get(
                    item.id,
                    DoctrineResponse(item.id, None, [], [], [], None, "missing"),
                ),
            )
            for item in items
        ]
        summary = summarize_doctrine(scores)
    else:
        entries = load_matter_tasks(args.input)
        by_id = {
            record["task_id"]: MatterResponse.from_dict(record)
            for record in responses
        }
        scores = [
            score_matter_task(
                task,
                by_id.get(task.id, MatterResponse(task.id, [], [], "missing")),
            )
            for _, task in entries
        ]
        summary = summarize_matter(scores)
    _write_or_print(
        {
            "schema_version": "4.0",
            "track": args.track,
            "summary": summary,
            "items": [score_as_dict(score) for score in scores],
        },
        args.output,
    )
    return 0


def _load_score_file(path: str, cls):
    payload = json.loads(Path(path).read_text())
    return [cls(**record) for record in payload["items"]]


def _summarize_v4(args: argparse.Namespace) -> int:
    doctrine = _load_score_file(args.doctrine_scores, DoctrineItemScore)
    matter_records = json.loads(Path(args.matter_scores).read_text())["items"]
    matter = [
        MatterTaskScore(
            **{
                **record,
                "criteria": record["criteria"],
            }
        )
        for record in matter_records
    ]
    _write_or_print(summarize_suite(doctrine, matter), args.output)
    return 0


def _run_v4_doctrine(args: argparse.Namespace) -> int:
    _write_or_print(
        run_doctrine(args.manifest, args.items, args.output),
        None,
    )
    return 0


def _run_v4_matter(args: argparse.Namespace) -> int:
    _write_or_print(
        run_matter(args.manifest, args.tasks, args.output),
        None,
    )
    return 0


def _audit_v4(args: argparse.Namespace) -> int:
    findings = audit_doctrine_overlap(args.public, args.holdout)
    if findings:
        print("\n".join(findings))
        return 1
    print("no exact stem or family overlap detected")
    return 0


def _manifest_v4(args: argparse.Namespace) -> int:
    try:
        manifest = build_release_manifest(
            args.doctrine,
            args.matter,
            official=args.official,
        )
    except ValueError as error:
        print(error)
        return 1
    _write_or_print(manifest, args.output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="evidencebench")
    subparsers = parser.add_subparsers(required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("questions")
    validate.set_defaults(handler=_validate)
    score = subparsers.add_parser("score")
    score.add_argument("--questions", required=True)
    score.add_argument("--responses", required=True)
    score.add_argument("--output")
    score.set_defaults(handler=_score)
    run_command = subparsers.add_parser("run")
    run_command.add_argument("--manifest", required=True)
    run_command.add_argument("--questions", required=True)
    run_command.add_argument("--output", required=True)
    run_command.set_defaults(handler=_run)
    export = subparsers.add_parser("export-web")
    export.add_argument("--manifest", required=True)
    export.add_argument("--output", required=True)
    export.set_defaults(handler=_export)
    validate_v4 = subparsers.add_parser("validate-v4")
    validate_v4.add_argument("--track", choices=("doctrine", "matter"), required=True)
    validate_v4.add_argument("--input", required=True)
    validate_v4.add_argument("--official", action="store_true")
    validate_v4.add_argument("--candidate", action="store_true")
    validate_v4.set_defaults(handler=_validate_v4)
    score_v4 = subparsers.add_parser("score-v4")
    score_v4.add_argument("--track", choices=("doctrine", "matter"), required=True)
    score_v4.add_argument("--input", required=True)
    score_v4.add_argument("--responses", required=True)
    score_v4.add_argument("--output")
    score_v4.set_defaults(handler=_score_v4)
    summarize_v4 = subparsers.add_parser("summarize-v4")
    summarize_v4.add_argument("--doctrine-scores", required=True)
    summarize_v4.add_argument("--matter-scores", required=True)
    summarize_v4.add_argument("--output")
    summarize_v4.set_defaults(handler=_summarize_v4)
    run_v4_doctrine = subparsers.add_parser("run-v4-doctrine")
    run_v4_doctrine.add_argument("--manifest", required=True)
    run_v4_doctrine.add_argument("--items", required=True)
    run_v4_doctrine.add_argument("--output", required=True)
    run_v4_doctrine.set_defaults(handler=_run_v4_doctrine)
    run_v4_matter = subparsers.add_parser("run-v4-matter")
    run_v4_matter.add_argument("--manifest", required=True)
    run_v4_matter.add_argument("--tasks", required=True)
    run_v4_matter.add_argument("--output", required=True)
    run_v4_matter.set_defaults(handler=_run_v4_matter)
    audit_v4 = subparsers.add_parser("audit-v4")
    audit_v4.add_argument("--public", required=True)
    audit_v4.add_argument("--holdout", required=True)
    audit_v4.set_defaults(handler=_audit_v4)
    manifest_v4 = subparsers.add_parser("manifest-v4")
    manifest_v4.add_argument("--doctrine", required=True)
    manifest_v4.add_argument("--matter", required=True)
    manifest_v4.add_argument("--output")
    manifest_v4.add_argument("--official", action="store_true")
    manifest_v4.set_defaults(handler=_manifest_v4)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
