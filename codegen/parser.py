from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .ir import (
    BackendIR,
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


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
        )
        relations.append(relation_ir)

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
        backend=BackendIR(
            output_dir=backend_cfg.get("outputDir", "backend"),
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
