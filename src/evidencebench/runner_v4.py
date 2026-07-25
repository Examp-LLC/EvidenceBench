from __future__ import annotations

import json
import hashlib
import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .datasets import file_sha256
from .datasets_v4 import load_doctrine_items, load_matter_tasks
from .models_v4 import MatterTask


DOCTRINE_PROMPT_VERSION = "evidencebench-v4-doctrine-1"
MATTER_PROMPT_VERSION = "evidencebench-v4-matter-agent-1"
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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
    with urllib.request.urlopen(request, timeout=manifest.get("timeout_seconds", 180)) as response:
        return json.loads(response.read())


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


def _request(manifest: dict, payload: dict) -> dict:
    for attempt in range(2):
        try:
            return _post_openrouter(manifest, payload)
        except Exception as error:
            if attempt == 0 and _is_retryable(error):
                continue
            raise
    raise AssertionError("unreachable")


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
    governing_law = (
        "the Federal Rules of Evidence"
        if item.jurisdiction == "federal"
        else f"the controlling evidence law of {item.jurisdiction.replace('_', ' ').title()}"
    )
    return f"""You are completing the EvidenceBench v4 Doctrine track.
This is closed-book. Do not browse or use tools. Apply {governing_law} and
return one JSON object only. Use only the supplied fact IDs.

Required shape:
{{"ruling":"admit|exclude|limit|defer","issue_codes":["RULE_..."],
"authorities":["controlling rule or case citation"],"grounding":[{{"issue_code":"RULE_...",
"fact_ids":["F1"]}}],"confidence":0.0,"explanation":"brief analysis"}}

Allowed rulings: {rulings}
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
    outputs = []
    for item in load_doctrine_items(items_path):
        try:
            result = _request(
                manifest,
                {
                    "model": manifest["model_id"],
                    "temperature": 0,
                    "seed": manifest.get("seed", 20260304),
                    "max_tokens": manifest.get("max_output_tokens", 1200),
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": doctrine_prompt(item)}],
                },
            )
            parsed = _json_content(result["choices"][0]["message"])
            outputs.append(
                {
                    **parsed,
                    "item_id": item.id,
                    "status": "ok",
                    "usage": result.get("usage", {}),
                    "generation_id": result.get("id"),
                }
            )
        except Exception as error:
            outputs.append(
                {
                    "item_id": item.id,
                    "ruling": None,
                    "issue_codes": [],
                    "authorities": [],
                    "grounding": [],
                    "confidence": None,
                    "explanation": "",
                    "status": f"failed:{type(error).__name__}",
                }
            )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in outputs) + "\n"
    )
    return {
        "provider": "openrouter",
        "model": manifest["model_id"],
        "prompt_version": DOCTRINE_PROMPT_VERSION,
        "dataset_sha256": file_sha256(str(items_path)),
        "output_path": str(output),
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
    return f"""You are completing the EvidenceBench v4 Matter track in a
restricted workspace. Review the supplied record with the available tools.
Do not browse or assume facts not in the record.

Task: {task.title}
Instructions: {task.instructions}
Required deliverables: {deliverables}

You must write findings.json with this shape:
{{"findings":[{{"issue_code":"...","disposition":"...",
"fact_ids":["..."],"record_refs":["document:line-or-section"],
"authorities":["controlling rule or case citation"],"explanation":"..."}}]}}
Use write_output for every deliverable. When complete, respond briefly.
"""


def _run_matter_task(
    manifest: dict,
    task_dir: Path,
    task: MatterTask,
    output_root: Path,
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
    for _ in range(manifest.get("max_turns", 20)):
        result = _request(
            manifest,
            {
                "model": manifest["model_id"],
                "temperature": 0,
                "seed": manifest.get("seed", 20260304),
                "max_tokens": manifest.get("max_output_tokens", 2000),
                "messages": messages,
                "tools": MATTER_TOOLS,
                "parallel_tool_calls": False,
            },
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
    records = []
    for task_dir, task in load_matter_tasks(tasks_path):
        task_output = destination / "workspaces" / task.id
        if task_output.exists():
            raise FileExistsError(
                f"refusing to overwrite prior task workspace: {task_output}"
            )
        task_output.mkdir(parents=True)
        try:
            response, transcript, usage = _run_matter_task(
                manifest, task_dir, task, task_output
            )
        except Exception as error:
            response = {
                "task_id": task.id,
                "findings": [],
                "deliverables": [],
                "status": f"failed:{type(error).__name__}",
            }
            transcript = []
            usage = {}
        records.append(response)
        (destination / f"{task.id}.transcript.json").write_text(
            json.dumps({"messages": transcript, "usage": usage}, indent=2) + "\n"
        )
    response_path = destination / "responses.jsonl"
    response_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n"
    )
    return {
        "provider": "openrouter",
        "model": manifest["model_id"],
        "prompt_version": MATTER_PROMPT_VERSION,
        "response_path": str(response_path),
        "tasks": len(records),
    }
