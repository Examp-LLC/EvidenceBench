from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models_v4 import DoctrineItem, MatterTask


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]


def load_doctrine_items(path: str | Path) -> list[DoctrineItem]:
    return [DoctrineItem.from_dict(item) for item in read_jsonl(path)]


def load_matter_task(path: str | Path) -> MatterTask:
    return MatterTask.from_dict(read_json(path))


def load_matter_tasks(path: str | Path) -> list[tuple[Path, MatterTask]]:
    root = Path(path)
    if root.is_file():
        return [(root.parent, load_matter_task(root))]
    return [
        (task_path.parent, load_matter_task(task_path))
        for task_path in sorted(root.glob("**/task.json"))
    ]
