"""JSON Schema 校验辅助。"""

from __future__ import annotations

import json
from typing import Any

import jsonschema
from jsonschema import ValidationError


def parse_json_maybe(raw: str | None) -> Any:
    if not raw:
        return None
    return json.loads(raw)


def validate_extra_fields(
    schema_raw: str | None,
    extra_fields: dict[str, Any] | None,
) -> None:
    """若社区配置了 application_schema / final_schema，则用 jsonschema 校验。"""
    if not schema_raw:
        return
    schema = json.loads(schema_raw)
    instance = extra_fields or {}
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except ValidationError as exc:
        raise ValueError(f"extra_fields 不符合社区 schema: {exc.message}") from exc


def dumps_extra(extra_fields: dict[str, Any] | None) -> str | None:
    if extra_fields is None:
        return None
    return json.dumps(extra_fields, ensure_ascii=False)
