from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Dict, Iterable, List, cast

from jinja2 import Environment, FileSystemLoader

from .ir import (
    FieldIR,
    ForeignKeyIR,
    IndexIR,
    ProjectIR,
    QueryableFieldIR,
    RelationFilterIR,
    RelationIR,
    SortableFieldIR,
    TableIR,
)
from .type_mapping import db_type_length, java_import, snake_to_camel, snake_to_pascal

TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates"

ANNOTATION_IMPORTS = {
    "Max": "javax.validation.constraints.Max",
    "Min": "javax.validation.constraints.Min",
    "NotBlank": "javax.validation.constraints.NotBlank",
    "NotNull": "javax.validation.constraints.NotNull",
    "Pattern": "javax.validation.constraints.Pattern",
    "Size": "javax.validation.constraints.Size",
}

FRONTEND_MESSAGES = {
    "zh-CN": {
        "html_lang": "zh-CN",
        "dashboard_title": "仪表盘",
        "layout_brand_subtitle": "Vue2 管理工作台",
        "layout_caption": "已为 {artifact_id} 生成经典管理后台界面",
        "menu_group_data": "数据管理",
        "menu_group_relations": "关联视图",
        "dashboard_hero_subtitle": "已连接 Spring Boot CRUD 后端的 Vue2 管理工作台。",
        "dashboard_card_data_title": "数据模块",
        "dashboard_card_data_description": "已生成的 CRUD 页面",
        "dashboard_card_relations_title": "关联视图",
        "dashboard_card_relations_description": "已生成的联表查询页面",
        "dashboard_quick_nav_title": "快速导航",
        "dashboard_quick_nav_description": "打开已生成的数据模块与关联查询页面。",
        "table_subtitle": "管理{table_title}的 CRUD 页面与数据记录。",
        "table_toolbar_description": "支持查询、排序、新增、编辑与查看生成的数据记录。",
        "relation_subtitle": "查看{left_title}与{right_title}的联表查询结果。",
        "relation_toolbar_description": "只读联表视图，底层 SQL 由生成器自动生成。",
        "button_new": "新增",
        "button_search": "查询",
        "button_reset": "重置",
        "button_detail": "详情",
        "button_edit": "编辑",
        "button_delete": "删除",
        "button_cancel": "取消",
        "button_save": "保存",
        "table_actions": "操作",
        "sort_by": "排序字段",
        "sort_by_placeholder": "请选择排序字段",
        "sort_direction": "排序方向",
        "sort_direction_placeholder": "请选择排序方向",
        "sort_ascending": "升序",
        "sort_descending": "降序",
        "dialog_detail_title": "记录详情",
        "dialog_new_title": "新增{title}",
        "dialog_edit_title": "编辑{title}",
        "message_created": "创建成功",
        "message_updated": "更新成功",
        "message_deleted": "删除成功",
        "confirm_delete": "确认删除当前记录吗？",
        "confirm_warning_title": "提示",
        "boolean_yes": "是",
        "boolean_no": "否",
        "placeholder_enter": "请输入{label}",
        "placeholder_select": "请选择{label}",
        "request_empty_response": "服务端返回了空响应",
        "request_failed": "请求失败",
        "request_network_failed": "网络请求失败",
        "no_script": "此页面需要启用 JavaScript 才能运行。",
        "untitled": "未命名",
    },
    "en-US": {
        "html_lang": "en-US",
        "dashboard_title": "Dashboard",
        "layout_brand_subtitle": "Vue2 Admin Workspace",
        "layout_caption": "Generated classic management frontend for {artifact_id}",
        "menu_group_data": "Data Management",
        "menu_group_relations": "Relation Views",
        "dashboard_hero_subtitle": "Generated Vue2 admin workspace connected to the Spring Boot CRUD backend.",
        "dashboard_card_data_title": "Data Modules",
        "dashboard_card_data_description": "Generated CRUD pages",
        "dashboard_card_relations_title": "Relation Views",
        "dashboard_card_relations_description": "Generated join query pages",
        "dashboard_quick_nav_title": "Quick Navigation",
        "dashboard_quick_nav_description": "Open generated modules and relation query pages.",
        "table_subtitle": "Manage {table_title} records with generated CRUD views.",
        "table_toolbar_description": "Search, sort, create, edit, and inspect generated records.",
        "relation_subtitle": "Browse generated join results for {left_title} and {right_title}.",
        "relation_toolbar_description": "Read-only relation view backed by generated join SQL.",
        "button_new": "New",
        "button_search": "Search",
        "button_reset": "Reset",
        "button_detail": "Detail",
        "button_edit": "Edit",
        "button_delete": "Delete",
        "button_cancel": "Cancel",
        "button_save": "Save",
        "table_actions": "Actions",
        "sort_by": "Sort By",
        "sort_by_placeholder": "Select sort field",
        "sort_direction": "Direction",
        "sort_direction_placeholder": "Select direction",
        "sort_ascending": "Ascending",
        "sort_descending": "Descending",
        "dialog_detail_title": "Record Detail",
        "dialog_new_title": "New {title}",
        "dialog_edit_title": "Edit {title}",
        "message_created": "Created successfully",
        "message_updated": "Updated successfully",
        "message_deleted": "Deleted successfully",
        "confirm_delete": "Delete the selected record?",
        "confirm_warning_title": "Warning",
        "boolean_yes": "Yes",
        "boolean_no": "No",
        "placeholder_enter": "Enter {label}",
        "placeholder_select": "Select {label}",
        "request_empty_response": "Empty response received",
        "request_failed": "Request failed",
        "request_network_failed": "Network request failed",
        "no_script": "This frontend requires JavaScript to run.",
        "untitled": "Untitled",
    },
}


class CodeRenderer:
    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_ROOT)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render_project(self, project: ProjectIR) -> Dict[str, str]:
        files: Dict[str, str] = {}
        backend_root = project.backend.output_dir.strip("/") or "backend"
        java_root = f"{backend_root}/src/main/java/{project.base_package_path}"
        resource_root = f"{backend_root}/src/main/resources"

        base_context = {
            "project": project,
            "package": project.base_package,
            "datasource_placeholders": self._datasource_placeholders(project),
            "insert_fill_fields": self._auto_fill_fields(project, mode="insert"),
            "update_fill_fields": self._auto_fill_fields(project, mode="update"),
            "auto_fill_imports": self._auto_fill_imports(project),
        }

        files[f"{backend_root}/pom.xml"] = self._render("pom.xml.j2", **base_context)
        files[f"{resource_root}/application.yml"] = self._render(
            "resources/application.yml.j2", **base_context
        )
        files[f"{resource_root}/init.sql"] = self._render_init_sql(project)
        files[f"{java_root}/{project.application_class_name}.java"] = self._render(
            "app/Application.java.j2", **base_context
        )
        files[f"{java_root}/config/MybatisPlusConfig.java"] = self._render(
            "config/MybatisPlusConfig.java.j2", **base_context
        )
        files[f"{java_root}/config/MybatisMetaObjectHandler.java"] = self._render(
            "config/MybatisMetaObjectHandler.java.j2", **base_context
        )
        files[f"{java_root}/common/Result.java"] = self._render(
            "common/Result.java.j2", **base_context
        )
        files[f"{java_root}/common/ErrorCode.java"] = self._render(
            "common/ErrorCode.java.j2", **base_context
        )
        files[f"{java_root}/common/PageResult.java"] = self._render(
            "common/PageResult.java.j2", **base_context
        )
        files[f"{java_root}/exception/BizException.java"] = self._render(
            "exception/BizException.java.j2", **base_context
        )
        files[f"{java_root}/exception/NotFoundException.java"] = self._render(
            "exception/NotFoundException.java.j2", **base_context
        )
        files[f"{java_root}/exception/GlobalExceptionHandler.java"] = self._render(
            "common/GlobalExceptionHandler.java.j2", **base_context
        )

        relation_groups = self._group_relations(project.relations)

        for table in project.tables:
            table_relations = relation_groups.get(table.name, [])
            create_dto_fields = self._request_dto_fields(table, mode="create")
            update_dto_fields = self._request_dto_fields(table, mode="update")
            query_dto_fields = self._query_dto_fields(
                table.queryable_fields,
                table.sortable_fields,
            )
            sortable_fields = [
                self._sortable_field_context(item) for item in table.sortable_fields
            ]
            table_context = {
                **base_context,
                "table": table,
                "table_relations": table_relations,
                "entity_imports": self._java_imports(
                    field.java_type for field in table.fields
                ),
                "query_fields": self._query_field_contexts(table.queryable_fields),
                "sortable_fields": sortable_fields,
                "has_sorting": bool(sortable_fields),
                "relation_methods": [
                    {
                        "method_name": relation.method_name,
                        "dto_name": relation.dto_name,
                        "query_name": relation.query_name,
                        "endpoint_name": relation.name,
                    }
                    for relation in table_relations
                ],
                "mapper_relation_context": [
                    self._relation_mapper_context(relation)
                    for relation in table_relations
                ],
            }

            files[f"{java_root}/entity/{table.entity_name}.java"] = self._render(
                "entity/Entity.java.j2", **table_context
            )
            files[f"{java_root}/mapper/{table.mapper_name}.java"] = self._render(
                "mapper/Mapper.java.j2", **table_context
            )
            files[f"{resource_root}/mapper/{table.mapper_name}.xml"] = self._render(
                "mapper/Mapper.xml.j2", **table_context
            )
            files[f"{java_root}/service/{table.service_name}.java"] = self._render(
                "service/Service.java.j2", **table_context
            )
            files[f"{java_root}/service/impl/{table.service_impl_name}.java"] = (
                self._render("service_impl/ServiceImpl.java.j2", **table_context)
            )
            files[f"{java_root}/controller/{table.controller_name}.java"] = (
                self._render("controller/Controller.java.j2", **table_context)
            )
            files[f"{java_root}/dto/{table.create_dto_name}.java"] = self._render(
                "dto/CreateRequest.java.j2",
                **table_context,
                dto_name=table.create_dto_name,
                dto_fields=create_dto_fields,
                dto_imports=self._dto_imports(create_dto_fields),
            )
            files[f"{java_root}/dto/{table.update_dto_name}.java"] = self._render(
                "dto/UpdateRequest.java.j2",
                **table_context,
                dto_name=table.update_dto_name,
                dto_fields=update_dto_fields,
                dto_imports=self._dto_imports(update_dto_fields),
            )
            files[f"{java_root}/dto/{table.query_dto_name}.java"] = self._render(
                "dto/QueryRequest.java.j2",
                **table_context,
                dto_name=table.query_dto_name,
                dto_fields=query_dto_fields,
                dto_imports=self._dto_imports(query_dto_fields),
            )

        for relation in project.relations:
            relation_query_fields = self._relation_query_dto_fields(relation)
            relation_context = {
                **base_context,
                "relation": relation,
                "dto_imports": self._java_imports(
                    item.java_type for item in relation.select_items
                ),
                "query_imports": self._dto_imports(relation_query_fields),
                "query_fields": relation_query_fields,
            }
            files[f"{java_root}/dto/{relation.dto_name}.java"] = self._render(
                "dto/RelationDto.java.j2", **relation_context
            )
            files[f"{java_root}/dto/{relation.query_name}.java"] = self._render(
                "dto/RelationQuery.java.j2", **relation_context
            )

        if project.frontend.enabled and project.frontend.framework == "vue2":
            files.update(self._render_vue2_frontend(project))

        return files

    def _render(self, template_name: str, **context: object) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)

    def _datasource_placeholders(self, project: ProjectIR) -> Dict[str, str]:
        datasource = project.datasource
        return {
            "url": self._env_placeholder("DB_URL", datasource["url"]),
            "username": self._env_placeholder("DB_USERNAME", datasource["username"]),
            "password": self._env_placeholder("DB_PASSWORD", datasource["password"]),
            "driver_class_name": self._env_placeholder(
                "DB_DRIVER_CLASS_NAME",
                datasource["driverClassName"],
            ),
        }

    def _env_placeholder(self, env_name: str, default_value: str) -> str:
        escaped_default = str(default_value).replace('"', '\\"')
        return f"${{{env_name}:{escaped_default}}}"

    def _request_dto_fields(self, table: TableIR, mode: str) -> List[Dict[str, object]]:
        fields: List[Dict[str, object]] = []
        for field in table.fields:
            if field.is_primary or field.logic_delete or field.auto_fill:
                continue

            annotations: List[str] = []
            annotation_types: List[str] = []
            field_name = field.property_name
            max_length = db_type_length(field.db_type)

            if mode == "create" and not field.nullable:
                if field.java_type == "String":
                    annotations.append(
                        f'@NotBlank(message = "{field_name} must not be blank")'
                    )
                    annotation_types.append("NotBlank")
                else:
                    annotations.append(
                        f'@NotNull(message = "{field_name} must not be null")'
                    )
                    annotation_types.append("NotNull")

            if field.java_type == "String" and max_length is not None:
                annotations.append(
                    f'@Size(max = {max_length}, message = "{field_name} length must be <= {max_length}")'
                )
                annotation_types.append("Size")

            fields.append(
                {
                    "java_type": field.java_type,
                    "property_name": field.property_name,
                    "annotations": annotations,
                    "annotation_types": annotation_types,
                    "default_value": None,
                }
            )

        return fields

    def _query_dto_fields(
        self,
        queryable_fields: Iterable[QueryableFieldIR | RelationFilterIR],
        sortable_fields: Iterable[SortableFieldIR],
    ) -> List[Dict[str, object]]:
        sortable_field_list = list(sortable_fields)
        fields = [
            {
                "java_type": "Long",
                "property_name": "page",
                "annotations": ['@Min(value = 1, message = "page must be >= 1")'],
                "annotation_types": ["Min"],
                "default_value": "1L",
            },
            {
                "java_type": "Long",
                "property_name": "size",
                "annotations": [
                    '@Min(value = 1, message = "size must be >= 1")',
                    '@Max(value = 200, message = "size must be <= 200")',
                ],
                "annotation_types": ["Min", "Max"],
                "default_value": "20L",
            },
        ]

        for item in queryable_fields:
            fields.append(
                {
                    "java_type": item.java_type,
                    "property_name": item.property_name,
                    "annotations": [],
                    "annotation_types": [],
                    "default_value": None,
                }
            )

        if sortable_field_list:
            fields.append(
                {
                    "java_type": "String",
                    "property_name": "sortBy",
                    "annotations": [],
                    "annotation_types": [],
                    "default_value": None,
                }
            )
            fields.append(
                {
                    "java_type": "String",
                    "property_name": "sortDir",
                    "annotations": [
                        '@Pattern(regexp = "ASC|DESC|asc|desc", message = "sortDir must be ASC or DESC")'
                    ],
                    "annotation_types": ["Pattern"],
                    "default_value": None,
                }
            )

        return fields

    def _relation_query_dto_fields(
        self, relation: RelationIR
    ) -> List[Dict[str, object]]:
        fields = self._query_dto_fields([], relation.sortable_fields)
        insert_at = 2
        for item in relation.filters:
            fields.insert(
                insert_at,
                {
                    "java_type": item.java_type,
                    "property_name": item.param_name,
                    "annotations": [],
                    "annotation_types": [],
                    "default_value": None,
                },
            )
            insert_at += 1
        return fields

    def _dto_imports(self, dto_fields: Iterable[Dict[str, object]]) -> List[str]:
        imports = set()
        for field in dto_fields:
            imported = java_import(str(field["java_type"]))
            if imported:
                imports.add(imported)
            annotation_types = cast(List[str], field["annotation_types"])
            for annotation_type in annotation_types:
                imported = ANNOTATION_IMPORTS.get(str(annotation_type))
                if imported:
                    imports.add(imported)
        return sorted(imports)

    def _query_field_contexts(
        self,
        queryable_fields: Iterable[QueryableFieldIR],
    ) -> List[Dict[str, object]]:
        fields: List[Dict[str, object]] = []
        for item in queryable_fields:
            fields.append(
                {
                    "property_name": item.property_name,
                    "column_name": item.column_name,
                    "java_type": item.java_type,
                    "operator": item.operator,
                    "is_string": item.java_type == "String",
                    "method_suffix": item.property_name[:1].upper()
                    + item.property_name[1:],
                }
            )
        return fields

    def _sortable_field_context(
        self, sortable_field: SortableFieldIR
    ) -> Dict[str, object]:
        return {
            "request_name": sortable_field.request_name,
            "column_name": sortable_field.column_name,
            "property_name": sortable_field.property_name,
            "java_type": sortable_field.java_type,
            "method_suffix": sortable_field.property_name[:1].upper()
            + sortable_field.property_name[1:],
            "side": sortable_field.side,
        }

    def _render_vue2_frontend(self, project: ProjectIR) -> Dict[str, str]:
        files: Dict[str, str] = {}
        locale = project.frontend.locale
        messages = self._frontend_messages(locale)
        frontend_root = project.frontend.output_dir.strip("/") or "frontend"
        relation_groups = self._group_relations(project.relations)
        table_map = {table.name: table for table in project.tables}

        table_pages = [
            self._frontend_table_page_context(
                project,
                table,
                relation_groups.get(table.name, []),
                locale,
            )
            for table in project.tables
        ]
        relation_pages = [
            self._frontend_relation_page_context(project, relation, table_map, locale)
            for relation in project.relations
        ]

        frontend_context = {
            "project": project,
            "frontend": project.frontend,
            "messages": messages,
            "table_pages": table_pages,
            "relation_pages": relation_pages,
            "menu_groups": self._frontend_menu_groups(
                locale,
                table_pages,
                relation_pages,
            ),
            "dashboard_cards": [
                {
                    "title": messages["dashboard_card_data_title"],
                    "value": len(table_pages),
                    "description": messages["dashboard_card_data_description"],
                    "icon": "el-icon-s-grid",
                },
                {
                    "title": messages["dashboard_card_relations_title"],
                    "value": len(relation_pages),
                    "description": messages["dashboard_card_relations_description"],
                    "icon": "el-icon-connection",
                },
            ],
        }

        shared_files = {
            f"{frontend_root}/package.json": "frontend/package.json.j2",
            f"{frontend_root}/babel.config.js": "frontend/babel.config.js.j2",
            f"{frontend_root}/vue.config.js": "frontend/vue.config.js.j2",
            f"{frontend_root}/public/index.html": "frontend/public/index.html.j2",
            f"{frontend_root}/src/main.js": "frontend/src/main.js.j2",
            f"{frontend_root}/src/App.vue": "frontend/src/App.vue.j2",
            f"{frontend_root}/src/router/index.js": "frontend/src/router/index.js.j2",
            f"{frontend_root}/src/layout/Layout.vue": "frontend/src/layout/Layout.vue.j2",
            f"{frontend_root}/src/styles/index.scss": "frontend/src/styles/index.scss.j2",
            f"{frontend_root}/src/utils/request.js": "frontend/src/utils/request.js.j2",
            f"{frontend_root}/src/utils/format.js": "frontend/src/utils/format.js.j2",
            f"{frontend_root}/src/views/dashboard/index.vue": "frontend/src/views/dashboard/index.vue.j2",
        }
        for file_path, template_name in shared_files.items():
            files[file_path] = self._render(template_name, **frontend_context)

        for page in table_pages:
            files[f"{frontend_root}/src/api/{page['resource_name']}.js"] = self._render(
                "frontend/src/api/table.js.j2",
                **frontend_context,
                page=page,
            )
            files[f"{frontend_root}/src/views/{page['resource_name']}/index.vue"] = (
                self._render(
                    "frontend/src/views/table/index.vue.j2",
                    **frontend_context,
                    page=page,
                )
            )

        for page in relation_pages:
            files[
                f"{frontend_root}/src/views/relations/{page['endpoint_name']}/index.vue"
            ] = self._render(
                "frontend/src/views/relation/index.vue.j2",
                **frontend_context,
                page=page,
            )

        return files

    def _frontend_menu_groups(
        self,
        locale: str,
        table_pages: List[Dict[str, object]],
        relation_pages: List[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        messages = self._frontend_messages(locale)
        groups = [
            {
                "title": messages["menu_group_data"],
                "icon": "el-icon-s-grid",
                "items": [
                    {
                        "path": str(page["route_path"]),
                        "title": str(page["title"]),
                        "icon": str(page["menu_icon"]),
                    }
                    for page in table_pages
                    if bool(page["menu_visible"])
                ],
            }
        ]
        if relation_pages:
            groups.append(
                {
                    "title": messages["menu_group_relations"],
                    "icon": "el-icon-connection",
                    "items": [
                        {
                            "path": str(page["route_path"]),
                            "title": str(page["title"]),
                            "icon": str(page["menu_icon"]),
                        }
                        for page in relation_pages
                        if bool(page["menu_visible"])
                    ],
                }
            )
        return [group for group in groups if group["items"]]

    def _frontend_table_page_context(
        self,
        project: ProjectIR,
        table: TableIR,
        table_relations: List[RelationIR],
        locale: str,
    ) -> Dict[str, object]:
        field_by_property = {field.property_name: field for field in table.fields}
        title = self._frontend_table_title(table, locale)
        query_fields = [
            self._frontend_query_field(
                field_by_property[item.property_name],
                item.property_name,
                locale,
            )
            for item in table.queryable_fields
            if item.property_name in field_by_property
            and field_by_property[item.property_name].frontend.query_visible
        ]
        form_fields = [
            self._frontend_form_field(field, locale)
            for field in table.fields
            if not field.is_primary
            and not field.logic_delete
            and not field.auto_fill
            and field.frontend.form_visible
        ]
        table_columns = [
            self._frontend_table_column(field, table.sortable_fields, locale)
            for field in table.fields
            if not field.logic_delete and field.frontend.table_visible
        ]
        detail_fields = [
            self._frontend_detail_field(field, locale)
            for field in table.fields
            if not field.logic_delete and field.frontend.detail_visible
        ]
        sort_options = [
            self._frontend_sort_option(
                sort_item,
                field_by_property[sort_item.property_name],
                locale,
            )
            for sort_item in table.sortable_fields
            if sort_item.property_name in field_by_property
        ]
        resource_pascal = snake_to_pascal(table.resource_name)
        relation_methods = [
            {
                "method_name": relation.method_name,
                "api_function_name": f"fetch{relation.method_name[:1].upper()}{relation.method_name[1:]}",
                "endpoint_name": relation.name,
                "title": relation.frontend.menu_title
                or self._frontend_title(locale, relation.name, relation.dto_name),
                "route_path": f"/relations/{relation.name}",
                "menu_icon": relation.frontend.menu_icon,
                "menu_visible": relation.frontend.menu_visible,
            }
            for relation in table_relations
        ]

        return {
            "title": title,
            "subtitle": self._frontend_text(
                locale,
                "table_subtitle",
                table_title=title,
            ),
            "resource_name": table.resource_name,
            "entity_name": table.entity_name,
            "route_path": f"/{table.resource_name}",
            "route_name": f"{table.entity_name}Index",
            "menu_icon": table.frontend.menu_icon,
            "menu_visible": table.frontend.menu_visible,
            "api_base": f"/{table.resource_name}",
            "api_function_names": {
                "fetch_page": f"fetch{resource_pascal}Page",
                "fetch_one": f"fetch{table.entity_name}",
                "create": f"create{table.entity_name}",
                "update": f"update{table.entity_name}",
                "delete": f"delete{table.entity_name}",
            },
            "query_fields": query_fields,
            "form_fields": form_fields,
            "table_columns": table_columns,
            "detail_fields": detail_fields,
            "sort_options": sort_options,
            "has_sorting": bool(sort_options),
            "sort_map": [
                {
                    "prop": item["property_name"],
                    "request_name": item["request_name"],
                }
                for item in sort_options
            ],
            "primary_key_property": table.primary_key_property,
            "primary_key_method_suffix": table.primary_key_property[:1].upper()
            + table.primary_key_property[1:],
            "relation_methods": relation_methods,
        }

    def _frontend_relation_page_context(
        self,
        project: ProjectIR,
        relation: RelationIR,
        table_map: Dict[str, TableIR],
        locale: str,
    ) -> Dict[str, object]:
        left_table = table_map[relation.left_table]
        right_table = table_map[relation.right_table]
        left_fields = {field.column_name: field for field in left_table.fields}
        right_fields = {field.column_name: field for field in right_table.fields}

        query_fields = []
        for item in relation.filters:
            source_fields = left_fields if item.side == "left" else right_fields
            source_field = source_fields[item.column_name]
            if not source_field.frontend.query_visible:
                continue
            query_fields.append(
                self._frontend_query_field(source_field, item.param_name, locale)
            )

        columns = []
        for item in relation.select_items:
            source_fields = left_fields if item.side == "left" else right_fields
            source_field = source_fields[item.column_name]
            columns.append(
                {
                    "property_name": item.alias,
                    "label": self._frontend_label(source_field, item.alias, locale),
                    "formatter": self._frontend_formatter(item.java_type),
                }
            )

        sort_options = []
        for sort_item in relation.sortable_fields:
            source_fields = left_fields if sort_item.side == "left" else right_fields
            source_field = source_fields[sort_item.column_name]
            sort_options.append(
                self._frontend_sort_option(sort_item, source_field, locale)
            )

        title = relation.frontend.menu_title or self._frontend_title(
            locale,
            relation.name,
            relation.dto_name,
        )

        return {
            "title": title,
            "subtitle": self._frontend_text(
                locale,
                "relation_subtitle",
                left_title=self._frontend_table_title(left_table, locale),
                right_title=self._frontend_table_title(right_table, locale),
            ),
            "endpoint_name": relation.name,
            "route_path": f"/relations/{relation.name}",
            "route_name": f"{snake_to_pascal(relation.name)}RelationIndex",
            "menu_icon": relation.frontend.menu_icon,
            "menu_visible": relation.frontend.menu_visible,
            "api_import_file": left_table.resource_name,
            "api_function_name": f"fetch{relation.method_name[:1].upper()}{relation.method_name[1:]}",
            "query_fields": query_fields,
            "columns": columns,
            "sort_options": sort_options,
            "has_sorting": bool(sort_options),
        }

    def _frontend_form_field(self, field: FieldIR, locale: str) -> Dict[str, object]:
        widget = self._frontend_widget(
            str(field.java_type),
            str(field.db_type),
            mode="form",
            component_override=str(field.frontend.component),
            has_options=bool(field.frontend.options),
        )
        label = self._frontend_label(field, str(field.property_name), locale)
        return {
            "property_name": str(field.property_name),
            "label": label,
            "kind": widget["kind"],
            "default_js": widget["default_js"],
            "step": widget["step"],
            "picker_type": widget["picker_type"],
            "value_format": widget["value_format"],
            "max_length": widget["max_length"],
            "required": not bool(field.nullable),
            "options": [
                {"label": item.label, "value": item.value}
                for item in field.frontend.options
            ],
            "placeholder": self._frontend_placeholder(
                locale,
                widget["kind"],
                str(field.frontend.placeholder) or label,
            ),
        }

    def _frontend_query_field(
        self,
        field: FieldIR,
        prop_name: str,
        locale: str,
    ) -> Dict[str, object]:
        widget = self._frontend_widget(
            str(field.java_type),
            str(field.db_type),
            mode="query",
            component_override=str(field.frontend.query_component)
            or str(field.frontend.component),
            has_options=bool(field.frontend.options),
        )
        label = self._frontend_label(field, prop_name, locale)
        return {
            "property_name": prop_name,
            "label": label,
            "kind": widget["kind"],
            "default_js": widget["default_js"],
            "step": widget["step"],
            "picker_type": widget["picker_type"],
            "value_format": widget["value_format"],
            "options": [
                {"label": item.label, "value": item.value}
                for item in field.frontend.options
            ],
            "placeholder": self._frontend_placeholder(
                locale,
                widget["kind"],
                str(field.frontend.placeholder) or label,
            ),
        }

    def _frontend_table_column(
        self,
        field: FieldIR,
        sortable_fields: Iterable[SortableFieldIR],
        locale: str,
    ) -> Dict[str, object]:
        sortable_props = {item.property_name for item in sortable_fields}
        property_name = str(field.property_name)
        return {
            "property_name": property_name,
            "label": self._frontend_label(field, property_name, locale),
            "formatter": self._frontend_formatter(str(field.java_type)),
            "sortable": property_name in sortable_props,
        }

    def _frontend_detail_field(self, field: FieldIR, locale: str) -> Dict[str, object]:
        property_name = str(field.property_name)
        return {
            "property_name": property_name,
            "label": self._frontend_label(field, property_name, locale),
            "formatter": self._frontend_formatter(str(field.java_type)),
        }

    def _frontend_sort_option(
        self,
        sort_item: SortableFieldIR,
        field: FieldIR,
        locale: str,
    ) -> Dict[str, object]:
        return {
            "request_name": sort_item.request_name,
            "property_name": sort_item.property_name,
            "label": self._frontend_label(field, sort_item.request_name, locale),
        }

    def _frontend_table_title(self, table: TableIR, locale: str) -> str:
        return (
            table.frontend.menu_title
            or table.comment
            or self._frontend_title(locale, table.entity_name, table.entity_name)
        )

    def _frontend_label(self, field: FieldIR, fallback_name: str, locale: str) -> str:
        return (
            str(field.frontend.label)
            or str(field.comment)
            or self._frontend_title(locale, fallback_name, fallback_name)
        )

    def _frontend_widget(
        self,
        java_type: str,
        db_type: str,
        mode: str,
        component_override: str = "",
        has_options: bool = False,
    ) -> Dict[str, object]:
        if component_override:
            return self._frontend_widget_from_component(
                component_override,
                java_type,
                db_type,
                mode,
                has_options,
            )
        max_length = db_type_length(db_type)
        if has_options:
            return self._frontend_widget_from_component(
                "select",
                java_type,
                db_type,
                mode,
                has_options,
            )
        if java_type == "String":
            kind = (
                "textarea"
                if "text" in db_type.lower() or (max_length or 0) > 120
                else "text"
            )
            return {
                "kind": kind,
                "default_js": "''",
                "step": "1",
                "picker_type": "",
                "value_format": "",
                "max_length": max_length or 255,
            }
        if java_type in {"Long", "Integer"}:
            return {
                "kind": "number",
                "default_js": "null",
                "step": "1",
                "picker_type": "",
                "value_format": "",
                "max_length": 0,
            }
        if java_type in {"Double", "BigDecimal"}:
            return {
                "kind": "number",
                "default_js": "null",
                "step": "0.01",
                "picker_type": "",
                "value_format": "",
                "max_length": 0,
            }
        if java_type == "LocalDateTime":
            return {
                "kind": "datetime",
                "default_js": "''",
                "step": "1",
                "picker_type": "datetime",
                "value_format": "yyyy-MM-ddTHH:mm:ss",
                "max_length": 0,
            }
        if java_type == "LocalDate":
            return {
                "kind": "date",
                "default_js": "''",
                "step": "1",
                "picker_type": "date",
                "value_format": "yyyy-MM-dd",
                "max_length": 0,
            }
        if java_type == "Boolean":
            return {
                "kind": "boolean" if mode == "query" else "switch",
                "default_js": "null" if mode == "query" else "false",
                "step": "1",
                "picker_type": "",
                "value_format": "",
                "max_length": 0,
            }
        return {
            "kind": "text",
            "default_js": "''",
            "step": "1",
            "picker_type": "",
            "value_format": "",
            "max_length": max_length or 255,
        }

    def _frontend_widget_from_component(
        self,
        component: str,
        java_type: str,
        db_type: str,
        mode: str,
        has_options: bool,
    ) -> Dict[str, object]:
        max_length = db_type_length(db_type)
        if component in {"text", "textarea"}:
            return {
                "kind": component,
                "default_js": "''",
                "step": "1",
                "picker_type": "",
                "value_format": "",
                "max_length": max_length or 255,
            }
        if component == "number":
            return {
                "kind": "number",
                "default_js": "null",
                "step": "0.01" if java_type in {"Double", "BigDecimal"} else "1",
                "picker_type": "",
                "value_format": "",
                "max_length": 0,
            }
        if component == "switch":
            return {
                "kind": "boolean" if mode == "query" else "switch",
                "default_js": "null" if mode == "query" else "false",
                "step": "1",
                "picker_type": "",
                "value_format": "",
                "max_length": 0,
            }
        if component == "date":
            return {
                "kind": "date",
                "default_js": "''",
                "step": "1",
                "picker_type": "date",
                "value_format": "yyyy-MM-dd",
                "max_length": 0,
            }
        if component == "datetime":
            return {
                "kind": "datetime",
                "default_js": "''",
                "step": "1",
                "picker_type": "datetime",
                "value_format": "yyyy-MM-ddTHH:mm:ss",
                "max_length": 0,
            }
        if component == "select":
            default_js = "''" if java_type == "String" else "null"
            if has_options and any(
                item in {"Boolean", "boolean"}
                for item in {java_type, str(java_type).lower()}
            ):
                default_js = "null" if mode == "query" else "false"
            return {
                "kind": "select",
                "default_js": default_js,
                "step": "1",
                "picker_type": "",
                "value_format": "",
                "max_length": 0,
            }
        return self._frontend_widget(java_type, db_type, mode)

    def _frontend_formatter(self, java_type: str) -> str:
        if java_type == "LocalDateTime":
            return "datetime"
        if java_type == "LocalDate":
            return "date"
        if java_type == "Boolean":
            return "boolean"
        return "plain"

    def _frontend_messages(self, locale: str) -> Dict[str, str]:
        return cast(
            Dict[str, str], FRONTEND_MESSAGES.get(locale, FRONTEND_MESSAGES["zh-CN"])
        )

    def _frontend_text(self, locale: str, key: str, **kwargs: object) -> str:
        message = self._frontend_messages(locale)[key]
        if kwargs:
            return message.format(**kwargs)
        return message

    def _frontend_placeholder(self, locale: str, kind: object, label: str) -> str:
        kind_name = str(kind)
        key = (
            "placeholder_select"
            if kind_name in {"date", "datetime", "boolean", "select"}
            else "placeholder_enter"
        )
        if self._is_preformatted_placeholder(label):
            return label
        return self._frontend_text(locale, key, label=label)

    def _is_preformatted_placeholder(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        return stripped.startswith(("请输入", "请选择", "Enter ", "Select "))

    def _frontend_title(self, locale: str, name: str, fallback: str) -> str:
        text = name or fallback
        if not text:
            return self._frontend_text(locale, "untitled")
        normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
        normalized = normalized.replace("_", " ").replace("-", " ").strip()
        if not normalized:
            normalized = fallback
        return " ".join(part.capitalize() for part in normalized.split())

    def _auto_fill_imports(self, project: ProjectIR) -> List[str]:
        imports = set()
        for field in self._auto_fill_fields(project, mode="insert"):
            imported = java_import(str(field["java_type"]))
            if imported:
                imports.add(imported)
        for field in self._auto_fill_fields(project, mode="update"):
            imported = java_import(str(field["java_type"]))
            if imported:
                imports.add(imported)
        return sorted(imports)

    def _auto_fill_fields(self, project: ProjectIR, mode: str) -> List[Dict[str, str]]:
        fields: List[Dict[str, str]] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for table in project.tables:
            for field in table.fields:
                if not field.auto_fill:
                    continue
                if mode == "insert" and field.auto_fill not in {
                    "INSERT",
                    "INSERT_UPDATE",
                }:
                    continue
                if mode == "update" and field.auto_fill not in {
                    "UPDATE",
                    "INSERT_UPDATE",
                }:
                    continue

                value_expression = self._auto_fill_value_expression(field.java_type)
                if value_expression is None:
                    continue

                key = (field.property_name, field.java_type, mode)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                fields.append(
                    {
                        "property_name": field.property_name,
                        "java_type": field.java_type,
                        "value_expression": value_expression,
                    }
                )
        return fields

    def _auto_fill_value_expression(self, java_type: str) -> str | None:
        if java_type == "LocalDateTime":
            return "LocalDateTime.now()"
        if java_type == "LocalDate":
            return "LocalDate.now()"
        return None

    def _render_init_sql(self, project: ProjectIR) -> str:
        sections: List[str] = []
        database_name = project.datasource.get(
            "databaseName"
        ) or self._database_name_from_url(project.datasource.get("url", ""))
        if database_name:
            sections.append(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            sections.append(f"USE `{database_name}`;")

        for table in project.tables:
            column_lines: List[str] = []
            for field in table.fields:
                parts = [f"`{field.column_name}`", field.db_type]
                if not field.nullable:
                    parts.append("NOT NULL")
                if field.is_primary and field.id_type == "AUTO":
                    parts.append("AUTO_INCREMENT")
                if field.comment:
                    escaped_comment = field.comment.replace("'", "''")
                    parts.append(f"COMMENT '{escaped_comment}'")
                column_lines.append("  " + " ".join(parts))

            column_lines.append(f"  PRIMARY KEY (`{table.primary_key_column}`)")
            for field in table.fields:
                if field.unique:
                    column_lines.append(
                        f"  UNIQUE KEY `uk_{table.name}_{field.column_name}` (`{field.column_name}`)"
                    )
            for index_line in self._index_lines(project, table):
                column_lines.append(index_line)
            for foreign_key_line in self._foreign_key_lines(project, table):
                column_lines.append(foreign_key_line)

            suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            if table.comment:
                escaped_table_comment = table.comment.replace("'", "''")
                suffix += f" COMMENT='{escaped_table_comment}'"

            body = ",\n".join(column_lines)
            sections.append(
                f"CREATE TABLE IF NOT EXISTS `{table.name}` (\n{body}\n){suffix};"
            )

            if table.seed_data:
                sections.append(self._render_seed_data(table))

        return "\n\n".join(sections) + "\n"

    def _render_seed_data(self, table: TableIR) -> str:
        rows: List[str] = []
        ordered_columns = [field.column_name for field in table.fields]
        for seed_row in table.seed_data:
            columns = [
                column_name
                for column_name in ordered_columns
                if column_name in seed_row
            ]
            if not columns:
                continue
            rendered_columns = ", ".join(f"`{column_name}`" for column_name in columns)
            rendered_values = ", ".join(
                self._sql_literal(seed_row[column_name]) for column_name in columns
            )
            rows.append(
                f"INSERT INTO `{table.name}` ({rendered_columns}) VALUES ({rendered_values});"
            )
        return "\n".join(rows)

    def _sql_literal(self, value: object) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    def _database_name_from_url(self, datasource_url: str) -> str | None:
        match = re.search(r"jdbc:[^:]+://[^/]+/([^?;]+)", datasource_url)
        if not match:
            return None
        database_name = match.group(1).strip()
        return database_name or None

    def _index_lines(self, project: ProjectIR, table: TableIR) -> List[str]:
        lines: List[str] = []
        for index in self._merged_indexes(project, table):
            index_columns = ", ".join(
                f"`{column_name}`" for column_name in index.columns
            )
            prefix = "UNIQUE KEY" if index.unique else "KEY"
            lines.append(f"  {prefix} `{index.name}` ({index_columns})")
        return lines

    def _foreign_key_lines(self, project: ProjectIR, table: TableIR) -> List[str]:
        lines: List[str] = []
        for foreign_key in self._merged_foreign_keys(project, table):
            left_columns = ", ".join(
                f"`{column_name}`" for column_name in foreign_key.columns
            )
            right_columns = ", ".join(
                f"`{column_name}`" for column_name in foreign_key.ref_columns
            )
            line = (
                "  CONSTRAINT "
                f"`{foreign_key.name}` FOREIGN KEY ({left_columns}) REFERENCES "
                f"`{foreign_key.ref_table}` ({right_columns})"
            )
            if foreign_key.on_delete:
                line += f" ON DELETE {foreign_key.on_delete}"
            if foreign_key.on_update:
                line += f" ON UPDATE {foreign_key.on_update}"
            lines.append(line)

        return lines

    def _merged_indexes(self, project: ProjectIR, table: TableIR) -> List[IndexIR]:
        merged: List[IndexIR] = []
        seen_names: set[str] = set()
        seen_signatures: set[tuple[bool, tuple[str, ...]]] = {
            (True, (field.column_name,)) for field in table.fields if field.unique
        }
        seen_signatures.add((False, (table.primary_key_column,)))

        for index in [*table.indexes, *self._inferred_indexes(project, table)]:
            signature = (index.unique, tuple(index.columns))
            if index.name in seen_names or signature in seen_signatures:
                continue
            seen_names.add(index.name)
            seen_signatures.add(signature)
            merged.append(index)

        return merged

    def _inferred_indexes(self, project: ProjectIR, table: TableIR) -> List[IndexIR]:
        if not table.infer_indexes:
            return []

        table_fields = {field.column_name: field for field in table.fields}
        indexed_columns: List[str] = []

        def add_index(column_name: str) -> None:
            field = table_fields.get(column_name)
            if field is None or field.is_primary or field.unique:
                return
            if column_name not in indexed_columns:
                indexed_columns.append(column_name)

        for queryable_field in table.queryable_fields:
            add_index(queryable_field.column_name)

        for relation in project.relations:
            if relation.left_table == table.name:
                for on_clause in relation.on_clauses:
                    add_index(on_clause.left_column)
            if relation.right_table == table.name:
                for on_clause in relation.on_clauses:
                    add_index(on_clause.right_column)
            for relation_filter in relation.filters:
                if relation.left_table == table.name and relation_filter.side == "left":
                    add_index(relation_filter.column_name)
                if (
                    relation.right_table == table.name
                    and relation_filter.side == "right"
                ):
                    add_index(relation_filter.column_name)

        return [
            IndexIR(
                name=f"idx_{table.name}_{column_name}",
                columns=[column_name],
                inferred=True,
            )
            for column_name in indexed_columns
        ]

    def _merged_foreign_keys(
        self,
        project: ProjectIR,
        table: TableIR,
    ) -> List[ForeignKeyIR]:
        merged: List[ForeignKeyIR] = []
        seen_names: set[str] = set()
        seen_signatures: set[tuple[tuple[str, ...], str, tuple[str, ...]]] = set()

        for foreign_key in [
            *table.foreign_keys,
            *self._inferred_foreign_keys(project, table),
        ]:
            signature = (
                tuple(foreign_key.columns),
                foreign_key.ref_table,
                tuple(foreign_key.ref_columns),
            )
            if foreign_key.name in seen_names or signature in seen_signatures:
                continue
            seen_names.add(foreign_key.name)
            seen_signatures.add(signature)
            merged.append(foreign_key)

        return merged

    def _inferred_foreign_keys(
        self,
        project: ProjectIR,
        table: TableIR,
    ) -> List[ForeignKeyIR]:
        if not table.infer_foreign_keys:
            return []

        foreign_keys: List[ForeignKeyIR] = []
        for relation in project.relations:
            if relation.left_table != table.name or not relation.on_clauses:
                continue

            constraint_suffix = re.sub(r"[^a-zA-Z0-9_]+", "_", relation.name).strip("_")
            if not constraint_suffix:
                constraint_suffix = f"{relation.left_table}_{relation.right_table}"

            foreign_keys.append(
                ForeignKeyIR(
                    name=f"fk_{relation.left_table}_{relation.right_table}_{constraint_suffix}",
                    columns=[item.left_column for item in relation.on_clauses],
                    ref_table=relation.right_table,
                    ref_columns=[item.right_column for item in relation.on_clauses],
                    on_delete="RESTRICT",
                    on_update="RESTRICT",
                    inferred=True,
                )
            )

        return foreign_keys

    def _java_imports(self, java_types: Iterable[str]) -> List[str]:
        imports = set()
        for java_type in java_types:
            imported = java_import(java_type)
            if imported:
                imports.add(imported)
        return sorted(imports)

    def _group_relations(
        self, relations: List[RelationIR]
    ) -> Dict[str, List[RelationIR]]:
        grouped: Dict[str, List[RelationIR]] = defaultdict(list)
        for relation in relations:
            grouped[relation.left_table].append(relation)
        return grouped

    def _relation_mapper_context(self, relation: RelationIR) -> Dict[str, object]:
        select_sql: List[str] = []
        for item in relation.select_items:
            alias = "l" if item.side == "left" else "r"
            select_sql.append(f"{alias}.{item.column_name} AS {item.alias}")

        on_sql = [
            f"l.{item.left_column} = r.{item.right_column}"
            for item in relation.on_clauses
        ]

        where_items = []
        for item in relation.filters:
            alias = "l" if item.side == "left" else "r"
            condition = self._relation_condition(
                alias, item.column_name, item.param_name, item.operator
            )
            test = self._relation_test(item.param_name, item.is_string)

            where_items.append(
                {
                    "test": test,
                    "condition": condition,
                }
            )

        query_fields = []
        for item in relation.filters:
            query_fields.append(
                {
                    "param_name": item.param_name,
                    "java_type": item.java_type,
                    "method_suffix": item.param_name[:1].upper() + item.param_name[1:],
                }
            )

        sort_items = [
            {
                "request_name": item.request_name,
                "column_sql": f"{'l' if item.side == 'left' else 'r'}.{item.column_name}",
            }
            for item in relation.sortable_fields
        ]

        return {
            "name": relation.name,
            "method_name": relation.method_name,
            "dto_name": relation.dto_name,
            "query_name": relation.query_name,
            "join_type": relation.join_type,
            "left_table": relation.left_table,
            "right_table": relation.right_table,
            "select_sql": select_sql,
            "on_sql": on_sql,
            "where_items": where_items,
            "query_fields": query_fields,
            "query_field_names": {item["param_name"] for item in query_fields},
            "sort_items": sort_items,
            "has_sorting": bool(sort_items),
            "endpoint_name": snake_to_camel(relation.name),
        }

    def _relation_condition(
        self,
        alias: str,
        column_name: str,
        param_name: str,
        operator: str,
    ) -> str:
        column_ref = f"{alias}.{column_name}"
        param_ref = f"#{{query.{param_name}}}"
        if operator == "LIKE":
            return f"{column_ref} LIKE CONCAT('%', {param_ref}, '%')"
        operator_map = {
            "EQ": "=",
            "NE": "!=",
            "GT": ">",
            "GE": ">=",
            "LT": "<",
            "LE": "<=",
        }
        return f"{column_ref} {operator_map[operator]} {param_ref}"

    def _relation_test(self, param_name: str, is_string: bool) -> str:
        if is_string:
            return f"query.{param_name} != null and query.{param_name} != ''"
        return f"query.{param_name} != null"
