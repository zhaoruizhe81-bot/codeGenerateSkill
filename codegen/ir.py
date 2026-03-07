from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class FrontendOptionIR:
    label: str
    value: Any


@dataclass(slots=True)
class FieldFrontendIR:
    label: str = ""
    component: str = ""
    query_component: str = ""
    table_visible: bool = True
    form_visible: bool = True
    detail_visible: bool = True
    query_visible: bool = True
    placeholder: str = ""
    options: List[FrontendOptionIR] = field(default_factory=list)


@dataclass(slots=True)
class TableFrontendIR:
    menu_title: str = ""
    menu_icon: str = "el-icon-document"
    menu_visible: bool = True


@dataclass(slots=True)
class RelationFrontendIR:
    menu_title: str = ""
    menu_icon: str = "el-icon-connection"
    menu_visible: bool = True


@dataclass(slots=True)
class FieldIR:
    column_name: str
    property_name: str
    java_type: str
    db_type: str
    nullable: bool
    comment: str
    unique: bool = False
    logic_delete: bool = False
    auto_fill: Optional[str] = None
    id_type: Optional[str] = None
    is_primary: bool = False
    frontend: FieldFrontendIR = field(default_factory=FieldFrontendIR)


@dataclass(slots=True)
class QueryableFieldIR:
    property_name: str
    column_name: str
    java_type: str
    operator: str


@dataclass(slots=True)
class SortableFieldIR:
    request_name: str
    column_name: str
    property_name: str
    java_type: str
    side: Optional[str] = None


@dataclass(slots=True)
class IndexIR:
    name: str
    columns: List[str] = field(default_factory=list)
    unique: bool = False
    inferred: bool = False


@dataclass(slots=True)
class ForeignKeyIR:
    name: str
    columns: List[str] = field(default_factory=list)
    ref_table: str = ""
    ref_columns: List[str] = field(default_factory=list)
    on_delete: Optional[str] = None
    on_update: Optional[str] = None
    inferred: bool = False


@dataclass(slots=True)
class TableIR:
    name: str
    comment: str
    entity_name: str
    object_name: str
    resource_name: str
    primary_key_property: str
    primary_key_column: str
    primary_key_java_type: str
    fields: List[FieldIR] = field(default_factory=list)
    queryable_fields: List[QueryableFieldIR] = field(default_factory=list)
    sortable_fields: List[SortableFieldIR] = field(default_factory=list)
    indexes: List[IndexIR] = field(default_factory=list)
    foreign_keys: List[ForeignKeyIR] = field(default_factory=list)
    seed_data: List[Dict[str, Any]] = field(default_factory=list)
    infer_indexes: bool = True
    infer_foreign_keys: bool = True
    frontend: TableFrontendIR = field(default_factory=TableFrontendIR)

    @property
    def mapper_name(self) -> str:
        return f"{self.entity_name}Mapper"

    @property
    def service_name(self) -> str:
        return f"{self.entity_name}Service"

    @property
    def service_impl_name(self) -> str:
        return f"{self.entity_name}ServiceImpl"

    @property
    def controller_name(self) -> str:
        return f"{self.entity_name}Controller"

    @property
    def create_dto_name(self) -> str:
        return f"{self.entity_name}CreateRequest"

    @property
    def update_dto_name(self) -> str:
        return f"{self.entity_name}UpdateRequest"

    @property
    def query_dto_name(self) -> str:
        return f"{self.entity_name}QueryRequest"


@dataclass(slots=True)
class RelationSelectIR:
    side: str
    column_name: str
    property_name: str
    java_type: str
    alias: str


@dataclass(slots=True)
class RelationFilterIR:
    side: str
    column_name: str
    property_name: str
    java_type: str
    operator: str
    param_name: str
    is_string: bool


@dataclass(slots=True)
class RelationOnIR:
    left_column: str
    right_column: str


@dataclass(slots=True)
class RelationIR:
    name: str
    left_table: str
    right_table: str
    left_entity_name: str
    join_type: str
    dto_name: str
    method_name: str
    query_name: str
    select_items: List[RelationSelectIR] = field(default_factory=list)
    filters: List[RelationFilterIR] = field(default_factory=list)
    sortable_fields: List[SortableFieldIR] = field(default_factory=list)
    on_clauses: List[RelationOnIR] = field(default_factory=list)
    frontend: RelationFrontendIR = field(default_factory=RelationFrontendIR)


@dataclass(slots=True)
class FrontendIR:
    enabled: bool = False
    framework: str = "vue2"
    locale: str = "zh-CN"
    output_dir: str = "frontend"
    app_title: str = ""
    backend_url: str = "http://127.0.0.1:8080"
    dev_port: int = 8081


@dataclass(slots=True)
class BackendIR:
    output_dir: str = "backend"


@dataclass(slots=True)
class ProjectIR:
    group_id: str
    artifact_id: str
    name: str
    base_package: str
    boot_version: str
    java_version: str
    datasource: Dict[str, str]
    api_prefix: str
    author: str
    date_time_format: str
    enable_swagger: bool
    application_name: str
    backend: BackendIR = field(default_factory=BackendIR)
    frontend: FrontendIR = field(default_factory=FrontendIR)
    tables: List[TableIR] = field(default_factory=list)
    relations: List[RelationIR] = field(default_factory=list)

    @property
    def base_package_path(self) -> str:
        return self.base_package.replace(".", "/")

    @property
    def application_class_name(self) -> str:
        base = (
            self.artifact_id.replace("-", " ")
            .replace("_", " ")
            .title()
            .replace(" ", "")
        )
        if not base:
            base = "Application"
        return f"{base}Application"


@dataclass(slots=True)
class RenderPlan:
    files: Dict[str, str]
