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
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
