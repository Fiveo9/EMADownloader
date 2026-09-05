"""Graphical settings management for the local web UI.

Edits are written ONLY to the gitignored personal override file
``config/settings.local.toml`` (next to the active base config). The
committed template ``config/settings.toml`` is never touched, and unknown
keys already present in the override file (e.g. proxy credentials) are
preserved verbatim. ``load_config`` merges the override file section by
section on top of the base, so changes take effect on the next request
without restarting the server.

Python has no TOML writer in the standard library, and the managed schema
only contains strings, numbers, and lists of strings — small enough to
serialize here instead of adding a dependency.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import tomllib

from ema_downloader.config import find_default_config_path, load_config

logger = logging.getLogger("ema_downloader.webapp")

# Placeholder returned for a configured proxy so credentials never reach the
# browser; PUT requests carrying this exact value are skipped (kept as-is).
PROXY_MASK = "********"

LOCAL_FILE_NAME = "settings.local.toml"
_DEFAULT_HEADER = [
    "# Personal configuration overrides.",
    "# Managed by the Web UI settings page; merged over settings.toml at startup.",
]


class SettingsValidationError(Exception):
    """Raised when submitted settings fail validation; carries field errors."""

    def __init__(self, errors: List[Dict[str, str]]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} 个设置项未通过校验")


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------


def _v_int(field: str, value: Any, lo: int, hi: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} 必须是整数")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} 必须是整数") from None
    if not lo <= number <= hi:
        raise ValueError(f"{field} 必须在 {lo} 到 {hi} 之间")
    return number


def _v_float(field: str, value: Any, lo: float, hi: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} 必须是数字")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} 必须是数字") from None
    if not lo <= number <= hi:
        raise ValueError(f"{field} 必须在 {lo} 到 {hi} 之间")
    return number


def _v_str(field: str, value: Any, allow_empty: bool = False, max_len: int = 1024) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是字符串")
    text = value.strip()
    if not text and not allow_empty:
        raise ValueError(f"{field} 不能为空")
    if len(text) > max_len:
        raise ValueError(f"{field} 过长（最多 {max_len} 字符）")
    return text


def _v_str_list(field: str, value: Any, max_items: int = 30, item_len: int = 120) -> List[str]:
    if isinstance(value, str):
        value = [part for part in value.split(",")]
    if not isinstance(value, list):
        raise ValueError(f"{field} 必须是字符串列表")
    cleaned: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field} 的每一项都必须是字符串")
        text = item.strip()
        if not text:
            continue
        if len(text) > item_len:
            raise ValueError(f"{field} 中存在超过 {item_len} 字符的项")
        cleaned.append(text)
    if len(cleaned) > max_items:
        raise ValueError(f"{field} 最多 {max_items} 项")
    return cleaned


def _proxy_validator(field: str, value: Any) -> str:
    return _v_str(field, value, allow_empty=True, max_len=2048)


# section -> field -> (validator, ui 描述)
FIELD_SCHEMA: Dict[str, Dict[str, Tuple[Callable[[str, Any], Any], str]]] = {
    "network": {
        "workers": (lambda f, v: _v_int(f, v, 1, 16), "并发下载数 (1-16)"),
        "timeout": (lambda f, v: _v_float(f, v, 1, 600), "请求超时 (秒)"),
        "max_retries": (lambda f, v: _v_int(f, v, 1, 10), "最大重试次数"),
        "retry_delay": (lambda f, v: _v_float(f, v, 0, 60), "重试退避基数 (秒)"),
        "request_delay": (lambda f, v: _v_float(f, v, 0, 60), "下载间隔 (秒)"),
        "proxy": (_proxy_validator, "代理地址"),
    },
    "filters": {
        "default_types": (lambda f, v: _v_str_list(f, v), "默认文档类型"),
        "default_status": (lambda f, v: _v_str_list(f, v), "默认官方状态"),
        "default_languages": (lambda f, v: _v_str_list(f, v), "默认语言"),
    },
    "storage": {
        "library_dir": (lambda f, v: _v_str(f, v), "资料库目录"),
    },
    "classification": {
        "rules_file": (lambda f, v: _v_str(f, v), "分类规则 CSV 路径"),
    },
}


# ---------------------------------------------------------------------------
# Paths and local TOML read/write
# ---------------------------------------------------------------------------


def resolve_paths(config_path: Optional[Path | str]) -> Tuple[Optional[Path], Path]:
    """Return (base settings path or None, local override path)."""
    if config_path:
        base = Path(config_path)
        return base, base.with_name(LOCAL_FILE_NAME)
    base = find_default_config_path()
    if base:
        return base, base.with_name(LOCAL_FILE_NAME)
    return None, Path.cwd() / "config" / LOCAL_FILE_NAME


def _load_local(local_path: Path) -> Tuple[Dict[str, Any], List[str]]:
    """Parse the override file, returning (data, leading comment lines)."""
    if not local_path.exists():
        return {}, list(_DEFAULT_HEADER)
    try:
        with open(local_path, "rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise SettingsValidationError(
            [{"section": "-", "field": "-", "message": f"现有配置文件解析失败: {exc}"}]
        ) from exc

    header: List[str] = []
    with open(local_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.strip() == "" and not header:
                continue
            if line.strip().startswith("#"):
                header.append(line)
            else:
                break
    return data, header or list(_DEFAULT_HEADER)


def _toml_string(value: str) -> str:
    if "'" not in value and "\n" not in value and "\t" not in value:
        return f"'{value}'"  # literal string: backslashes (Windows paths) need no escaping
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise SettingsValidationError(
        [{"section": "-", "field": "-", "message": f"不支持的配置值类型: {type(value).__name__}"}]
    )


def _dump_table(lines: List[str], prefix: str, values: Dict[str, Any]) -> None:
    scalars = {key: val for key, val in values.items() if not isinstance(val, dict)}
    nested = {key: val for key, val in values.items() if isinstance(val, dict)}
    if scalars or not nested:
        lines.append(f"[{prefix}]")
        for key, val in scalars.items():
            lines.append(f"{key} = {_toml_value(val)}")
    for key, val in nested.items():
        _dump_table(lines, f"{prefix}.{key}", val)


def _dump_toml(data: Dict[str, Any], header: List[str]) -> str:
    lines = list(header)
    for section, values in data.items():
        if isinstance(values, dict):
            _dump_table(lines, str(section), values)
        else:
            lines.append(f"{section} = {_toml_value(values)}")
    return "\n".join(lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_settings(config_path: Optional[Path | str]) -> Dict[str, Any]:
    """Effective settings merged from base + local, with override marks."""
    config = load_config(config_path=config_path)
    base, local = resolve_paths(config_path)
    local_data, _ = _load_local(local)

    proxy = config.network.get_effective_proxy() or ""
    values: Dict[str, Any] = {
        "network": {
            "workers": config.network.workers,
            "timeout": config.network.timeout,
            "max_retries": config.network.max_retries,
            "retry_delay": config.network.retry_delay,
            "request_delay": config.network.request_delay,
            "proxy": PROXY_MASK if proxy else "",
        },
        "filters": {
            "default_types": list(config.filters.default_types),
            "default_status": list(config.filters.default_status),
            "default_languages": list(config.filters.default_languages),
        },
        "storage": {
            "library_dir": str(config.storage.library_dir),
        },
        "classification": {
            "rules_file": str(config.classification.rules_file),
        },
    }
    overridden = {
        str(section): sorted(fields.keys())
        for section, fields in local_data.items()
        if isinstance(fields, dict)
    }
    return {
        "base_path": str(base) if base else None,
        "local_path": str(local),
        "values": values,
        "overridden": overridden,
    }


def write_settings(
    config_path: Optional[Path | str], updates: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate submitted settings and merge them into the local override file.

    Returns the applied (cleaned) updates. Raises SettingsValidationError with
    per-field errors, or OSError when the file cannot be written.
    """
    if not isinstance(updates, dict):
        raise SettingsValidationError(
            [{"section": "-", "field": "-", "message": "请求体必须是对象"}]
        )

    clean: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, str]] = []
    for section, fields in updates.items():
        schema = FIELD_SCHEMA.get(str(section))
        if schema is None:
            errors.append({"section": str(section), "field": "-", "message": "不支持的配置分组"})
            continue
        if not isinstance(fields, dict):
            errors.append({"section": str(section), "field": "-", "message": "配置分组必须是对象"})
            continue
        for field, value in fields.items():
            entry = schema.get(str(field))
            if entry is None:
                errors.append({"section": str(section), "field": str(field), "message": "不支持的设置项"})
                continue
            validator, label = entry
            try:
                cleaned_value = validator(label, value)
            except ValueError as exc:
                errors.append({"section": str(section), "field": str(field), "message": str(exc)})
                continue
            clean.setdefault(str(section), {})[str(field)] = cleaned_value

    if errors:
        raise SettingsValidationError(errors)

    # A proxy equal to the mask placeholder means "unchanged"; never persist it.
    network_fields = clean.get("network")
    if network_fields and network_fields.get("proxy") == PROXY_MASK:
        del network_fields["proxy"]
        if not network_fields:
            clean.pop("network")

    if clean:
        base, local = resolve_paths(config_path)
        data, header = _load_local(local)
        for section, fields in clean.items():
            data.setdefault(section, {}).update(fields)
        content = _dump_toml(data, header)
        tmp_path = local.with_suffix(".toml.tmp")
        local.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_path, local)
        logger.info("Settings updated in %s: %s", local, ", ".join(
            f"{section}.{field}" for section, fields in clean.items() for field in fields
        ))

    return clean
