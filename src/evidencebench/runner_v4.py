from __future__ import annotations

import json
import hashlib
import os
import re
import socket
import subprocess
import threading
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from xml.etree import ElementTree

from .datasets import file_sha256
from .datasets_v4 import load_doctrine_items, load_matter_tasks
from .models_v4 import MatterTask


DOCTRINE_PROMPT_VERSION = "evidencebench-v4-doctrine-2"
MATTER_PROMPT_VERSION = "evidencebench-v4-matter-agent-2"
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DOCTRINE_ISSUE_CATALOG = (
    (
        "EBV4_D01_JUDICIAL_ADMINISTRATION",
        "Judicial administration and preliminary questions",
    ),
    ("EBV4_D02_RELEVANCE_403", "Relevance and Rule 403 balancing"),
    (
        "EBV4_D03_CHARACTER_PROPENSITY_HABIT",
        "Character, propensity, other acts, or habit",
    ),
    ("EBV4_D04_POLICY_EXCLUSIONS", "Policy-based exclusions and compromise rules"),
    (
        "EBV4_D05_WITNESS_EXAMINATION",
        "Witness competency, examination, and sequestration",
    ),
    ("EBV4_D06_IMPEACHMENT_REHABILITATION", "Impeachment and rehabilitation"),
    ("EBV4_D07_OPINION_EXPERTS", "Lay or expert opinion evidence"),
    ("EBV4_D08_HEARSAY_DEFINITIONS", "Hearsay definitions and exclusions"),
    ("EBV4_D09_HEARSAY_EXCEPTIONS", "Hearsay exceptions"),
    (
        "EBV4_D10_AUTHENTICATION_IDENTIFICATION",
        "Authentication and identification",
    ),
    (
        "EBV4_D11_CONTENTS_ORIGINALS_SUMMARIES",
        "Original-writing rule, contents, and summaries",
    ),
    (
        "EBV4_D12_PRIVILEGE_CONSTITUTIONAL",
        "Privilege and constitutional evidence limits",
    ),
)


class CostBudgetExceeded(RuntimeError):
    pass


class RunCostBudget:
    def __init__(self, limit_usd: float | None) -> None:
        self.limit_usd = float(limit_usd) if limit_usd is not None else None
        self.spent_usd = 0.0
        self._lock = threading.Lock()

    def ensure_available(self) -> None:
        with self._lock:
            if self.limit_usd is not None and self.spent_usd >= self.limit_usd:
                raise CostBudgetExceeded(
                    f"run cost limit reached: ${self.spent_usd:.6f} "
                    f"of ${self.limit_usd:.2f}"
                )

    def record(self, result: dict) -> None:
        value = result.get("usage", {}).get("cost", 0)
        if isinstance(value, (int, float, str)):
            try:
                with self._lock:
                    self.spent_usd += float(value)
            except ValueError:
                pass


_JSONL_LOCK = threading.Lock()


def _read_jsonl_if_present(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _JSONL_LOCK:
        with path.open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def _load_ignored_env(start: Path) -> None:
    path = None
    for directory in (start, *start.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            path = candidate
            break
        if (directory / ".git").exists():
            break
    if path is None:
        return
    for line in path.read_text().splitlines():
        match = re.match(
            r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$",
            line,
        )
        if not match:
            continue
        name, value = match.groups()
        if value[:1] == value[-1:] and value[:1] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


def _post_openrouter(manifest: dict, payload: dict) -> dict:
    api_key_env = manifest.get("api_key_env", "OPENROUTER_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"missing required environment variable: {api_key_env}")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": manifest.get("app_title", "EvidenceBench v4"),
    }
    if manifest.get("http_referer"):
        headers["HTTP-Referer"] = manifest["http_referer"]
    request = urllib.request.Request(
        manifest.get("base_url", DEFAULT_OPENROUTER_URL),
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=manifest.get("timeout_seconds", 180)
        ) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        error.openrouter_body = error.read().decode(errors="replace")[:2000]
        raise


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, (urllib.error.URLError, TimeoutError, socket.timeout)):
        return True
    return isinstance(error, urllib.error.HTTPError) and error.code in {
        408,
        429,
        500,
        502,
        503,
        504,
    }


def _error_message(error: Exception) -> str:
    body = getattr(error, "openrouter_body", "")
    return f"{error}: {body}".strip()[:2000]


def _request(
    manifest: dict, payload: dict, budget: RunCostBudget | None = None
) -> dict:
    if budget is not None:
        budget.ensure_available()
    for attempt in range(2):
        try:
            result = _post_openrouter(manifest, payload)
            if budget is not None:
                budget.record(result)
            return result
        except Exception as error:
            if attempt == 0 and _is_retryable(error):
                continue
            raise
    raise AssertionError("unreachable")


def _generation_parameters(manifest: dict) -> dict:
    parameters: dict = {}
    if "temperature" not in manifest:
        parameters["temperature"] = 0
    elif manifest["temperature"] is not None:
        parameters["temperature"] = manifest["temperature"]
    for key in ("reasoning", "verbosity"):
        if key in manifest:
            parameters[key] = manifest[key]
    if "provider_route" in manifest:
        parameters["provider"] = manifest["provider_route"]
    seed = manifest.get("seed", 20260304)
    if seed is not None:
        parameters["seed"] = seed
    if "parallel_tool_calls" in manifest:
        parameters["parallel_tool_calls"] = manifest["parallel_tool_calls"]
    return parameters


def _json_content(message: dict) -> dict:
    content = message.get("content", "")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str):
        raise ValueError("model response content must be text")
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("model response must contain one JSON object")
    return parsed


def doctrine_prompt(item) -> str:
    facts = "\n".join(f"{fact.id}: {fact.text}" for fact in item.facts)
    rulings = ", ".join(item.allowed_rulings)
    issue_catalog = "\n".join(
        f"- {code}: {label}" for code, label in DOCTRINE_ISSUE_CATALOG
    )
    governing_law = (
        "the Federal Rules of Evidence"
        if item.jurisdiction == "federal"
        else f"the controlling evidence law of {item.jurisdiction.replace('_', ' ').title()}"
    )
    return f"""You are completing the EvidenceBench v4 Doctrine track.
This is closed-book. Do not browse or use tools. Apply {governing_law} and
return one JSON object only. Use only the supplied fact IDs.

Required shape:
{{"ruling":"admit|exclude|limit|defer","issue_codes":["EBV4_D..."],
"authorities":["controlling rule or case citation"],"grounding":[{{"issue_code":"EBV4_D...",
"fact_ids":["F1"]}}],"confidence":0.0,"explanation":"brief analysis"}}

Allowed rulings: {rulings}
Choose every materially controlling issue code from this fixed catalog:
{issue_catalog}
Question: {item.stem}
Facts:
{facts}
"""


def run_doctrine(
    manifest_path: str | Path,
    items_path: str | Path,
    output_path: str | Path,
) -> dict:
    manifest_path = Path(manifest_path)
    _load_ignored_env(manifest_path.resolve().parent)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("provider") != "openrouter":
        raise ValueError("v4 runner requires provider=openrouter")
    if manifest.get("tools_enabled"):
        raise ValueError("Doctrine track must disable tools")
    budget = RunCostBudget(manifest.get("max_run_cost_usd"))
    output = Path(output_path)
    prior_outputs = _read_jsonl_if_present(output)
    completed_ids = {
        record.get("item_id")
        for record in prior_outputs
        if record.get("item_id")
    }
    for record in prior_outputs:
        budget.record(record)
    pending_items = [
        item
        for item in load_doctrine_items(items_path)
        if item.id not in completed_ids
    ]

    def evaluate(item) -> dict:
        try:
            result = _request(
                manifest,
                {
                    "model": manifest["model_id"],
                    "max_tokens": manifest.get("max_output_tokens", 1200),
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": doctrine_prompt(item)}],
                    **_generation_parameters(manifest),
                },
                budget,
            )
            parsed = _json_content(result["choices"][0]["message"])
            return {
                **parsed,
                "item_id": item.id,
                "status": "ok",
                "usage": result.get("usage", {}),
                "generation_id": result.get("id"),
                "served_model": result.get("model"),
                "served_provider": result.get("provider"),
            }
        except Exception as error:
            return {
                "item_id": item.id,
                "ruling": None,
                "issue_codes": [],
                "authorities": [],
                "grounding": [],
                "confidence": None,
                "explanation": "",
                "status": f"failed:{type(error).__name__}",
                "error": _error_message(error),
            }
    workers = max(1, int(manifest.get("concurrency", 1)))
    new_count = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate, item) for item in pending_items]
        for future in as_completed(futures):
            _append_jsonl(output, future.result())
            new_count += 1
    return {
        "provider": "openrouter",
        "model": manifest["model_id"],
        "prompt_version": DOCTRINE_PROMPT_VERSION,
        "dataset_sha256": file_sha256(str(items_path)),
        "output_path": str(output),
        "items": len(completed_ids) + new_count,
        "resumed_items": len(completed_ids),
        "cost_usd": budget.spent_usd,
        "cost_limit_usd": budget.limit_usd,
    }


def _safe_path(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ValueError("absolute paths are not allowed")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("path escapes the workspace") from exc
    return candidate


def _extract_document(path: Path) -> str:
    if path.suffix.casefold() in {".txt", ".md", ".json", ".csv", ".tsv"}:
        return path.read_text(errors="replace")
    if path.suffix.casefold() == ".pdf":
        completed = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return completed.stdout
    if path.suffix.casefold() in {".docx", ".pptx", ".xlsx"}:
        chunks: list[str] = []
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if not name.endswith(".xml"):
                    continue
                try:
                    root = ElementTree.fromstring(archive.read(name))
                except ElementTree.ParseError:
                    continue
                text = " ".join(
                    node.text.strip()
                    for node in root.iter()
                    if node.text and node.text.strip()
                )
                if text:
                    chunks.append(f"[{name}]\n{text}")
        return "\n\n".join(chunks)
    raise ValueError(f"unsupported document format: {path.suffix}")


MATTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List matter documents available for review.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read a matter document by its relative path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_documents",
            "description": (
                "Read up to ten declared matter documents in one call. Prefer "
                "this when the task requires reviewing the complete record."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 10,
                        "items": {"type": "string"},
                    }
                },
                "required": ["paths"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search all text-extractable documents for a literal query.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_output",
            "description": "Write a UTF-8 output file. findings.json is mandatory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
]


class MatterWorkspace:
    def __init__(
        self,
        document_root: Path,
        output_root: Path,
        *,
        document_paths: list[str] | None = None,
        canonical_paths: dict[str, str] | None = None,
    ) -> None:
        self.document_root = document_root.resolve()
        self.output_root = output_root.resolve()
        self.document_paths = document_paths
        self.canonical_paths = canonical_paths or {}
        self.output_root.mkdir(parents=True, exist_ok=True)

    def execute(self, name: str, arguments: dict) -> dict:
        if name == "list_documents":
            if self.document_paths is not None:
                return {"documents": sorted(self.document_paths)}
            return {
                "documents": [
                    str(path.relative_to(self.document_root))
                    for path in sorted(self.document_root.rglob("*"))
                    if path.is_file()
                ]
            }
        if name == "read_document":
            requested = arguments["path"]
            if (
                self.document_paths is not None
                and requested not in self.document_paths
            ):
                raise ValueError("document is not declared by the task")
            path = _safe_path(self.document_root, requested)
            canonical_path = self.canonical_paths.get(requested)
            content = (
                _safe_path(self.document_root, canonical_path).read_text()
                if canonical_path
                else _extract_document(path)
            )
            return {"path": requested, "content": content}
        if name == "read_documents":
            paths = arguments.get("paths")
            if not isinstance(paths, list) or not 1 <= len(paths) <= 10:
                raise ValueError("paths must contain between one and ten documents")
            if len(paths) != len(set(paths)):
                raise ValueError("paths must not contain duplicates")
            return {
                "documents": [
                    self.execute("read_document", {"path": path})
                    for path in paths
                ]
            }
        if name == "search_documents":
            query = arguments["query"].casefold()
            matches = []
            for path in sorted(self.document_root.rglob("*")):
                if not path.is_file():
                    continue
                relative = str(path.relative_to(self.document_root))
                if self.document_paths is not None and relative not in self.document_paths:
                    continue
                try:
                    canonical_path = self.canonical_paths.get(relative)
                    text = (
                        _safe_path(self.document_root, canonical_path).read_text()
                        if canonical_path
                        else _extract_document(path)
                    )
                except (ValueError, OSError, subprocess.SubprocessError):
                    continue
                for number, line in enumerate(text.splitlines(), 1):
                    if query in line.casefold():
                        matches.append(
                            {
                                "path": str(path.relative_to(self.document_root)),
                                "line": number,
                                "text": line[:500],
                            }
                        )
                        if len(matches) == 100:
                            return {"matches": matches, "truncated": True}
            return {"matches": matches, "truncated": False}
        if name == "write_output":
            path = _safe_path(self.output_root, arguments["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"])
            return {"path": arguments["path"], "bytes": len(arguments["content"].encode())}
        raise ValueError(f"unknown tool: {name}")


def matter_prompt(task: MatterTask) -> str:
    deliverables = ", ".join(task.deliverables)
    documents = ", ".join(document.path for document in task.documents)
    issue_codes = ", ".join(
        finding.issue_code for finding in task.gold_findings
    )
    return f"""You are completing the EvidenceBench v4 Matter track in a
restricted workspace. Review the supplied record with the available tools.
Do not browse or assume facts not in the record.

Task: {task.title}
Instructions: {task.instructions}
Declared documents: {documents}
Required deliverables: {deliverables}
Required issue slots: {issue_codes}

You must write findings.json with this shape:
{{"findings":[{{"issue_code":"...","disposition":"...",
"fact_ids":["..."],"record_refs":["document:line-or-section"],
"authorities":["controlling rule or case citation"],"explanation":"..."}}]}}
Write exactly one finding for every required issue slot. The slot identifiers
are neutral output keys, not answers; determine each disposition, authority,
fact, and record reference from the matter.
Disposition must be exactly one of: admit, exclude, limit, defer.
Read every declared document. Prefer one read_documents call for the complete
record. Use write_output for every deliverable. When complete, respond briefly.
"""


def _run_matter_task(
    manifest: dict,
    task_dir: Path,
    task: MatterTask,
    output_root: Path,
    budget: RunCostBudget | None = None,
) -> tuple[dict, list[dict], dict]:
    workspace = MatterWorkspace(
        task_dir / "documents",
        output_root,
        document_paths=[document.path for document in task.documents],
        canonical_paths={
            document.path: document.canonical_text_path
            for document in task.documents
            if document.canonical_text_path
        },
    )
    messages: list[dict] = [{"role": "user", "content": matter_prompt(task)}]
    transcript: list[dict] = list(messages)
    total_usage: dict[str, int] = {}
    route_events: list[dict] = []
    for _ in range(manifest.get("max_turns", 20)):
        result = _request(
            manifest,
            {
                "model": manifest["model_id"],
                "max_tokens": manifest.get("max_output_tokens", 2000),
                "messages": messages,
                "tools": MATTER_TOOLS,
                **_generation_parameters(manifest),
            },
            budget,
        )
        route_events.append(
            {
                "generation_id": result.get("id"),
                "served_model": result.get("model"),
                "served_provider": result.get("provider"),
                "created": result.get("created"),
                "usage": result.get("usage", {}),
            }
        )
        for key, value in result.get("usage", {}).items():
            if isinstance(value, int):
                total_usage[key] = total_usage.get(key, 0) + value
        message = result["choices"][0]["message"]
        messages.append(message)
        transcript.append(message)
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            break
        for tool_call in tool_calls:
            function = tool_call["function"]
            try:
                arguments = json.loads(function.get("arguments", "{}"))
                payload = workspace.execute(function["name"], arguments)
            except Exception as error:
                payload = {"error": f"{type(error).__name__}: {error}"}
            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function["name"],
                "content": json.dumps(payload, sort_keys=True),
            }
            messages.append(tool_message)
            transcript.append(tool_message)

    findings_path = output_root / "findings.json"
    if not findings_path.is_file():
        raise ValueError("agent did not create findings.json")
    parsed = json.loads(findings_path.read_text())
    if not isinstance(parsed.get("findings"), list):
        raise ValueError("findings.json must contain a findings list")
    actual_deliverables = [
        str(path.relative_to(output_root))
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
    ]
    deliverable_metadata = []
    for relative in actual_deliverables:
        path = output_root / relative
        content = path.read_text(errors="replace")
        sections = []
        if path.suffix.casefold() == ".md":
            sections = [
                match.group(1).strip()
                for line in content.splitlines()
                if (match := re.match(r"^#{1,6}\s+(.+?)\s*$", line))
            ]
        elif path.suffix.casefold() == ".json":
            try:
                parsed_content = json.loads(content)
                if isinstance(parsed_content, dict):
                    sections = list(parsed_content)
            except json.JSONDecodeError:
                pass
        deliverable_metadata.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sections": sections,
            }
        )
    response = {
        "task_id": task.id,
        "findings": parsed["findings"],
        "deliverables": actual_deliverables,
        "deliverable_metadata": deliverable_metadata,
        "route_events": route_events,
        "status": "ok",
    }
    return response, transcript, total_usage


def run_matter(
    manifest_path: str | Path,
    tasks_path: str | Path,
    output_root: str | Path,
) -> dict:
    manifest_path = Path(manifest_path)
    _load_ignored_env(manifest_path.resolve().parent)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("provider") != "openrouter":
        raise ValueError("v4 runner requires provider=openrouter")
    if not manifest.get("tools_enabled"):
        raise ValueError("Matter track requires tools_enabled=true")
    destination = Path(output_root)
    destination.mkdir(parents=True, exist_ok=True)
    budget = RunCostBudget(manifest.get("max_run_cost_usd"))
    response_path = destination / "responses.jsonl"
    prior_records = _read_jsonl_if_present(response_path)
    completed_ids = {
        record.get("task_id")
        for record in prior_records
        if record.get("task_id")
    }
    for record in prior_records:
        for route_event in record.get("route_events", []):
            budget.record(route_event)
    pending_tasks = [
        (task_dir, task)
        for task_dir, task in load_matter_tasks(tasks_path)
        if task.id not in completed_ids
    ]

    def evaluate(entry) -> dict:
        task_dir, task = entry
        task_output = destination / "workspaces" / task.id
        if task_output.exists():
            interrupted_root = destination / "interrupted"
            interrupted_root.mkdir(parents=True, exist_ok=True)
            interrupted = interrupted_root / task.id
            suffix = 1
            while interrupted.exists():
                interrupted = interrupted_root / f"{task.id}-{suffix}"
                suffix += 1
            task_output.rename(interrupted)
        task_output.mkdir(parents=True)
        try:
            response, transcript, usage = _run_matter_task(
                manifest, task_dir, task, task_output, budget
            )
        except Exception as error:
            response = {
                "task_id": task.id,
                "findings": [],
                "deliverables": [],
                "status": f"failed:{type(error).__name__}",
                "error": _error_message(error),
            }
            transcript = []
            usage = {}
        (destination / f"{task.id}.transcript.json").write_text(
            json.dumps(
                {
                    "messages": transcript,
                    "usage": usage,
                    "route_events": response.get("route_events", []),
                },
                indent=2,
            )
            + "\n"
        )
        return response

    workers = max(1, int(manifest.get("concurrency", 1)))
    new_count = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate, entry) for entry in pending_tasks]
        for future in as_completed(futures):
            _append_jsonl(response_path, future.result())
            new_count += 1
    return {
        "provider": "openrouter",
        "model": manifest["model_id"],
        "prompt_version": MATTER_PROMPT_VERSION,
        "response_path": str(response_path),
        "tasks": len(completed_ids) + new_count,
        "resumed_tasks": len(completed_ids),
        "cost_usd": budget.spent_usd,
        "cost_limit_usd": budget.limit_usd,
    }
