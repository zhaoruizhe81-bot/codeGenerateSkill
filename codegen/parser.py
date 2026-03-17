from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .ir import (
    BackendIR,
    DictionaryIR,
    DictionaryItemIR,
    FieldIR,
    FieldFrontendIR,
    FrontendIR,
    FrontendOptionIR,
    ForeignKeyIR,
    IndexIR,
    ProjectIR,
    QueryableFieldIR,
    RelationFrontendIR,
    RelationFilterIR,
    RelationIR,
    RelationOnIR,
    RelationSelectIR,
    SortableFieldIR,
    TableIR,
    TableFrontendIR,
    SecurityIR,
    JwtConfigIR,
    RbacConfigIR,
    TableAuthIR,
    PermissionIR,
    TenantIR,
)
from .schema import validate_schema
from .type_mapping import db_to_java, snake_to_camel, snake_to_pascal


@dataclass(slots=True)
class ParseIssue:
    path: str
    message: str


class ConfigError(Exception):
    def __init__(self, issues: List[ParseIssue]):
        self.issues = issues
        message = "\n".join([f"- {item.path}: {item.message}" for item in issues])
        super().__init__(f"Invalid config:\n{message}")


RANGE_OPERATORS = {"GT", "GE", "LT", "LE"}
ROLE_PREFIX = "ROLE_"
DICT_VALUE_TYPE_TO_JAVA = {
    "string": "String",
    "integer": "Integer",
    "long": "Long",
    "boolean": "Boolean",
}


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_role_code(raw_role: Any) -> str:
    role = str(raw_role).strip().upper()
    if role.startswith(ROLE_PREFIX):
        return role
    return f"{ROLE_PREFIX}{role}"


def _normalize_role_list(
    raw_roles: List[Any], path: str, issues: List[ParseIssue]
) -> List[str]:
    normalized_roles: List[str] = []
    seen_roles: set[str] = set()
    for index, raw_role in enumerate(raw_roles):
        role = str(raw_role).strip()
        if not role:
            issues.append(
                ParseIssue(
                    path=f"{path}[{index}]",
                    message="role must not be blank",
                )
            )
            continue
        normalized_role = _normalize_role_code(role)
        if normalized_role in seen_roles:
            continue
        seen_roles.add(normalized_role)
        normalized_roles.append(normalized_role)
    return normalized_roles


def _normalize_required_role(
    raw_role: Any, path: str, issues: List[ParseIssue], default_role: str
) -> str:
    role = str(raw_role).strip()
    if not role:
        issues.append(ParseIssue(path=path, message="role must not be blank"))
        return default_role
    return _normalize_role_code(role)


def _default_role_name(role_code: str) -> str:
    role_name = role_code
    if role_name.startswith(ROLE_PREFIX):
        role_name = role_name[len(ROLE_PREFIX) :]
    return role_name.replace("_", " ").title()


def _next_seed_id(seed_data: List[Dict[str, Any]]) -> int:
    numeric_ids = [
        int(item["id"])
        for item in seed_data
        if isinstance(item.get("id"), int) or str(item.get("id", "")).isdigit()
    ]
    if not numeric_ids:
        return 1
    return max(numeric_ids) + 1


def _normalize_dictionary_value(value: Any, value_type: str) -> Any:
    if value_type == "string":
        return str(value)
    if value_type in {"integer", "long"}:
        return int(value)
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        lowered = str(value).strip().lower()
        if lowered in {"1", "true"}:
            return True
        if lowered in {"0", "false"}:
            return False
    raise ValueError(f"unsupported dictionary value '{value}' for type '{value_type}'")


def _is_dictionary_value_compatible(value: Any, value_type: str) -> bool:
    if value_type == "string":
        return isinstance(value, str)
    if value_type in {"integer", "long"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "boolean":
        return isinstance(value, bool)
    return False


def _parse_dictionaries(
    payload: Dict[str, Any], issues: List[ParseIssue]
) -> List[DictionaryIR]:
    dictionaries: List[DictionaryIR] = []
    seen_keys: set[str] = set()

    for index, dictionary_cfg in enumerate(payload.get("dictionaries", [])):
        path = f"dictionaries[{index}]"
        dict_key = str(dictionary_cfg["key"]).strip()
        if dict_key in seen_keys:
            issues.append(
                ParseIssue(
                    path=f"{path}.key",
                    message=f"duplicated dictionary key '{dict_key}'",
                )
            )
            continue
        seen_keys.add(dict_key)
        value_type = str(dictionary_cfg["valueType"])
        items: List[DictionaryItemIR] = []
        seen_values: set[tuple[str, Any]] = set()
        for item_index, item_cfg in enumerate(dictionary_cfg["items"]):
            item_path = f"{path}.items[{item_index}]"
            raw_value = item_cfg["value"]
            if not _is_dictionary_value_compatible(raw_value, value_type):
                issues.append(
                    ParseIssue(
                        path=f"{item_path}.value",
                        message=f"value must match dictionary valueType '{value_type}'",
                    )
                )
                continue
            normalized_value = _normalize_dictionary_value(raw_value, value_type)
            dedupe_key = (value_type, normalized_value)
            if dedupe_key in seen_values:
                issues.append(
                    ParseIssue(
                        path=f"{item_path}.value",
                        message=f"duplicated dictionary value '{normalized_value}'",
                    )
                )
                continue
            seen_values.add(dedupe_key)
            items.append(
                DictionaryItemIR(
                    label=str(item_cfg["label"]),
                    value=normalized_value,
                    sort=int(item_cfg.get("sort", 0)),
                    enabled=bool(item_cfg.get("enabled", True)),
                )
            )

        dictionaries.append(
            DictionaryIR(
                key=dict_key,
                name=str(dictionary_cfg["name"]),
                value_type=value_type,
                items=items,
            )
        )

    return dictionaries


def _collect_rbac_permissions(
    tables: List[TableIR], relations: List[RelationIR]
) -> List[str]:
    permissions: List[str] = []
    seen_permissions: set[str] = set()

    def add_permission(permission: str | None) -> None:
        if not permission or permission in seen_permissions:
            return
        seen_permissions.add(permission)
        permissions.append(permission)

    for table in tables:
        if table.auth is None or not table.auth.enabled:
            continue
        add_permission(table.auth.permissions.query)
        add_permission(table.auth.permissions.create)
        add_permission(table.auth.permissions.update)
        add_permission(table.auth.permissions.delete)

    for relation in relations:
        if relation.auth is None or not relation.auth.enabled:
            continue
        add_permission(relation.auth.permissions.query)

    return permissions


def _ensure_rbac_seed_data(
    tables: List[TableIR], relations: List[RelationIR], rbac: RbacConfigIR
) -> None:
    table_by_name = {table.name: table for table in tables}
    required_table_names = {
        "sys_user",
        "sys_role",
        "sys_user_role",
        "sys_menu_permission",
        "sys_role_permission",
    }
    if not required_table_names.issubset(table_by_name):
        return

    sys_user_table = table_by_name["sys_user"]
    sys_role_table = table_by_name["sys_role"]
    sys_user_role_table = table_by_name["sys_user_role"]
    sys_menu_permission_table = table_by_name["sys_menu_permission"]
    sys_role_permission_table = table_by_name["sys_role_permission"]

    desired_role_codes = [rbac.super_admin_role] + [
        role_code
        for role_code in rbac.default_roles
        if role_code != rbac.super_admin_role
    ]

    role_seed_by_code: Dict[str, Dict[str, Any]] = {}
    for seed_row in sys_role_table.seed_data:
        role_code = seed_row.get("role_code")
        if isinstance(role_code, str) and role_code.strip():
            normalized_role_code = _normalize_role_code(role_code)
            if normalized_role_code != role_code:
                seed_row["role_code"] = normalized_role_code
            role_seed_by_code[normalized_role_code] = seed_row

    next_role_id = _next_seed_id(sys_role_table.seed_data)
    for role_code in desired_role_codes:
        if role_code in role_seed_by_code:
            continue
        role_seed = {
            "id": next_role_id,
            "role_name": _default_role_name(role_code),
            "role_code": role_code,
            "created_at": "2024-01-01 00:00:00",
        }
        sys_role_table.seed_data.append(role_seed)
        role_seed_by_code[role_code] = role_seed
        next_role_id += 1

    admin_user_id = 1
    for seed_row in sys_user_table.seed_data:
        if seed_row.get("username") == "admin" and seed_row.get("id") is not None:
            admin_user_id = int(seed_row["id"])
            break

    super_admin_role_id = int(role_seed_by_code[rbac.super_admin_role]["id"])
    existing_user_role_pairs = {
        (int(seed_row["user_id"]), int(seed_row["role_id"]))
        for seed_row in sys_user_role_table.seed_data
        if seed_row.get("user_id") is not None and seed_row.get("role_id") is not None
    }
    admin_mapping = (admin_user_id, super_admin_role_id)
    if admin_mapping not in existing_user_role_pairs:
        sys_user_role_table.seed_data.append(
            {
                "id": _next_seed_id(sys_user_role_table.seed_data),
                "user_id": admin_user_id,
                "role_id": super_admin_role_id,
            }
        )

    permission_seed_by_code: Dict[str, Dict[str, Any]] = {}
    for seed_row in sys_menu_permission_table.seed_data:
        permission_code = seed_row.get("permission_str")
        if isinstance(permission_code, str) and permission_code.strip():
            permission_seed_by_code[permission_code] = seed_row

    next_permission_id = _next_seed_id(sys_menu_permission_table.seed_data)
    for permission_code in _collect_rbac_permissions(tables, relations):
        if permission_code in permission_seed_by_code:
            continue
        permission_seed = {
            "id": next_permission_id,
            "parent_id": 0,
            "name": permission_code,
            "permission_str": permission_code,
            "type": 2,
            "path": None,
        }
        sys_menu_permission_table.seed_data.append(permission_seed)
        permission_seed_by_code[permission_code] = permission_seed
        next_permission_id += 1

    existing_role_permission_pairs = {
        (int(seed_row["role_id"]), int(seed_row["permission_id"]))
        for seed_row in sys_role_permission_table.seed_data
        if seed_row.get("role_id") is not None
        and seed_row.get("permission_id") is not None
    }
    next_role_permission_id = _next_seed_id(sys_role_permission_table.seed_data)
    for permission_code in _collect_rbac_permissions(tables, relations):
        permission_id = int(permission_seed_by_code[permission_code]["id"])
        mapping = (super_admin_role_id, permission_id)
        if mapping in existing_role_permission_pairs:
            continue
        sys_role_permission_table.seed_data.append(
            {
                "id": next_role_permission_id,
                "role_id": super_admin_role_id,
                "permission_id": permission_id,
            }
        )
        existing_role_permission_pairs.add(mapping)
        next_role_permission_id += 1


def _dictionary_seed_value(value: Any, value_type: str) -> str:
    normalized = _normalize_dictionary_value(value, value_type)
    if value_type == "boolean":
        return "true" if normalized else "false"
    return str(normalized)


def _inject_dictionary_tables(payload: Dict[str, Any], security_enabled: bool) -> None:
    existing_tables = {t["name"] for t in payload.get("tables", [])}
    dictionary_tables = []

    if "sys_dict_type" not in existing_tables:
        table_cfg = {
                "name": "sys_dict_type",
                "comment": "Dictionary Type",
                "entityName": "SysDictType",
                "primaryKey": "id",
                "queryableFields": [
                    {"name": "dict_key", "operator": "LIKE"},
                    {"name": "dict_name", "operator": "LIKE"},
                ],
                "sortableFields": ["dict_key", "created_at"],
                "frontend": {
                    "menuTitle": "Dictionary Types",
                    "menuIcon": "el-icon-collection-tag",
                },
                "fields": [
                    {"name": "id", "type": "bigint", "nullable": False, "idType": "AUTO", "comment": "ID"},
                    {"name": "dict_key", "type": "varchar(64)", "nullable": False, "unique": True, "comment": "Dictionary Key"},
                    {"name": "dict_name", "type": "varchar(128)", "nullable": False, "comment": "Dictionary Name"},
                    {"name": "value_type", "type": "varchar(32)", "nullable": False, "comment": "Dictionary Value Type"},
                    {"name": "created_at", "type": "datetime", "nullable": False, "autoFill": "INSERT", "comment": "Created Time"},
                ],
            }
        if security_enabled:
            table_cfg["auth"] = {
                "permissions": {
                    "query": "system:dict-type:view",
                    "create": "system:dict-type:add",
                    "update": "system:dict-type:edit",
                    "delete": "system:dict-type:delete",
                }
            }
        dictionary_tables.append(table_cfg)

    if "sys_dict_item" not in existing_tables:
        table_cfg = {
                "name": "sys_dict_item",
                "comment": "Dictionary Item",
                "entityName": "SysDictItem",
                "primaryKey": "id",
                "queryableFields": [
                    {"name": "dict_type_id", "operator": "EQ"},
                    {"name": "item_label", "operator": "LIKE"},
                ],
                "sortableFields": ["dict_type_id", "sort", "created_at"],
                "frontend": {
                    "menuTitle": "Dictionary Items",
                    "menuIcon": "el-icon-tickets",
                },
                "foreignKeys": [
                    {
                        "columns": ["dict_type_id"],
                        "refTable": "sys_dict_type",
                        "refColumns": ["id"],
                    }
                ],
                "fields": [
                    {"name": "id", "type": "bigint", "nullable": False, "idType": "AUTO", "comment": "ID"},
                    {"name": "dict_type_id", "type": "bigint", "nullable": False, "comment": "Dictionary Type ID"},
                    {"name": "item_label", "type": "varchar(128)", "nullable": False, "comment": "Dictionary Item Label"},
                    {"name": "item_value", "type": "varchar(128)", "nullable": False, "comment": "Dictionary Item Value"},
                    {"name": "sort", "type": "int", "nullable": False, "comment": "Sort Order"},
                    {"name": "enabled", "type": "tinyint(1)", "nullable": False, "comment": "Enabled Status"},
                    {"name": "created_at", "type": "datetime", "nullable": False, "autoFill": "INSERT", "comment": "Created Time"},
                ],
            }
        if security_enabled:
            table_cfg["auth"] = {
                "permissions": {
                    "query": "system:dict-item:view",
                    "create": "system:dict-item:add",
                    "update": "system:dict-item:edit",
                    "delete": "system:dict-item:delete",
                }
            }
        dictionary_tables.append(table_cfg)

    payload["tables"] = dictionary_tables + payload.get("tables", [])


def _ensure_dictionary_seed_data(
    tables: List[TableIR], dictionaries: List[DictionaryIR]
) -> None:
    if not dictionaries:
        return

    table_by_name = {table.name: table for table in tables}
    if "sys_dict_type" not in table_by_name or "sys_dict_item" not in table_by_name:
        return

    dict_type_table = table_by_name["sys_dict_type"]
    dict_item_table = table_by_name["sys_dict_item"]

    type_seed_by_key: Dict[str, Dict[str, Any]] = {}
    for seed_row in dict_type_table.seed_data:
        dict_key = seed_row.get("dict_key")
        if isinstance(dict_key, str) and dict_key.strip():
            type_seed_by_key[dict_key] = seed_row

    next_type_id = _next_seed_id(dict_type_table.seed_data)
    for dictionary in dictionaries:
        if dictionary.key in type_seed_by_key:
            seed_row = type_seed_by_key[dictionary.key]
            seed_row["dict_name"] = dictionary.name
            seed_row["value_type"] = dictionary.value_type
            continue
        seed_row = {
            "id": next_type_id,
            "dict_key": dictionary.key,
            "dict_name": dictionary.name,
            "value_type": dictionary.value_type,
            "created_at": "2024-01-01 00:00:00",
        }
        dict_type_table.seed_data.append(seed_row)
        type_seed_by_key[dictionary.key] = seed_row
        next_type_id += 1

    existing_item_keys = {
        (
            int(seed_row["dict_type_id"]),
            str(seed_row["item_value"]),
        )
        for seed_row in dict_item_table.seed_data
        if seed_row.get("dict_type_id") is not None and seed_row.get("item_value") is not None
    }
    next_item_id = _next_seed_id(dict_item_table.seed_data)
    for dictionary in dictionaries:
        dict_type_id = int(type_seed_by_key[dictionary.key]["id"])
        for item in dictionary.items:
            item_value = _dictionary_seed_value(item.value, dictionary.value_type)
            dedupe_key = (dict_type_id, item_value)
            if dedupe_key in existing_item_keys:
                continue
            dict_item_table.seed_data.append(
                {
                    "id": next_item_id,
                    "dict_type_id": dict_type_id,
                    "item_label": item.label,
                    "item_value": item_value,
                    "sort": item.sort,
                    "enabled": item.enabled,
                    "created_at": "2024-01-01 00:00:00",
                }
            )
            existing_item_keys.add(dedupe_key)
            next_item_id += 1


def parse_config(payload: Dict[str, Any]) -> ProjectIR:
    issues: List[ParseIssue] = []

    schema_errors = validate_schema(payload)
    if schema_errors:
        for item in schema_errors:
            issues.append(ParseIssue(path=item.path, message=item.message))
        raise ConfigError(issues)

    project_cfg = payload["project"]
    datasource_cfg = payload["datasource"]
    backend_cfg = payload.get("backend", {})
    frontend_cfg = payload.get("frontend", {})
    global_cfg = payload["global"]
    dictionaries_ir = _parse_dictionaries(payload, issues)
    dictionary_by_key = {item.key: item for item in dictionaries_ir}

    security_cfg = payload.get("security", {})
    jwt_cfg = security_cfg.get("jwt", {})
    rbac_cfg = security_cfg.get("rbac", {})
    
    security_enabled = bool(security_cfg.get("enabled", False))
    default_roles_input = rbac_cfg.get("defaultRoles")
    if default_roles_input is None and security_enabled:
        default_roles_input = ["ROLE_USER"]
    elif default_roles_input is None:
        default_roles_input = []
    normalized_default_roles = _normalize_role_list(
        list(default_roles_input),
        "security.rbac.defaultRoles",
        issues,
    )
    if security_enabled and not normalized_default_roles:
        normalized_default_roles = ["ROLE_USER"]

    security_ir = SecurityIR(
        enabled=security_enabled,
        type=str(security_cfg.get("type", "jwt")),
        jwt=JwtConfigIR(
            secret=str(jwt_cfg.get("secret", "default-secret-key-must-be-at-least-256-bits")),
            expiration=int(jwt_cfg.get("expiration", 86400)),
            header=str(jwt_cfg.get("header", "Authorization")),
            prefix=str(jwt_cfg.get("prefix", "Bearer ")),
        ),
        rbac=RbacConfigIR(
            strategy=str(rbac_cfg.get("strategy", "role_permission")),
            super_admin_role=_normalize_required_role(
                rbac_cfg.get("superAdminRole", "ROLE_ADMIN"),
                "security.rbac.superAdminRole",
                issues,
                "ROLE_ADMIN",
            ),
            default_roles=normalized_default_roles,
        )
    )

    if security_ir.enabled:
        _inject_rbac_tables(payload, security_ir.rbac)
    if dictionaries_ir:
        _inject_dictionary_tables(payload, security_ir.enabled)

    if not _is_valid_package(project_cfg["basePackage"]):
        issues.append(
            ParseIssue(path="project.basePackage", message="invalid Java package name")
        )

    api_prefix = global_cfg.get("apiPrefix", "/api")
    if not str(api_prefix).startswith("/"):
        issues.append(
            ParseIssue(path="global.apiPrefix", message="must start with '/'")
        )

    if not str(project_cfg["bootVersion"]).startswith("2."):
        issues.append(
            ParseIssue(path="project.bootVersion", message="must start with '2.'")
        )

    if str(project_cfg["javaVersion"]) != "8":
        issues.append(
            ParseIssue(
                path="project.javaVersion", message="only Java 8 is supported in v1"
            )
        )

    table_map: Dict[str, TableIR] = {}
    tables: List[TableIR] = []

    for table_index, table_cfg in enumerate(payload["tables"]):
        table_path = f"tables[{table_index}]"
        table_name = table_cfg["name"]

        if table_name in table_map:
            issues.append(
                ParseIssue(
                    path=f"{table_path}.name",
                    message=f"duplicated table '{table_name}'",
                )
            )
            continue

        entity_name = table_cfg.get("entityName") or snake_to_pascal(table_name)
        if not _is_valid_java_identifier(entity_name):
            issues.append(
                ParseIssue(
                    path=f"{table_path}.entityName", message="invalid Java class name"
                )
            )
            continue
        object_name = entity_name[:1].lower() + entity_name[1:]

        fields: List[FieldIR] = []
        by_column: Dict[str, FieldIR] = {}

        logic_delete_count = 0
        for field_index, field_cfg in enumerate(table_cfg["fields"]):
            field_path = f"{table_path}.fields[{field_index}]"
            column_name = field_cfg["name"]
            property_name = snake_to_camel(column_name)
            java_type = db_to_java(field_cfg["type"])
            logic_delete = bool(field_cfg.get("logicDelete", False))
            if logic_delete:
                logic_delete_count += 1

            field_frontend_cfg = field_cfg.get("frontend", {})
            dict_key = field_cfg.get("dictKey")
            dict_value_type = None
            if dict_key is not None:
                dict_key = str(dict_key).strip()
                dictionary = dictionary_by_key.get(dict_key)
                if dictionary is None:
                    issues.append(
                        ParseIssue(
                            path=f"{field_path}.dictKey",
                            message=f"unknown dictionary '{dict_key}'",
                        )
                    )
                else:
                    dict_value_type = dictionary.value_type
                    expected_java_type = DICT_VALUE_TYPE_TO_JAVA[dictionary.value_type]
                    if java_type != expected_java_type:
                        issues.append(
                            ParseIssue(
                                path=f"{field_path}.dictKey",
                                message=(
                                    f"dictionary '{dict_key}' expects Java type "
                                    f"'{expected_java_type}', got '{java_type}'"
                                ),
                            )
                        )
                if "options" in field_frontend_cfg:
                    issues.append(
                        ParseIssue(
                            path=f"{field_path}.frontend.options",
                            message="cannot be used together with dictKey",
                        )
                    )
            field_frontend = FieldFrontendIR(
                label=field_frontend_cfg.get("label", ""),
                component=field_frontend_cfg.get("component", ""),
                query_component=field_frontend_cfg.get("queryComponent", ""),
                table_visible=bool(field_frontend_cfg.get("tableVisible", True)),
                form_visible=bool(field_frontend_cfg.get("formVisible", True)),
                detail_visible=bool(field_frontend_cfg.get("detailVisible", True)),
                query_visible=bool(field_frontend_cfg.get("queryVisible", True)),
                placeholder=field_frontend_cfg.get("placeholder", ""),
                options=[
                    FrontendOptionIR(label=item["label"], value=item["value"])
                    for item in field_frontend_cfg.get("options", [])
                ],
            )

            field_ir = FieldIR(
                column_name=column_name,
                property_name=property_name,
                java_type=java_type,
                db_type=field_cfg["type"],
                nullable=bool(field_cfg["nullable"]),
                comment=field_cfg.get("comment", ""),
                unique=bool(field_cfg.get("unique", False)),
                logic_delete=logic_delete,
                auto_fill=field_cfg.get("autoFill"),
                id_type=field_cfg.get("idType"),
                is_primary=False,
                dict_key=dict_key if dict_key else None,
                dict_value_type=dict_value_type,
                frontend=field_frontend,
            )
            fields.append(field_ir)

            if column_name in by_column:
                issues.append(
                    ParseIssue(
                        path=f"{field_path}.name",
                        message=f"duplicated field '{column_name}'",
                    )
                )
            else:
                by_column[column_name] = field_ir

        if logic_delete_count > 1:
            issues.append(
                ParseIssue(
                    path=table_path,
                    message="at most one logicDelete field is allowed per table",
                )
            )

        primary_key = table_cfg["primaryKey"]
        if primary_key not in by_column:
            issues.append(
                ParseIssue(
                    path=f"{table_path}.primaryKey",
                    message=f"primary key '{primary_key}' does not exist in fields",
                )
            )
            continue

        primary_field = by_column[primary_key]
        primary_field.is_primary = True

        queryable_fields: List[QueryableFieldIR] = []
        for query_index, query_cfg in enumerate(table_cfg["queryableFields"]):
            query_path = f"{table_path}.queryableFields[{query_index}]"
            if isinstance(query_cfg, str):
                field_name = query_cfg
                operator = "EQ"
            else:
                field_name = query_cfg["name"]
                operator = query_cfg.get("operator", "EQ")

            if field_name not in by_column:
                issues.append(
                    ParseIssue(
                        path=query_path,
                        message=f"query field '{field_name}' does not exist in table fields",
                    )
                )
                continue

            selected_field = by_column[field_name]
            operator_issue = _validate_operator_support(
                selected_field.java_type, operator
            )
            if operator_issue:
                issues.append(ParseIssue(path=query_path, message=operator_issue))
                continue

            queryable_fields.append(
                QueryableFieldIR(
                    property_name=selected_field.property_name,
                    column_name=selected_field.column_name,
                    java_type=selected_field.java_type,
                    operator=operator,
                )
            )

        seed_data: List[Dict[str, Any]] = []
        for seed_index, seed_row in enumerate(table_cfg.get("seedData", [])):
            seed_path = f"{table_path}.seedData[{seed_index}]"
            unknown_columns = [
                column_name for column_name in seed_row if column_name not in by_column
            ]
            if unknown_columns:
                for column_name in unknown_columns:
                    issues.append(
                        ParseIssue(
                            path=f"{seed_path}.{column_name}",
                            message=f"seed field '{column_name}' does not exist in table fields",
                        )
                    )
                continue
            seed_data.append(dict(seed_row))

        auth_cfg = table_cfg.get("auth")
        table_auth_ir = None
        if auth_cfg is not None:
            permissions_cfg = auth_cfg.get("permissions", {})
            table_auth_ir = TableAuthIR(
                enabled=bool(auth_cfg.get("enabled", True)),
                roles=_normalize_role_list(
                    list(auth_cfg.get("roles", [])),
                    f"{table_path}.auth.roles",
                    issues,
                ),
                permissions=PermissionIR(
                    query=permissions_cfg.get("query"),
                    create=permissions_cfg.get("create"),
                    update=permissions_cfg.get("update"),
                    delete=permissions_cfg.get("delete"),
                )
            )
        elif security_ir.enabled:
            table_auth_ir = TableAuthIR(
                enabled=True,
                roles=[],
                permissions=PermissionIR(
                    query=f"{table_name}:view",
                    create=f"{table_name}:add",
                    update=f"{table_name}:edit",
                    delete=f"{table_name}:delete",
                )
            )

        table_ir = TableIR(
            name=table_name,
            comment=table_cfg.get("comment", ""),
            entity_name=entity_name,
            object_name=object_name,
            resource_name=table_name.lower(),
            primary_key_property=primary_field.property_name,
            primary_key_column=primary_field.column_name,
            primary_key_java_type=primary_field.java_type,
            fields=fields,
            queryable_fields=queryable_fields,
            seed_data=seed_data,
            infer_indexes=bool(table_cfg.get("inferIndexes", True)),
            infer_foreign_keys=bool(table_cfg.get("inferForeignKeys", True)),
            frontend=TableFrontendIR(
                menu_title=table_cfg.get("frontend", {}).get("menuTitle", ""),
                menu_icon=table_cfg.get("frontend", {}).get(
                    "menuIcon", "el-icon-document"
                ),
                menu_visible=bool(
                    table_cfg.get("frontend", {}).get("menuVisible", True)
                ),
            ),
            auth=table_auth_ir,
        )

        table_map[table_name] = table_ir
        tables.append(table_ir)

    for table_index, table_cfg in enumerate(payload["tables"]):
        table_path = f"tables[{table_index}]"
        table_name = table_cfg["name"]
        table_ir = table_map.get(table_name)
        if table_ir is None:
            continue

        by_column = {field.column_name: field for field in table_ir.fields}

        sortable_fields: List[SortableFieldIR] = []
        seen_sort_names: set[str] = set()
        for sort_index, sort_field_name in enumerate(
            table_cfg.get("sortableFields", [])
        ):
            sort_path = f"{table_path}.sortableFields[{sort_index}]"
            if sort_field_name not in by_column:
                issues.append(
                    ParseIssue(
                        path=sort_path,
                        message=f"sortable field '{sort_field_name}' does not exist in table fields",
                    )
                )
                continue

            source_field = by_column[sort_field_name]
            request_name = source_field.property_name
            if request_name in seen_sort_names:
                issues.append(
                    ParseIssue(
                        path=sort_path,
                        message=f"duplicated sortable field '{request_name}'",
                    )
                )
                continue
            seen_sort_names.add(request_name)
            sortable_fields.append(
                SortableFieldIR(
                    request_name=request_name,
                    column_name=source_field.column_name,
                    property_name=source_field.property_name,
                    java_type=source_field.java_type,
                )
            )

        indexes: List[IndexIR] = []
        seen_index_names: set[str] = set()
        for index_pos, index_cfg in enumerate(table_cfg.get("indexes", [])):
            index_path = f"{table_path}.indexes[{index_pos}]"
            index_columns = index_cfg["columns"]
            missing_columns = [
                column_name
                for column_name in index_columns
                if column_name not in by_column
            ]
            if missing_columns:
                for column_name in missing_columns:
                    issues.append(
                        ParseIssue(
                            path=f"{index_path}.columns",
                            message=f"index field '{column_name}' does not exist in table fields",
                        )
                    )
                continue

            unique = bool(index_cfg.get("unique", False))
            default_prefix = "uk" if unique else "idx"
            default_name = f"{default_prefix}_{table_name}_{'_'.join(index_columns)}"
            index_name = index_cfg.get("name") or default_name
            if index_name in seen_index_names:
                issues.append(
                    ParseIssue(
                        path=f"{index_path}.name",
                        message=f"duplicated index name '{index_name}'",
                    )
                )
                continue
            seen_index_names.add(index_name)
            indexes.append(
                IndexIR(name=index_name, columns=list(index_columns), unique=unique)
            )

        foreign_keys: List[ForeignKeyIR] = []
        seen_foreign_key_names: set[str] = set()
        for foreign_key_index, foreign_key_cfg in enumerate(
            table_cfg.get("foreignKeys", [])
        ):
            foreign_key_path = f"{table_path}.foreignKeys[{foreign_key_index}]"
            columns = foreign_key_cfg["columns"]
            ref_table_name = foreign_key_cfg["refTable"]
            ref_columns = foreign_key_cfg["refColumns"]

            if len(columns) != len(ref_columns):
                issues.append(
                    ParseIssue(
                        path=foreign_key_path,
                        message="foreign key columns and refColumns must have the same length",
                    )
                )
                continue

            missing_columns = [
                column_name for column_name in columns if column_name not in by_column
            ]
            if missing_columns:
                for column_name in missing_columns:
                    issues.append(
                        ParseIssue(
                            path=f"{foreign_key_path}.columns",
                            message=f"foreign key field '{column_name}' does not exist in table fields",
                        )
                    )
                continue

            if ref_table_name not in table_map:
                issues.append(
                    ParseIssue(
                        path=f"{foreign_key_path}.refTable",
                        message=f"unknown referenced table '{ref_table_name}'",
                    )
                )
                continue

            ref_table = table_map[ref_table_name]
            ref_field_map = {field.column_name: field for field in ref_table.fields}
            missing_ref_columns = [
                column_name
                for column_name in ref_columns
                if column_name not in ref_field_map
            ]
            if missing_ref_columns:
                for column_name in missing_ref_columns:
                    issues.append(
                        ParseIssue(
                            path=f"{foreign_key_path}.refColumns",
                            message=f"foreign key referenced field '{column_name}' does not exist in table '{ref_table_name}'",
                        )
                    )
                continue

            default_name = f"fk_{table_name}_{ref_table_name}_{'_'.join(columns)}"
            foreign_key_name = foreign_key_cfg.get("name") or default_name
            if foreign_key_name in seen_foreign_key_names:
                issues.append(
                    ParseIssue(
                        path=f"{foreign_key_path}.name",
                        message=f"duplicated foreign key name '{foreign_key_name}'",
                    )
                )
                continue
            seen_foreign_key_names.add(foreign_key_name)
            foreign_keys.append(
                ForeignKeyIR(
                    name=foreign_key_name,
                    columns=list(columns),
                    ref_table=ref_table_name,
                    ref_columns=list(ref_columns),
                    on_delete=foreign_key_cfg.get("onDelete"),
                    on_update=foreign_key_cfg.get("onUpdate"),
                )
            )

        table_ir.sortable_fields = sortable_fields
        table_ir.indexes = indexes
        table_ir.foreign_keys = foreign_keys

    relations: List[RelationIR] = []
    relation_names: set[str] = set()
    relation_dto_names: set[str] = set()
    relation_query_names: set[str] = set()
    relation_methods_by_table: Dict[str, set[str]] = {}
    for relation_index, relation_cfg in enumerate(payload["relations"]):
        relation_path = f"relations[{relation_index}]"
        left_table = relation_cfg["leftTable"]
        right_table = relation_cfg["rightTable"]

        if left_table not in table_map:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.leftTable",
                    message=f"unknown table '{left_table}'",
                )
            )
            continue
        if right_table not in table_map:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.rightTable",
                    message=f"unknown table '{right_table}'",
                )
            )
            continue

        left_table_ir = table_map[left_table]
        right_table_ir = table_map[right_table]

        left_fields = {field.column_name: field for field in left_table_ir.fields}
        right_fields = {field.column_name: field for field in right_table_ir.fields}

        relation_on: List[RelationOnIR] = []
        for on_index, on_cfg in enumerate(relation_cfg["on"]):
            on_path = f"{relation_path}.on[{on_index}]"
            left_field = on_cfg["leftField"]
            right_field = on_cfg["rightField"]

            if left_field not in left_fields:
                issues.append(
                    ParseIssue(
                        path=f"{on_path}.leftField",
                        message=f"unknown field '{left_field}' in left table",
                    )
                )
                continue
            if right_field not in right_fields:
                issues.append(
                    ParseIssue(
                        path=f"{on_path}.rightField",
                        message=f"unknown field '{right_field}' in right table",
                    )
                )
                continue

            relation_on.append(
                RelationOnIR(left_column=left_field, right_column=right_field)
            )

        relation_select: List[RelationSelectIR] = []
        for select_index, select_cfg in enumerate(relation_cfg["select"]):
            select_path = f"{relation_path}.select[{select_index}]"
            side_name = select_cfg["table"]
            field_name = select_cfg["field"]

            side = _resolve_relation_side(side_name, left_table, right_table)
            if side is None:
                issues.append(
                    ParseIssue(
                        path=f"{select_path}.table",
                        message=f"must be one of: left, right, {left_table}, {right_table}",
                    )
                )
                continue

            source_map = left_fields if side == "left" else right_fields
            if field_name not in source_map:
                issues.append(
                    ParseIssue(
                        path=f"{select_path}.field",
                        message=f"unknown field '{field_name}' in {side} table",
                    )
                )
                continue

            source_field = source_map[field_name]
            alias = select_cfg.get("alias") or source_field.property_name

            relation_select.append(
                RelationSelectIR(
                    side=side,
                    column_name=source_field.column_name,
                    property_name=source_field.property_name,
                    java_type=source_field.java_type,
                    alias=alias,
                )
            )

        relation_filters: List[RelationFilterIR] = []
        seen_params: set[str] = set()
        for filter_index, filter_cfg in enumerate(relation_cfg["filters"]):
            filter_path = f"{relation_path}.filters[{filter_index}]"
            side_name = filter_cfg["table"]
            field_name = filter_cfg["field"]
            operator = filter_cfg["operator"]
            param_name = filter_cfg["param"]

            side = _resolve_relation_side(side_name, left_table, right_table)
            if side is None:
                issues.append(
                    ParseIssue(
                        path=f"{filter_path}.table",
                        message=f"must be one of: left, right, {left_table}, {right_table}",
                    )
                )
                continue

            source_map = left_fields if side == "left" else right_fields
            if field_name not in source_map:
                issues.append(
                    ParseIssue(
                        path=f"{filter_path}.field",
                        message=f"unknown field '{field_name}' in {side} table",
                    )
                )
                continue

            source_field = source_map[field_name]
            operator_issue = _validate_operator_support(
                source_field.java_type, operator
            )
            if operator_issue:
                issues.append(
                    ParseIssue(
                        path=filter_path,
                        message=operator_issue,
                    )
                )
                continue

            normalized_param_name = snake_to_camel(param_name)
            if normalized_param_name in seen_params:
                issues.append(
                    ParseIssue(
                        path=f"{filter_path}.param",
                        message=f"duplicated param '{normalized_param_name}'",
                    )
                )
                continue
            seen_params.add(normalized_param_name)

            relation_filters.append(
                RelationFilterIR(
                    side=side,
                    column_name=source_field.column_name,
                    property_name=source_field.property_name,
                    java_type=source_field.java_type,
                    operator=operator,
                    param_name=normalized_param_name,
                    is_string=source_field.java_type == "String",
                )
            )

        relation_sortable_fields: List[SortableFieldIR] = []
        seen_relation_sort_names: set[str] = set()
        for sort_index, sort_cfg in enumerate(relation_cfg.get("sortableFields", [])):
            sort_path = f"{relation_path}.sortableFields[{sort_index}]"
            side_name = sort_cfg["table"]
            field_name = sort_cfg["field"]

            side = _resolve_relation_side(side_name, left_table, right_table)
            if side is None:
                issues.append(
                    ParseIssue(
                        path=f"{sort_path}.table",
                        message=f"must be one of: left, right, {left_table}, {right_table}",
                    )
                )
                continue

            source_map = left_fields if side == "left" else right_fields
            if field_name not in source_map:
                issues.append(
                    ParseIssue(
                        path=f"{sort_path}.field",
                        message=f"unknown field '{field_name}' in {side} table",
                    )
                )
                continue

            source_field = source_map[field_name]
            request_name = snake_to_camel(
                sort_cfg.get("name") or source_field.property_name
            )
            if request_name in seen_relation_sort_names:
                issues.append(
                    ParseIssue(
                        path=f"{sort_path}.name",
                        message=f"duplicated sortable field '{request_name}'",
                    )
                )
                continue
            seen_relation_sort_names.add(request_name)
            relation_sortable_fields.append(
                SortableFieldIR(
                    request_name=request_name,
                    column_name=source_field.column_name,
                    property_name=source_field.property_name,
                    java_type=source_field.java_type,
                    side=side,
                )
            )

        if not relation_on:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.on",
                    message="at least one valid ON clause is required",
                )
            )
            continue
        if not relation_select:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.select",
                    message="at least one valid select field is required",
                )
            )
            continue

        query_name = f"{relation_cfg['methodName'][:1].upper()}{relation_cfg['methodName'][1:]}Query"
        relation_name = relation_cfg["name"]
        method_name = relation_cfg["methodName"]
        dto_name = relation_cfg["dtoName"]

        if not _is_valid_java_identifier(method_name):
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.methodName",
                    message="invalid Java method name",
                )
            )
            continue
        if not _is_valid_java_identifier(dto_name):
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.dtoName", message="invalid Java class name"
                )
            )
            continue
        if not _is_valid_java_identifier(query_name):
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.methodName",
                    message="invalid generated query class name",
                )
            )
            continue

        if relation_name in relation_names:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.name",
                    message=f"duplicated relation name '{relation_name}'",
                )
            )
            continue
        relation_names.add(relation_name)

        if dto_name in relation_dto_names:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.dtoName",
                    message=f"duplicated relation dto '{dto_name}'",
                )
            )
            continue
        relation_dto_names.add(dto_name)

        if query_name in relation_query_names:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.methodName",
                    message=f"duplicated relation query type '{query_name}'",
                )
            )
            continue
        relation_query_names.add(query_name)

        left_methods = relation_methods_by_table.setdefault(left_table, set())
        if method_name in left_methods:
            issues.append(
                ParseIssue(
                    path=f"{relation_path}.methodName",
                    message=f"duplicated mapper method '{method_name}' for table '{left_table}'",
                )
            )
            continue
        left_methods.add(method_name)

        auth_cfg = relation_cfg.get("auth")
        relation_auth_ir = None
        if auth_cfg is not None:
            relation_auth_ir = TableAuthIR(
                enabled=bool(auth_cfg.get("enabled", True)),
                roles=_normalize_role_list(
                    list(auth_cfg.get("roles", [])),
                    f"{relation_path}.auth.roles",
                    issues,
                ),
                permissions=PermissionIR()
            )
        elif security_ir.enabled:
            relation_auth_ir = TableAuthIR(
                enabled=True,
                roles=[],
                permissions=PermissionIR(query=f"{relation_name}:view")
            )

        relation_ir = RelationIR(
            name=relation_name,
            left_table=left_table,
            right_table=right_table,
            left_entity_name=left_table_ir.entity_name,
            join_type=relation_cfg["joinType"],
            dto_name=dto_name,
            method_name=method_name,
            query_name=query_name,
            select_items=relation_select,
            filters=relation_filters,
            sortable_fields=relation_sortable_fields,
            on_clauses=relation_on,
            frontend=RelationFrontendIR(
                menu_title=relation_cfg.get("frontend", {}).get("menuTitle", ""),
                menu_icon=relation_cfg.get("frontend", {}).get(
                    "menuIcon", "el-icon-connection"
                ),
                menu_visible=bool(
                    relation_cfg.get("frontend", {}).get("menuVisible", True)
                ),
            ),
            auth=relation_auth_ir,
        )
        relations.append(relation_ir)

    if security_ir.enabled:
        _ensure_rbac_seed_data(tables, relations, security_ir.rbac)
    if dictionaries_ir:
        _ensure_dictionary_seed_data(tables, dictionaries_ir)

    if issues:
        raise ConfigError(issues)

    normalized_datasource = {
        "url": str(datasource_cfg["url"]),
        "databaseName": str(
            datasource_cfg.get("databaseName")
            or _database_name_from_url(datasource_cfg["url"])
            or ""
        ),
        "username": str(datasource_cfg["username"]),
        "password": str(datasource_cfg["password"]),
        "driverClassName": str(datasource_cfg["driverClassName"]),
    }

    project_ir = ProjectIR(
        group_id=project_cfg["groupId"],
        artifact_id=project_cfg["artifactId"],
        name=project_cfg["name"],
        base_package=project_cfg["basePackage"],
        boot_version=project_cfg["bootVersion"],
        java_version=str(project_cfg["javaVersion"]),
        datasource=normalized_datasource,
        api_prefix=global_cfg.get("apiPrefix", "/api"),
        author=global_cfg.get("author", ""),
        date_time_format=global_cfg.get("dateTimeFormat", "yyyy-MM-dd HH:mm:ss"),
        enable_swagger=bool(global_cfg.get("enableSwagger", False)),
        application_name=project_cfg["name"],
        tenant=TenantIR(
            enabled=bool(global_cfg.get("tenant", {}).get("enabled", False)),
            column=str(global_cfg.get("tenant", {}).get("column", "tenant_id")),
        ),
        security=security_ir,
        backend=BackendIR(
            output_dir=backend_cfg.get("outputDir", "backend"),
            upload_dir=backend_cfg.get("uploadDir", "uploads"),
        ),
        frontend=FrontendIR(
            enabled=bool(frontend_cfg.get("enabled", False)),
            framework=frontend_cfg.get("framework", "vue2"),
            locale=frontend_cfg.get("locale", "zh-CN"),
            output_dir=frontend_cfg.get("outputDir", "frontend"),
            app_title=frontend_cfg.get("appTitle") or project_cfg["name"],
            backend_url=frontend_cfg.get("backendUrl", "http://127.0.0.1:8080"),
            dev_port=int(frontend_cfg.get("devPort", 8081)),
        ),
        dictionaries=dictionaries_ir,
        tables=tables,
        relations=relations,
    )
    return project_ir


def _resolve_relation_side(
    side_name: str, left_table: str, right_table: str
) -> str | None:
    lowered = side_name.lower()
    if lowered in {"left", left_table.lower()}:
        return "left"
    if lowered in {"right", right_table.lower()}:
        return "right"
    return None


def _database_name_from_url(datasource_url: str) -> str | None:
    match = re.search(r"jdbc:[^:]+://[^/]+/([^?;]+)", datasource_url)
    if not match:
        return None
    database_name = match.group(1).strip()
    return database_name or None


def _validate_operator_support(java_type: str, operator: str) -> str | None:
    if operator == "LIKE" and java_type != "String":
        return "LIKE operator only supports String fields"
    if operator in RANGE_OPERATORS and java_type not in {
        "Long",
        "Integer",
        "Double",
        "BigDecimal",
        "LocalDate",
        "LocalDateTime",
    }:
        return f"{operator} operator only supports numeric or date/time fields"
    return None


def _is_valid_package(package_name: str) -> bool:
    return (
        re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*", package_name)
        is not None
    )


def _is_valid_java_identifier(name: str) -> bool:
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None


def _inject_rbac_tables(payload: Dict[str, Any], rbac_config: RbacConfigIR) -> None:
    existing_tables = {t["name"] for t in payload.get("tables", [])}
    rbac_tables = []
    
    if "sys_user" not in existing_tables:
        rbac_tables.append({
            "name": "sys_user",
            "comment": "System User",
            "entityName": "SysUser",
            "primaryKey": "id",
            "queryableFields": [
                {"name": "username", "operator": "LIKE"}
            ],
            "fields": [
                {"name": "id", "type": "bigint", "nullable": False, "idType": "AUTO", "comment": "ID"},
                {"name": "username", "type": "varchar(64)", "nullable": False, "unique": True, "comment": "Username"},
                {"name": "password", "type": "varchar(255)", "nullable": False, "comment": "Password"},
                {"name": "enabled", "type": "tinyint(1)", "nullable": False, "comment": "Enabled status"},
                {"name": "created_at", "type": "datetime", "nullable": False, "autoFill": "INSERT", "comment": "Created Time"}
            ],
            "seedData": [
                {"id": 1, "username": "admin", "password": "$2y$10$6nO2SjLp7N7EoenOqL8bgOHwNHF9h3Gq8rivStyFnx/SnwbBSfcBa", "enabled": True, "created_at": "2024-01-01 00:00:00"}
            ]
        })
    if "sys_role" not in existing_tables:
        rbac_tables.append({
            "name": "sys_role",
            "comment": "System Role",
            "entityName": "SysRole",
            "primaryKey": "id",
            "queryableFields": [{"name": "role_code", "operator": "EQ"}],
            "fields": [
                {"name": "id", "type": "bigint", "nullable": False, "idType": "AUTO", "comment": "ID"},
                {"name": "role_name", "type": "varchar(64)", "nullable": False, "comment": "Role Name"},
                {"name": "role_code", "type": "varchar(64)", "nullable": False, "unique": True, "comment": "Role Code"},
                {"name": "created_at", "type": "datetime", "nullable": False, "autoFill": "INSERT", "comment": "Created Time"}
            ],
            "seedData": [
                {"id": 1, "role_name": "Administrator", "role_code": rbac_config.super_admin_role, "created_at": "2024-01-01 00:00:00"}
            ]
        })
    if "sys_user_role" not in existing_tables:
        rbac_tables.append({
            "name": "sys_user_role",
            "comment": "User Role Mapping",
            "entityName": "SysUserRole",
            "primaryKey": "id",
            "queryableFields": [{"name": "user_id", "operator": "EQ"}],
            "fields": [
                {"name": "id", "type": "bigint", "nullable": False, "idType": "AUTO", "comment": "ID"},
                {"name": "user_id", "type": "bigint", "nullable": False, "comment": "User ID"},
                {"name": "role_id", "type": "bigint", "nullable": False, "comment": "Role ID"}
            ],
            "seedData": [
                {"id": 1, "user_id": 1, "role_id": 1}
            ]
        })
    if "sys_menu_permission" not in existing_tables:
        rbac_tables.append({
            "name": "sys_menu_permission",
            "comment": "Menu and Permission",
            "entityName": "SysMenuPermission",
            "primaryKey": "id",
            "queryableFields": [{"name": "parent_id", "operator": "EQ"}],
            "fields": [
                {"name": "id", "type": "bigint", "nullable": False, "idType": "AUTO", "comment": "ID"},
                {"name": "parent_id", "type": "bigint", "nullable": False, "comment": "Parent ID"},
                {"name": "name", "type": "varchar(64)", "nullable": False, "comment": "Name"},
                {"name": "permission_str", "type": "varchar(128)", "nullable": True, "comment": "Permission String"},
                {"name": "type", "type": "tinyint", "nullable": False, "comment": "1:Menu 2:Button"},
                {"name": "path", "type": "varchar(255)", "nullable": True, "comment": "Route Path"}
            ]
        })
    if "sys_role_permission" not in existing_tables:
        rbac_tables.append({
            "name": "sys_role_permission",
            "comment": "Role Permission Mapping",
            "entityName": "SysRolePermission",
            "primaryKey": "id",
            "queryableFields": [{"name": "role_id", "operator": "EQ"}],
            "fields": [
                {"name": "id", "type": "bigint", "nullable": False, "idType": "AUTO", "comment": "ID"},
                {"name": "role_id", "type": "bigint", "nullable": False, "comment": "Role ID"},
                {"name": "permission_id", "type": "bigint", "nullable": False, "comment": "Permission ID"}
            ]
        })

    payload["tables"] = rbac_tables + payload.get("tables", [])
