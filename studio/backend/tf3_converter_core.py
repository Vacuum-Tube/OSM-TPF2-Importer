from __future__ import annotations

import json
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModDescriptor:
    name: str = "Unnamed Mod"
    summary: str = ""
    description: str = ""
    authors: list[dict[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    url: str = ""
    mod_id: str = ""
    revision: int = 1
    dependencies: list | None = None
    incompatibilities: list | None = None
    params: list | None = None
    options: list | None = None
    severity_add: str = "None"
    severity_remove: str = "None"
    pre_run_script: str | None = None
    run_script: str | None = None
    post_run_script: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def target_mod_id(self) -> str:
        return self.mod_id or self._slugify_name(self.name)

    @staticmethod
    def _slugify_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name.strip())
        cleaned = cleaned.strip("_").lower()
        if not cleaned:
            return "converted_mod"
        return cleaned

    def as_mod_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "dependencies": self.dependencies,
            "incompatibilities": self.incompatibilities,
            "modId": self.target_mod_id,
            "options": self.options,
            "params": self.params,
            "revision": int(self.revision),
            "severityAdd": self.severity_add,
            "severityRemove": self.severity_remove,
        }
        if self.pre_run_script:
            payload["preRunScript"] = {"fileName": self.pre_run_script}
        if self.run_script:
            payload["runScript"] = {"fileName": self.run_script}
        if self.post_run_script:
            payload["postRunScript"] = {"fileName": self.post_run_script}
        return payload

    def as_modinfo_json(self) -> dict[str, Any]:
        authors = deepcopy(self.authors)
        if not authors and self.name:
            authors = [{"name": self.name, "role": "CREATOR"}]
        payload = {
            "authors": authors,
            "description": self.description or self.summary,
            "name": self.name,
            "summary": self.summary or self.description,
            "tags": self.tags,
            "url": self.url,
        }
        return payload


def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file {path} does not contain an object")
    return payload


def _strip_lua_comments(text: str) -> str:
    result: list[str] = []
    i = 0
    in_string: str | None = None
    escape = False

    while i < len(text):
        ch = text[i]
        if in_string is not None:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            i += 1
            continue

        if ch in {'"', "'"}:
            in_string = ch
            result.append(ch)
            i += 1
            continue

        if ch == "-" and i + 1 < len(text) and text[i + 1] == "-":
            i += 2
            while i < len(text) and text[i] != "\n":
                i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _find_top_level_char(text: str, start: int, target: str) -> int:
    depth = 0
    in_string: str | None = None
    escape = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string is not None:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            continue

        if ch in {'"', "'"}:
            in_string = ch
            continue

        if ch in "([{":
            depth += 1
            continue

        if ch in ")]}":
            if ch == target and depth == 0:
                return index
            depth = max(0, depth - 1)
            continue

        if ch == target and depth == 0:
            return index
    return -1


def _read_lua_string(text: str, start: int) -> tuple[str, int]:
    quote = text[start]
    index = start + 1
    chars: list[str] = []
    escape = False
    while index < len(text):
        ch = text[index]
        if escape:
            chars.append(ch)
            escape = False
        elif ch == "\\":
            chars.append(ch)
            escape = True
        elif ch == quote:
            return "".join(chars), index + 1
        else:
            chars.append(ch)
        index += 1
    raise ValueError(f"Unterminated Lua string starting at {start}")


def _parse_lua_value_text(text: str, index: int) -> tuple[Any, int]:
    index = _skip_whitespace(text, index)
    if index >= len(text):
        return "", index

    ch = text[index]

    if ch == '{':
        return _load_lua_table_from_index(text, index)

    if ch in {'"', "'"}:
        return _read_lua_string(text, index)

    if ch == "_" and index + 1 < len(text) and text[index + 1] == "(":
        value, end_index = _parse_lua_value_text(text, index + 2)
        end_index = _skip_whitespace(text, end_index)
        if end_index < len(text) and text[end_index] == ")":
            return value, end_index + 1
        return value, end_index

    if text.startswith("true", index):
        return True, index + 4
    if text.startswith("false", index):
        return False, index + 5
    if text.startswith("nil", index):
        return None, index + 3
    if text.startswith("null", index):
        return None, index + 4

    if ch == "-" or ch.isdigit():
        end_index = index + 1
        while end_index < len(text) and (text[end_index].isdigit() or text[end_index] == "."):
            end_index += 1
        literal = text[index:end_index]
        if "." in literal:
            return float(literal), end_index
        return int(literal), end_index

    end_index = index + 1
    while end_index < len(text) and (text[end_index].isalnum() or text[end_index] in "_./:-"):
        end_index += 1
    return text[index:end_index], end_index


def _load_lua_table_from_index(text: str, index: int) -> tuple[Any, int]:
    index = _skip_whitespace(text, index)
    if index >= len(text) or text[index] != "{":
        raise ValueError(f"Expected Lua table at index {index}")

    index += 1
    result: dict[str, Any] = {}
    items: list[Any] = []
    is_map = False

    while True:
        index = _skip_whitespace(text, index)
        if index >= len(text):
            raise ValueError("Unterminated Lua table")
        if text[index] == "}":
            return (result if is_map else items), index + 1

        item_start = index
        terminal = _find_top_level_char(text, item_start, ",")
        close_index = _find_top_level_char(text, item_start, "}")
        if terminal == -1 or (close_index != -1 and close_index < terminal):
            terminal = close_index
        if terminal == -1:
            terminal = len(text)

        segment = text[item_start:terminal].strip()
        if not segment:
            index = terminal + 1 if terminal < len(text) and text[terminal] == "," else terminal
            continue

        eq_index = _find_top_level_char(segment, 0, "=")
        if eq_index != -1:
            key_text = segment[:eq_index].strip()
            value_text = segment[eq_index + 1 :].strip()
            key, _ = _parse_lua_value_text(key_text, 0)
            value, _ = _parse_lua_value_text(value_text, 0)
            result[str(key)] = value
            is_map = True
            index = terminal
        else:
            value, consumed = _parse_lua_value_text(text, item_start)
            items.append(value)
            index = consumed

        index = _skip_whitespace(text, index)
        if index < len(text) and text[index] == ",":
            index += 1
        elif index < len(text) and text[index] == "}":
            return (result if is_map else items), index + 1


def _load_lua_table(text: str) -> dict[str, Any] | list[Any]:
    cleaned = _strip_lua_comments(text).strip()
    if not cleaned:
        return {}

    if cleaned.startswith("function") and "return" in cleaned:
        if "return" in cleaned:
            start = cleaned.find("return")
            cleaned = cleaned[start + len("return") :].strip()
            if cleaned.endswith("end"):
                cleaned = cleaned[:-3].rstrip()

    cleaned = cleaned.lstrip()
    if not cleaned.startswith("{"):
        return {}

    payload, _ = _load_lua_table_from_index(cleaned, 0)
    if isinstance(payload, dict):
        return payload
    return payload if payload else {}


def _coerce_author(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if isinstance(value, list):
        authors: list[dict[str, str]] = []
        for entry in value:
            if isinstance(entry, str):
                authors.append({"name": entry, "role": "CREATOR"})
            elif isinstance(entry, dict):
                name = str(entry.get("name") or entry.get("author") or "Unknown author")
                role = str(entry.get("role") or "CREATOR")
                authors.append({"name": name, "role": role})
        return authors
    if isinstance(value, dict):
        name = str(value.get("name") or value.get("author") or "Unknown author")
        role = str(value.get("role") or "CREATOR")
        return [{"name": name, "role": role}]
    return [{"name": str(value), "role": "CREATOR"}]


def _normalize_mod_descriptor(raw: dict[str, Any]) -> ModDescriptor:
    nested = None
    for key in ("info", "data"):
        candidate = raw.get(key)
        if isinstance(candidate, dict):
            nested = candidate
            break
    if nested is not None:
        raw = {**nested, **{k: v for k, v in raw.items() if k not in {"info", "data"}}}

    name = str(raw.get("name") or raw.get("displayName") or raw.get("modName") or "Unnamed Mod")
    summary = str(raw.get("summary") or raw.get("description") or raw.get("shortDescription") or "")
    description = str(raw.get("description") or raw.get("details") or summary)
    authors = _coerce_author(raw.get("authors"))
    if not authors and "author" in raw:
        authors = _coerce_author(raw["author"])

    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []

    url = str(raw.get("url") or "")
    revision_value = raw.get("revision")
    if revision_value is None:
        revision_value = raw.get("version")
    if revision_value is None:
        revision_value = raw.get("minorVersion")
    if revision_value is None:
        revision_value = raw.get("majorVersion")
    revision = 1 if revision_value in (None, "") else revision_value
    try:
        revision = int(revision)
    except (TypeError, ValueError):
        revision = 1

    mod_id = raw.get("modId") or raw.get("mod_id") or raw.get("id") or ""
    mod_id = str(mod_id).strip()

    warnings: list[str] = []

    def script_reference(keys: tuple[str, ...], label: str) -> str | None:
        payload = next((raw.get(key) for key in keys if raw.get(key)), None)
        if _is_inline_callback(payload):
            warnings.append(
                f"Unsupported inline {label} callback; no file reference was written to TF3 metadata."
            )
            return None
        return _extract_file_reference(payload)

    descriptor = ModDescriptor(
        name=name,
        summary=summary,
        description=description,
        authors=authors,
        tags=[str(tag) for tag in tags],
        url=url,
        mod_id=mod_id,
        revision=revision,
        dependencies=raw.get("dependencies"),
        incompatibilities=raw.get("incompatibilities"),
        params=raw.get("params") or raw.get("options"),
        options=raw.get("options"),
        severity_add=str(raw.get("severityAdd") or "None"),
        severity_remove=str(raw.get("severityRemove") or "None"),
        pre_run_script=script_reference(("preRunScript", "preRunFn", "preScript"), "pre-run"),
        run_script=script_reference(("runScript", "runFn", "script"), "run"),
        post_run_script=script_reference(("postRunScript", "postRunFn", "postScript"), "post-run"),
        warnings=warnings,
    )
    return descriptor


def _is_inline_callback(payload: Any) -> bool:
    if isinstance(payload, dict):
        payload = payload.get("fileName") or payload.get("filename")
    return isinstance(payload, str) and bool(re.match(r"^\s*function(?:\s|\(|$)", payload))


def _extract_file_reference(payload: Any) -> str | None:
    if payload is None:
        return None
    if isinstance(payload, str):
        return None if _is_inline_callback(payload) else payload
    if isinstance(payload, dict):
        reference = payload.get("fileName") or payload.get("filename")
        return None if _is_inline_callback(reference) else reference
    return None


def inspect_mod(source: str | Path) -> ModDescriptor:
    source_path = Path(source)
    if source_path.is_file():
        if source_path.suffix.lower() == ".json":
            payload = _read_json_file(source_path)
            return _normalize_mod_descriptor(payload)
        if source_path.suffix.lower() == ".lua":
            text = source_path.read_text(encoding="utf-8")
            return _normalize_mod_descriptor(_load_lua_table(text))
    if source_path.is_dir():
        candidates = [
            source_path / "mod.json",
            source_path / "_metadata" / "modinfo.json",
            source_path / "modinfo.json",
            source_path / "info.json",
            source_path / "mod.lua",
            source_path / "modinfo.lua",
        ]
        for candidate in candidates:
            if candidate.exists():
                if candidate.suffix.lower() == ".json":
                    payload = _read_json_file(candidate)
                    if isinstance(payload, dict):
                        return _normalize_mod_descriptor(payload)
                elif candidate.suffix.lower() == ".lua":
                    text = candidate.read_text(encoding="utf-8")
                    return _normalize_mod_descriptor(_load_lua_table(text))

        raise FileNotFoundError(f"No supported mod metadata file found in {source_path}")
    raise FileNotFoundError(f"Source does not exist: {source_path}")


def convert_mod(source: str | Path, destination: str | Path, *, name: str | None = None, author: str | None = None) -> dict[str, Any]:
    source_path = Path(source)
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)

    descriptor = inspect_mod(source_path)
    if name:
        descriptor.name = name
    if author:
        descriptor.authors = [{"name": author, "role": "CREATOR"}]

    if source_path.is_dir():
        for item in source_path.iterdir():
            target = destination_path / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
    elif source_path.is_file() and source_path.suffix.lower() == ".lua":
        destination_path.joinpath("mod.lua").write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

    (destination_path / "_metadata").mkdir(parents=True, exist_ok=True)
    (destination_path / "mod.json").write_text(json.dumps(descriptor.as_mod_json(), indent=4) + "\n", encoding="utf-8")
    (destination_path / "_metadata" / "modinfo.json").write_text(json.dumps(descriptor.as_modinfo_json(), indent=4) + "\n", encoding="utf-8")

    report = {
        "destination": str(destination_path),
        "modId": descriptor.target_mod_id,
        "name": descriptor.name,
        "revision": descriptor.revision,
        "warnings": descriptor.warnings,
    }
    return report
