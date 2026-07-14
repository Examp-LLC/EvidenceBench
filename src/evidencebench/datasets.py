from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Question


def read_jsonl(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def load_questions(path: str | Path) -> list[Question]:
    return [Question.from_dict(item) for item in read_jsonl(path)]


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
