from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from jsonschema import Draft202012Validator


SCHEMA_V1: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["project", "datasource", "tables", "relations", "global"],
    "additionalProperties": False,
    "properties": {
        "project": {
            "type": "object",
            "required": [
                "groupId",
                "artifactId",
                "name",
                "basePackage",
                "bootVersion",
                "javaVersion",
            ],
            "additionalProperties": False,
            "properties": {
                "groupId": {"type": "string", "minLength": 1},
                "artifactId": {"type": "string", "minLength": 1},
                "name": {"type": "string", "minLength": 1},
                "basePackage": {"type": "string", "minLength": 1},
                "bootVersion": {"type": "string", "pattern": r"^2\..+"},
                "javaVersion": {
                    "oneOf": [
                        {"type": "string", "enum": ["8"]},
                        {"type": "integer", "enum": [8]},
                    ]
                },
            },
        },
        "datasource": {
            "type": "object",
            "required": ["url", "username", "password", "driverClassName"],
            "additionalProperties": False,
            "properties": {
                "url": {"type": "string", "minLength": 1},
                "databaseName": {"type": "string", "minLength": 1},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "driverClassName": {"type": "string", "minLength": 1},
            },
        },
        "backend": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "outputDir": {"type": "string", "minLength": 1},
            },
        },
        "frontend": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "framework": {"type": "string", "enum": ["vue2"]},
                "locale": {"type": "string", "enum": ["zh-CN", "en-US"]},
                "outputDir": {"type": "string", "minLength": 1},
                "appTitle": {"type": "string"},
                "backendUrl": {"type": "string", "minLength": 1},
                "devPort": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535,
                },
            },
        },
        "tables": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "comment",
                    "entityName",
                    "fields",
                    "primaryKey",
                    "queryableFields",
                ],
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "comment": {"type": "string"},
                    "frontend": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "menuTitle": {"type": "string"},
                            "menuIcon": {"type": "string", "minLength": 1},
                            "menuVisible": {"type": "boolean", "default": True},
                        },
                    },
                    "entityName": {"type": "string", "minLength": 1},
                    "primaryKey": {"type": "string", "minLength": 1},
                    "queryableFields": {
                        "type": "array",
                        "items": {
                            "oneOf": [
                                {"type": "string", "minLength": 1},
                                {
                                    "type": "object",
                                    "required": ["name"],
                                    "additionalProperties": False,
                                    "properties": {
                                        "name": {"type": "string", "minLength": 1},
                                        "operator": {
                                            "type": "string",
                                            "enum": [
                                                "EQ",
                                                "NE",
                                                "LIKE",
                                                "GT",
                                                "GE",
                                                "LT",
                                                "LE",
                                            ],
                                            "default": "EQ",
                                        },
                                    },
                                },
                            ]
                        },
                    },
                    "sortableFields": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                    },
                    "indexes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["columns"],
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "columns": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "unique": {"type": "boolean", "default": False},
                            },
                        },
                    },
                    "foreignKeys": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["columns", "refTable", "refColumns"],
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "columns": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "refTable": {"type": "string", "minLength": 1},
                                "refColumns": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "onDelete": {
                                    "type": "string",
                                    "enum": [
                                        "RESTRICT",
                                        "CASCADE",
                                        "SET NULL",
                                        "NO ACTION",
                                    ],
                                },
                                "onUpdate": {
                                    "type": "string",
                                    "enum": [
                                        "RESTRICT",
                                        "CASCADE",
                                        "SET NULL",
                                        "NO ACTION",
                                    ],
                                },
                            },
                        },
                    },
                    "inferIndexes": {"type": "boolean", "default": True},
                    "inferForeignKeys": {"type": "boolean", "default": True},
                    "seedData": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": {
                                "type": [
                                    "string",
                                    "number",
                                    "integer",
                                    "boolean",
                                    "null",
                                ]
                            },
                        },
                    },
                    "fields": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": [
                                "name",
                                "type",
                                "nullable",
                                "comment",
                            ],
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string", "minLength": 1},
                                "type": {"type": "string", "minLength": 1},
                                "nullable": {"type": "boolean"},
                                "comment": {"type": "string"},
                                "unique": {"type": "boolean", "default": False},
                                "logicDelete": {"type": "boolean", "default": False},
                                "frontend": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "label": {"type": "string"},
                                        "component": {
                                            "type": "string",
                                            "enum": [
                                                "text",
                                                "textarea",
                                                "number",
                                                "switch",
                                                "date",
                                                "datetime",
                                                "select",
                                            ],
                                        },
                                        "queryComponent": {
                                            "type": "string",
                                            "enum": [
                                                "text",
                                                "textarea",
                                                "number",
                                                "switch",
                                                "date",
                                                "datetime",
                                                "select",
                                            ],
                                        },
                                        "tableVisible": {
                                            "type": "boolean",
                                            "default": True,
                                        },
                                        "formVisible": {
                                            "type": "boolean",
                                            "default": True,
                                        },
                                        "detailVisible": {
                                            "type": "boolean",
                                            "default": True,
                                        },
                                        "queryVisible": {
                                            "type": "boolean",
                                            "default": True,
                                        },
                                        "placeholder": {"type": "string"},
                                        "options": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["label", "value"],
                                                "additionalProperties": False,
                                                "properties": {
                                                    "label": {
                                                        "type": "string",
                                                        "minLength": 1,
                                                    },
                                                    "value": {
                                                        "type": [
                                                            "string",
                                                            "number",
                                                            "integer",
                                                            "boolean",
                                                            "null",
                                                        ]
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                                "autoFill": {
                                    "type": "string",
                                    "enum": ["INSERT", "UPDATE", "INSERT_UPDATE"],
                                },
                                "idType": {
                                    "type": "string",
                                    "enum": ["AUTO", "ASSIGN_ID", "INPUT"],
                                },
                            },
                        },
                    },
                },
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "leftTable",
                    "rightTable",
                    "joinType",
                    "on",
                    "select",
                    "filters",
                    "dtoName",
                    "methodName",
                ],
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "frontend": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "menuTitle": {"type": "string"},
                            "menuIcon": {"type": "string", "minLength": 1},
                            "menuVisible": {"type": "boolean", "default": True},
                        },
                    },
                    "leftTable": {"type": "string", "minLength": 1},
                    "rightTable": {"type": "string", "minLength": 1},
                    "joinType": {"type": "string", "enum": ["INNER", "LEFT"]},
                    "dtoName": {"type": "string", "minLength": 1},
                    "methodName": {"type": "string", "minLength": 1},
                    "on": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["leftField", "rightField"],
                            "additionalProperties": False,
                            "properties": {
                                "leftField": {"type": "string", "minLength": 1},
                                "rightField": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                    "select": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["table", "field"],
                            "additionalProperties": False,
                            "properties": {
                                "table": {"type": "string", "minLength": 1},
                                "field": {"type": "string", "minLength": 1},
                                "alias": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["table", "field", "operator", "param"],
                            "additionalProperties": False,
                            "properties": {
                                "table": {"type": "string", "minLength": 1},
                                "field": {"type": "string", "minLength": 1},
                                "operator": {
                                    "type": "string",
                                    "enum": [
                                        "EQ",
                                        "NE",
                                        "LIKE",
                                        "GT",
                                        "GE",
                                        "LT",
                                        "LE",
                                    ],
                                },
                                "param": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                    "sortableFields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["table", "field"],
                            "additionalProperties": False,
                            "properties": {
                                "table": {"type": "string", "minLength": 1},
                                "field": {"type": "string", "minLength": 1},
                                "name": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                },
            },
        },
        "global": {
            "type": "object",
            "required": ["apiPrefix", "author", "dateTimeFormat", "enableSwagger"],
            "additionalProperties": False,
            "properties": {
                "apiPrefix": {"type": "string", "default": "/api"},
                "author": {"type": "string"},
                "dateTimeFormat": {"type": "string", "default": "yyyy-MM-dd HH:mm:ss"},
                "enableSwagger": {"type": "boolean", "default": False},
            },
        },
    },
}


@dataclass(slots=True)
class ValidationErrorItem:
    path: str
    message: str


def _format_path(path_segments: Iterable[Any]) -> str:
    parts: List[str] = []
    for seg in path_segments:
        if isinstance(seg, int):
            parts.append(f"[{seg}]")
            continue
        if not parts:
            parts.append(str(seg))
        else:
            parts.append(f".{seg}")
    return "".join(parts) or "$"


def validate_schema(payload: Dict[str, Any]) -> List[ValidationErrorItem]:
    validator = Draft202012Validator(SCHEMA_V1)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    items: List[ValidationErrorItem] = []
    for error in errors:
        items.append(
            ValidationErrorItem(path=_format_path(error.path), message=error.message)
        )
    return items
