# springboot2-crud-codegen

English | [简体中文](README.zh-CN.md)

`springboot2-crud-codegen` is a Python CLI that generates Spring Boot 2 + MyBatis-Plus CRUD projects from JSON configuration.

It is designed for fast scaffolding of admin-style backends: entities, mappers, services, controllers, request DTOs, relation query DTOs, `init.sql`, and runnable Maven projects.

It can also generate a standalone Vue 2 admin frontend under `frontend/` when the optional `frontend` config block is enabled.

## What It Generates

- Full Maven project structure
- Spring Boot 2.x application with Java 8 target
- MyBatis-Plus CRUD for single tables
- Relation query endpoints with generated join SQL
- Request DTO validation annotations
- Unified `Result<T>` and `PageResult<T>` response wrappers
- `application.yml` with environment-variable datasource placeholders
- `init.sql` with database creation, table DDL, indexes, foreign keys, and optional seed data
- Auto-fill handler for fields like `createdAt` and `updatedAt`
- Optional standalone Vue 2 + Element UI admin frontend

## Supported Features

- Table query operators: `EQ`, `NE`, `LIKE`, `GT`, `GE`, `LT`, `LE`
- Relation filter operators: `EQ`, `NE`, `LIKE`, `GT`, `GE`, `LT`, `LE`
- Single-table sorting with whitelist-based `sortBy` and `sortDir`
- Relation-query sorting with whitelist-based `sortableFields`
- Explicit indexes and foreign keys
- Inferred indexes and foreign keys as fallback
- Logic-delete field mapping
- Auto-fill field mapping: `INSERT`, `INSERT_UPDATE`
- Seed data generation into `init.sql`
- Standalone Vue 2 admin generation with routes, layout, axios wrapper, CRUD pages, and relation pages
- Frontend fine-grained config for menu title/icon, field visibility, and component type
- Built-in frontend locale dictionaries with `zh-CN` default and optional `en-US`

## Install

```bash
python -m pip install -e .
```

## Quick Start

Generate the sample project:

```bash
python -m codegen -c examples/sample.json -o /tmp/codegen-out
```

Or use the console script after installation:

```bash
codegen -c examples/sample.json -o /tmp/codegen-out
```

Generated root:

```text
/tmp/codegen-out/<artifactId>/
```

Common output files:

- `pom.xml`
- `src/main/resources/application.yml`
- `src/main/resources/init.sql`
- `src/main/resources/mapper/*.xml`
- `src/main/java/<basePackage>/...`

## Example Config Files

- `examples/sample.json`: complete sample with two tables and one relation
- `examples/student_management.json`: simplest single-table student CRUD
- `examples/student_class_management.json`: student + class relation example with indexes, foreign keys, sorting, and seed data
- `examples/fullstack_sample.json`: backend + standalone Vue 2 frontend example
- `examples/student_class_management_fullstack.json`: multi-table student + class fullstack example with Chinese frontend labels over English SQL field names

## Minimal Single-Table Example

Use this shape when you want the smallest valid CRUD project:

```json
{
  "project": {
    "groupId": "com.example",
    "artifactId": "student-management",
    "name": "student-management",
    "basePackage": "com.example.student",
    "bootVersion": "2.7.18",
    "javaVersion": 8
  },
  "datasource": {
    "url": "jdbc:mysql://127.0.0.1:3306/student_management?useSSL=false&serverTimezone=UTC&characterEncoding=UTF-8",
    "databaseName": "student_management",
    "username": "root",
    "password": "123456",
    "driverClassName": "com.mysql.cj.jdbc.Driver"
  },
  "tables": [
    {
      "name": "students",
      "entityName": "Student",
      "primaryKey": "id",
      "queryableFields": [
        {"name": "student_name", "operator": "LIKE"}
      ],
      "fields": [
        {"name": "id", "type": "bigint", "nullable": false, "idType": "AUTO"},
        {"name": "student_name", "type": "varchar(64)", "nullable": false},
        {"name": "created_at", "type": "datetime", "nullable": false, "autoFill": "INSERT"},
        {"name": "updated_at", "type": "datetime", "nullable": false, "autoFill": "INSERT_UPDATE"}
      ]
    }
  ],
  "relations": [],
  "global": {
    "apiPrefix": "/api",
    "author": "codegen",
    "dateTimeFormat": "yyyy-MM-dd HH:mm:ss",
    "enableSwagger": false
  }
}
```

## Relation Example

Use a relation when you want a generated join endpoint:

```json
{
  "name": "student-class",
  "leftTable": "students",
  "rightTable": "classes",
  "joinType": "LEFT",
  "dtoName": "StudentClassDTO",
  "methodName": "pageStudentWithClass",
  "on": [
    {"leftField": "class_id", "rightField": "id"}
  ],
  "select": [
    {"table": "students", "field": "student_name", "alias": "studentName"},
    {"table": "classes", "field": "class_name", "alias": "className"}
  ],
  "filters": [
    {"table": "students", "field": "student_name", "operator": "LIKE", "param": "studentName"},
    {"table": "classes", "field": "class_name", "operator": "LIKE", "param": "className"}
  ],
  "sortableFields": [
    {"table": "students", "field": "student_name", "name": "studentName"},
    {"table": "classes", "field": "class_name", "name": "className"}
  ]
}
```

This generates a relation endpoint like:

```text
GET /api/students/relations/student-class
```

## Rule Reference

### Top-Level Keys

Required:

- `project`
- `datasource`
- `tables`
- `relations`
- `global`

### `project`

- `groupId`: Maven group id
- `artifactId`: Maven artifact id and output directory name
- `name`: Spring application name
- `basePackage`: Java package root
- `bootVersion`: must start with `2.`
- `javaVersion`: currently `8`

### `datasource`

- `url`: JDBC URL
- `databaseName`: optional but recommended; used by `init.sql`
- `username`: default username in generated placeholder
- `password`: default password in generated placeholder
- `driverClassName`: JDBC driver class

Generated `application.yml` uses placeholders like:

```yaml
spring:
  datasource:
    url: "${DB_URL:jdbc:mysql://127.0.0.1:3306/demo?...}"
    username: "${DB_USERNAME:root}"
    password: "${DB_PASSWORD:root}"
```

### `tables[]`

- `name`: database table name
- `comment`: optional table comment
- `entityName`: Java entity class name
- `primaryKey`: primary key column name
- `queryableFields`: query conditions for single-table page API
- `sortableFields`: whitelist of sortable columns for single-table page API
- `indexes`: explicit indexes
- `foreignKeys`: explicit foreign keys
- `inferIndexes`: default `true`
- `inferForeignKeys`: default `true`
- `seedData`: optional rows written into `init.sql`
- `fields`: table fields
- `frontend`: optional per-table frontend metadata

### `fields[]`

Required:

- `name`
- `type`
- `nullable`

Optional:

- `comment`
- `unique`
- `logicDelete`
- `autoFill`: `INSERT` or `INSERT_UPDATE`
- `idType`: for example `AUTO`
- `frontend`: optional field-level frontend metadata

Validation is generated automatically from field definitions:

- non-null `String` fields in create DTO -> `@NotBlank`
- non-null non-string fields in create DTO -> `@NotNull`
- `varchar(n)` and similar string lengths -> `@Size(max = n)`
- auto-fill fields are excluded from create/update DTOs

Frontend field metadata supports:

- `label`
- `component`: `text`, `textarea`, `number`, `switch`, `date`, `datetime`, `select`
- `queryComponent`
- `tableVisible`
- `formVisible`
- `detailVisible`
- `queryVisible`
- `placeholder`
- `options`: for `select`

### `queryableFields[]`

Each item supports:

```json
{"name": "amount", "operator": "GE"}
```

Supported operators:

- `EQ`
- `NE`
- `LIKE`
- `GT`
- `GE`
- `LT`
- `LE`

Rules:

- `LIKE` only works on `String`
- range operators work on numeric or date/time fields

### `sortableFields`

Single-table sorting uses a whitelist to avoid unsafe SQL.

Example:

```json
"sortableFields": ["created_at", "amount"]
```

Generated request DTO will include:

- `sortBy`
- `sortDir`

Valid directions:

- `ASC`
- `DESC`

### `indexes[]`

Example:

```json
"indexes": [
  {
    "name": "idx_students_name_class",
    "columns": ["student_name", "class_id"]
  }
]
```

Fields:

- `name`: optional, generated if omitted
- `columns`: required, one or more table columns
- `unique`: optional boolean

### `foreignKeys[]`

Example:

```json
"foreignKeys": [
  {
    "name": "fk_students_classes_student_class",
    "columns": ["class_id"],
    "refTable": "classes",
    "refColumns": ["id"],
    "onDelete": "RESTRICT",
    "onUpdate": "RESTRICT"
  }
]
```

Supported actions:

- `RESTRICT`
- `CASCADE`
- `SET NULL`
- `NO ACTION`

### `seedData[]`

Rows in `seedData` are converted into `INSERT INTO ... VALUES ...` statements in `init.sql`.

This is useful for:

- demo projects
- quick smoke tests
- local initialization

### `relations[]`

Each relation defines one generated join query endpoint.

Required keys:

- `name`
- `leftTable`
- `rightTable`
- `joinType`: `LEFT` or `INNER`
- `dtoName`
- `methodName`
- `on`
- `select`
- `filters`

Optional:

- `sortableFields`
- `frontend`

Relation filters follow the same operator rules as table queries.

### `frontend`

Enable Vue 2 admin generation with a top-level `frontend` block:

```json
"frontend": {
  "enabled": true,
  "framework": "vue2",
  "locale": "zh-CN",
  "outputDir": "frontend",
  "appTitle": "Demo Admin",
  "backendUrl": "http://127.0.0.1:8080",
  "devPort": 8081
}
```

`locale` defaults to `zh-CN`, so generated frontend copy and Element UI widgets are Chinese by default. Set it to `en-US` when you want an English UI.

Generated frontend includes:

- `frontend/package.json`
- `frontend/src/router/index.js`
- `frontend/src/layout/Layout.vue`
- `frontend/src/utils/request.js`
- `frontend/src/views/dashboard/index.vue`
- `frontend/src/views/<table>/index.vue`
- `frontend/src/views/relations/<relation>/index.vue`

Per-table frontend metadata example:

```json
"frontend": {
  "menuTitle": "User Center",
  "menuIcon": "el-icon-user-solid",
  "menuVisible": true
}
```

Per-field frontend metadata example:

```json
"frontend": {
  "label": "Login Name",
  "component": "textarea",
  "queryComponent": "text",
  "tableVisible": false,
  "formVisible": true,
  "detailVisible": true,
  "queryVisible": true,
  "placeholder": "Enter login name",
  "options": [
    {"label": "Enabled", "value": 1},
    {"label": "Disabled", "value": 0}
  ]
}
```

Keep SQL field names in English, such as `student_name` or `class_id`. For a Chinese UI, provide Chinese `comment` values or set `frontend.label` / `frontend.placeholder` explicitly. The renderer prefers `frontend.label`, then falls back to `comment`, so database naming and UI naming stay decoupled.

The same fallback also applies to relation result columns and sortable labels, which means one field-level label can drive both single-table pages and generated relation pages.

## Generated Runtime Behavior

- Validation annotations are generated in request DTOs
- Query DTOs validate `page`, `size`, and `sortDir`
- Global exception handler hides internal server errors from API clients
- `NotFoundException` is used for missing resources
- `MybatisMetaObjectHandler` auto-fills supported date/time fields

## Build and Test Commands

Install editable package:

```bash
python -m pip install -e .
```

Run Python tests:

```bash
python -m unittest discover -s tests -v
```

Run one test file:

```bash
python -m unittest discover -s tests -p 'test_renderer.py' -v
```

Run one test method:

```bash
python -m unittest discover -s tests -k test_render_application_uses_env_placeholders -v
```

Syntax check:

```bash
python -m compileall codegen tests
```

Compile a generated Java project:

```bash
mvn package -DskipTests
```

Build a generated Vue 2 frontend:

```bash
cd frontend
npm install
npm run build
```

## Typical Workflow

1. Start from `examples/student_management.json` or `examples/sample.json`
2. Adjust project metadata and table definitions
3. Add query fields, sorting, and relation definitions as needed
4. Generate the project
5. If frontend is enabled, install frontend dependencies and run/build it
6. Run `init.sql`
7. Start the Spring Boot app and verify endpoints with `curl`

## Current Scope and Limits

- Java 8 only
- Spring Boot 2.x only
- MySQL-oriented datasource and SQL output
- Frontend generation currently targets Vue 2 + Element UI only
- No generated test classes inside Java output
- Complex reporting SQL is out of scope for now

## Tips

- Prefer setting `databaseName` explicitly instead of relying only on JDBC URL parsing
- Use `sortableFields` whenever you expose sort parameters
- Use explicit `foreignKeys` for production-like DDL, and keep inference as a convenience fallback
- Keep auto-fill fields out of manual request payloads

## License

Currently no explicit license file is included in this repository.
