from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .datasets import file_sha256
from .datasets_v4 import load_doctrine_items, load_matter_tasks
from .validation_v4 import validate_doctrine_items, validate_matter_tasks


def _tree_commitment(root: Path) -> tuple[str, list[dict]]:
    inventory = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            inventory.append(
                {
                    "path": str(path.relative_to(root)),
                    "sha256": file_sha256(str(path)),
                    "bytes": path.stat().st_size,
                }
            )
    canonical = json.dumps(inventory, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest(), inventory


def build_release_manifest(
    doctrine_path: str | Path,
    matter_path: str | Path,
    *,
    official: bool,
) -> dict:
    doctrine_errors = validate_doctrine_items(doctrine_path, official=official)
    matter_errors = validate_matter_tasks(matter_path, official=official)
    if doctrine_errors or matter_errors:
        raise ValueError("\n".join(doctrine_errors + matter_errors))
    doctrine = load_doctrine_items(doctrine_path)
    matters = load_matter_tasks(matter_path)
    matter_root = Path(matter_path)
    matter_hash, inventory = _tree_commitment(matter_root)
    protocol_root = Path(__file__).resolve().parent
    protocol_files = [
        protocol_root / "models_v4.py",
        protocol_root / "scoring_v4.py",
        protocol_root / "statistics_v4.py",
        protocol_root / "validation_v4.py",
        protocol_root / "runner_v4.py",
    ]
    protocol_inventory = [
        {
            "path": path.name,
            "sha256": file_sha256(str(path)),
        }
        for path in protocol_files
    ]
    protocol_hash = hashlib.sha256(
        json.dumps(
            protocol_inventory, separators=(",", ":"), sort_keys=True
        ).encode()
    ).hexdigest()
    return {
        "schema_version": "4.0",
        "release_status": "official" if official else "development",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline_formula": {"doctrine": 0.5, "matter": 0.5},
        "doctrine": {
            "sha256": file_sha256(str(doctrine_path)),
            "count": len(doctrine),
            "family_count": len({item.family_id for item in doctrine}),
            "categories": dict(sorted(Counter(item.category for item in doctrine).items())),
            "review_statuses": dict(
                sorted(Counter(item.review.status for item in doctrine).items())
            ),
        },
        "matter": {
            "tree_sha256": matter_hash,
            "count": len(matters),
            "family_count": len({task.family_id for _, task in matters}),
            "task_types": dict(
                sorted(Counter(task.task_type for _, task in matters).items())
            ),
            "review_statuses": dict(
                sorted(Counter(task.review.status for _, task in matters).items())
            ),
            "inventory": inventory,
        },
        "protocol": {
            "sha256": protocol_hash,
            "files": protocol_inventory,
        },
        "authority_corpus": "fre-2025",
    }
