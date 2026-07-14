from __future__ import annotations

import json
import os
import socket
import urllib.request
import urllib.error
from pathlib import Path

from .datasets import file_sha256, load_questions


PROMPT_VERSION = "evidencebench-v1-closed-book"


def prompt_for(question) -> str:
    options = "\n".join(f"{option['id']}. {option['text']}" for option in question.options)
    return f"""You are completing a closed-book Federal Rules of Evidence exercise.
Do not browse, use tools, or claim to have consulted external material.
Choose the best answer and cite only Federal Rules of Evidence provisions that
support the answer. Return JSON only in this exact shape:
{{"choice_id":"A","explanation":"brief explanation","citations":["FRE 801(c)"]}}

Question: {question.stem}

Options:
{options}
"""


def _post_json(url: str, headers: dict[str, str], body: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read())


def _openai_compatible(manifest: dict, prompt: str) -> tuple[dict, dict]:
    api_key = os.environ[manifest["api_key_env"]]
    payload = {
        "model": manifest["model_id"],
        "temperature": 0,
        "max_tokens": manifest.get("max_output_tokens", 800),
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }
    result = _post_json(manifest["base_url"], {"Authorization": f"Bearer {api_key}"}, payload)
    return json.loads(result["choices"][0]["message"]["content"]), result.get("usage", {})


def _anthropic_messages(manifest: dict, prompt: str) -> tuple[dict, dict]:
    api_key = os.environ[manifest["api_key_env"]]
    payload = {
        "model": manifest["model_id"],
        "max_tokens": manifest.get("max_output_tokens", 800),
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    result = _post_json(
        manifest["base_url"],
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        payload,
    )
    content = "".join(part.get("text", "") for part in result.get("content", []))
    return json.loads(content), result.get("usage", {})


def _gemini_generate_content(manifest: dict, prompt: str) -> tuple[dict, dict]:
    api_key = os.environ[manifest["api_key_env"]]
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": manifest.get("max_output_tokens", 800),
            "responseMimeType": "application/json",
        },
    }
    result = _post_json(manifest["base_url"], {"x-goog-api-key": api_key}, payload)
    content = "".join(
        part.get("text", "")
        for part in result["candidates"][0]["content"].get("parts", [])
    )
    return json.loads(content), result.get("usageMetadata", {})


ADAPTERS = {
    "openai_compatible": _openai_compatible,
    "anthropic_messages": _anthropic_messages,
    "gemini_generate_content": _gemini_generate_content,
}


def _is_transport_failure(error: Exception) -> bool:
    return isinstance(error, (urllib.error.URLError, TimeoutError, socket.timeout))


def run(manifest_path: str, questions_path: str, output_path: str) -> dict:
    manifest = json.loads(Path(manifest_path).read_text())
    questions = load_questions(questions_path)
    if manifest.get("tools_enabled"):
        raise ValueError("EvidenceBench closed-book runs must disable tools")
    adapter = ADAPTERS.get(manifest["adapter"])
    if not adapter:
        raise ValueError(f"unsupported adapter: {manifest['adapter']}")
    outputs = []
    for question in questions:
        for attempt in range(2):
            try:
                parsed, usage = adapter(manifest, prompt_for(question))
                # The benchmark owns the stable item ID.  A model must never
                # be able to replace it with an echoed or fabricated field.
                outputs.append({**parsed, "question_id": question.id, "status": "ok", "usage": usage})
                break
            except Exception as error:  # invalid outputs and refusals are scored failures
                if attempt == 0 and _is_transport_failure(error):
                    continue
                outputs.append({"question_id": question.id, "choice_id": None, "explanation": "", "citations": [], "status": f"failed:{type(error).__name__}"})
                break
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(json.dumps(item, sort_keys=True) for item in outputs) + "\n")
    return {
        "model": manifest["display_name"],
        "model_id": manifest["model_id"],
        "provider_route": manifest["provider_route"],
        "prompt_version": PROMPT_VERSION,
        "dataset_sha256": file_sha256(questions_path),
        "output_path": output_path,
    }
