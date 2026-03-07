# springboot2-crud-codegen

[English](README.md) | 简体中文

`springboot2-crud-codegen` 是一个 Python CLI 工具，用来根据 JSON 配置生成 Spring Boot 2 + MyBatis-Plus CRUD 项目。

它适合快速搭建后台管理类接口项目，能生成实体、Mapper、Service、Controller、请求 DTO、联表查询 DTO、`init.sql`，以及可直接编译运行的 Maven 工程。

当配置里启用可选的 `frontend` 节点时，它还可以额外生成一个独立的 Vue2 + Element UI 管理后台项目，默认输出到 `frontend/`。

## 能生成什么

- 完整 Maven 项目结构
- 基于 Java 8 的 Spring Boot 2.x 工程
- 单表 CRUD
- 联表分页查询接口与 MyBatis XML
- 请求 DTO 校验注解
- 统一返回结构 `Result<T>` 和 `PageResult<T>`
- 使用环境变量占位的 `application.yml`
- 包含建库、建表、索引、外键、演示数据的 `init.sql`
- 自动填充时间字段的 MyBatis-Plus 处理器
- 可选生成独立 Vue2 + Element UI 管理前端

## 当前支持的能力

- 单表查询操作符：`EQ`、`NE`、`LIKE`、`GT`、`GE`、`LT`、`LE`
- 联表过滤操作符：`EQ`、`NE`、`LIKE`、`GT`、`GE`、`LT`、`LE`
- 单表排序：基于白名单生成 `sortBy` / `sortDir`
- 联表排序：基于 `sortableFields` 白名单生成 `ORDER BY`
- 显式索引和外键配置
- 自动推断索引和外键
- 逻辑删除字段映射
- 自动填充字段映射：`INSERT`、`INSERT_UPDATE`
- `seedData` 演示数据写入 `init.sql`
- 可生成独立 Vue2 管理后台，包含路由、布局、请求封装、单表 CRUD 页面、联表查询页面
- 支持前端细粒度配置：菜单标题/图标、字段显隐、组件类型
- 内置前端文案字典与 Element UI 语言切换，默认生成 `zh-CN` 中文界面，也可切换 `en-US`

## 安装

```bash
python -m pip install -e .
```

## 快速开始

使用内置示例生成项目：

```bash
python -m codegen -c examples/sample.json -o /tmp/codegen-out
```

安装后也可以直接使用命令：

```bash
codegen -c examples/sample.json -o /tmp/codegen-out
```

输出目录结构类似：

```text
/tmp/codegen-out/<artifactId>/
```

常见生成文件：

- `pom.xml`
- `src/main/resources/application.yml`
- `src/main/resources/init.sql`
- `src/main/resources/mapper/*.xml`
- `src/main/java/<basePackage>/...`

## 示例配置文件

- `examples/sample.json`：完整示例，包含双表和一个联表查询
- `examples/student_management.json`：最基础的学生单表 CRUD
- `examples/student_class_management.json`：学生 + 班级联表示例，包含排序、索引、外键和演示数据
- `examples/fullstack_sample.json`：后端 + 独立 Vue2 前端的完整示例
- `examples/student_class_management_fullstack.json`：英文字段名 + 中文前端列名的学生班级前后端一体示例

## 最小单表示例

如果你只想快速生成一个最基础的 CRUD，可以从这个结构开始：

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

## 联表示例

如果你要生成联表接口，可以按下面这种结构定义 `relations`：

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

这会生成类似下面的接口：

```text
GET /api/students/relations/student-class
```

## 配置规则说明

### 顶层字段

必填：

- `project`
- `datasource`
- `tables`
- `relations`
- `global`

### `project`

- `groupId`：Maven group id
- `artifactId`：Maven artifact id，同时也是输出目录名
- `name`：Spring 应用名
- `basePackage`：Java 包名根路径
- `bootVersion`：必须以 `2.` 开头
- `javaVersion`：当前固定为 `8`

### `datasource`

- `url`：JDBC URL
- `databaseName`：可选但强烈建议填写，`init.sql` 会优先使用它
- `username`：生成到环境变量占位里的默认用户名
- `password`：生成到环境变量占位里的默认密码
- `driverClassName`：JDBC 驱动类

生成出来的 `application.yml` 大致会是：

```yaml
spring:
  datasource:
    url: "${DB_URL:jdbc:mysql://127.0.0.1:3306/demo?...}"
    username: "${DB_USERNAME:root}"
    password: "${DB_PASSWORD:root}"
```

### `tables[]`

- `name`：数据库表名
- `comment`：表注释，可选
- `entityName`：Java 实体类名
- `primaryKey`：主键字段名
- `queryableFields`：单表分页接口的查询条件
- `sortableFields`：单表允许排序的字段白名单
- `indexes`：显式索引配置
- `foreignKeys`：显式外键配置
- `inferIndexes`：是否允许自动推断索引，默认 `true`
- `inferForeignKeys`：是否允许自动推断外键，默认 `true`
- `seedData`：写入 `init.sql` 的演示数据
- `fields`：字段列表
- `frontend`：可选的表级前端配置

### `fields[]`

必填字段：

- `name`
- `type`
- `nullable`

可选字段：

- `comment`
- `unique`
- `logicDelete`
- `autoFill`：支持 `INSERT`、`INSERT_UPDATE`
- `idType`：例如 `AUTO`
- `frontend`：可选的字段级前端配置

当前 DTO 校验会根据字段自动推断：

- `create` DTO 中，非空字符串 -> `@NotBlank`
- `create` DTO 中，非空非字符串 -> `@NotNull`
- `varchar(n)` 等字符串字段 -> `@Size(max = n)`
- 自动填充字段不会出现在 create/update DTO 中

字段级前端配置支持：

- `label`
- `component`：`text`、`textarea`、`number`、`switch`、`date`、`datetime`、`select`
- `queryComponent`
- `tableVisible`
- `formVisible`
- `detailVisible`
- `queryVisible`
- `placeholder`
- `options`：给 `select` 组件使用

### `queryableFields[]`

每一项可以写成：

```json
{"name": "amount", "operator": "GE"}
```

支持的操作符：

- `EQ`
- `NE`
- `LIKE`
- `GT`
- `GE`
- `LT`
- `LE`

规则：

- `LIKE` 只能用于字符串字段
- 范围操作符只能用于数值或日期时间字段

### `sortableFields`

单表排序必须走白名单，避免直接拼接不安全 SQL。

例如：

```json
"sortableFields": ["created_at", "amount"]
```

生成的 Query DTO 会额外带：

- `sortBy`
- `sortDir`

其中 `sortDir` 允许值：

- `ASC`
- `DESC`

### `indexes[]`

示例：

```json
"indexes": [
  {
    "name": "idx_students_name_class",
    "columns": ["student_name", "class_id"]
  }
]
```

字段说明：

- `name`：可选，不写时自动生成
- `columns`：必填，一个或多个列名
- `unique`：是否唯一索引，可选

### `foreignKeys[]`

示例：

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

支持的外键动作：

- `RESTRICT`
- `CASCADE`
- `SET NULL`
- `NO ACTION`

### `seedData[]`

`seedData` 会被转换成 `init.sql` 里的 `INSERT INTO ... VALUES ...`。

适合用于：

- 演示项目
- 快速联调
- 本地初始化数据

### `relations[]`

每一个 relation 都会生成一个联表分页接口。

必填：

- `name`
- `leftTable`
- `rightTable`
- `joinType`：`LEFT` 或 `INNER`
- `dtoName`
- `methodName`
- `on`
- `select`
- `filters`

可选：

- `sortableFields`
- `frontend`

联表过滤条件和单表查询一样，也支持 `EQ`、`NE`、`LIKE`、`GT`、`GE`、`LT`、`LE`。

### `frontend`

如果你想同时生成前端，可以在顶层加上：

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

`locale` 默认就是 `zh-CN`，所以不写也会生成中文按钮、中文提示语和中文 Element UI 组件文案；如果你想切回英文界面，再显式写成 `en-US` 即可。

生成出来的前端通常包含：

- `frontend/package.json`
- `frontend/src/router/index.js`
- `frontend/src/layout/Layout.vue`
- `frontend/src/utils/request.js`
- `frontend/src/views/dashboard/index.vue`
- `frontend/src/views/<table>/index.vue`
- `frontend/src/views/relations/<relation>/index.vue`

表级前端配置示例：

```json
"frontend": {
  "menuTitle": "用户中心",
  "menuIcon": "el-icon-user-solid",
  "menuVisible": true
}
```

字段级前端配置示例：

```json
"frontend": {
  "label": "登录名",
  "component": "textarea",
  "queryComponent": "text",
  "tableVisible": false,
  "formVisible": true,
  "detailVisible": true,
  "queryVisible": true,
  "placeholder": "请输入登录名",
  "options": [
    {"label": "启用", "value": 1},
    {"label": "禁用", "value": 0}
  ]
}
```

如果数据库字段名必须保持英文，比如 `student_name`、`class_id`，也没关系。前端显示名不取决于字段名，而是优先使用 `frontend.label`，其次使用字段 `comment`。所以你可以继续保留英文列名，同时通过中文 `comment` 或 `frontend.label` 生成中文表头、表单标签、查询条件、联表结果列名和排序字段文案。

同一个字段级 `frontend.label` 也会同步影响联表查询页面的结果列标题与排序字段标题，这样单表页面和联表页面的中文命名可以保持一致。

## 生成后的运行行为

- 请求 DTO 自动带校验注解
- Query DTO 自动校验 `page`、`size`、`sortDir`
- 全局异常处理不会把内部错误直接返回给前端
- 不存在资源时使用 `NotFoundException`
- `MybatisMetaObjectHandler` 会自动填充支持的日期时间字段

## 构建与测试命令

安装可编辑包：

```bash
python -m pip install -e .
```

运行 Python 测试：

```bash
python -m unittest discover -s tests -v
```

运行单个测试文件：

```bash
python -m unittest discover -s tests -p 'test_renderer.py' -v
```

运行单个测试方法：

```bash
python -m unittest discover -s tests -k test_render_application_uses_env_placeholders -v
```

语法检查：

```bash
python -m compileall codegen tests
```

编译生成出来的 Java 项目：

```bash
mvn package -DskipTests
```

构建生成出来的 Vue2 前端：

```bash
cd frontend
npm install
npm run build
```

## 推荐使用流程

1. 从 `examples/student_management.json` 或 `examples/sample.json` 开始改
2. 先补项目基础信息和表结构
3. 再逐步加查询条件、排序、索引、外键、联表关系
4. 如果需要前端，再补 `frontend` 和字段级前端配置
5. 生成项目
6. 执行 `init.sql`
7. 启动 Spring Boot 项目
8. 进入 `frontend/` 安装依赖并构建或启动前端
9. 用 `curl`、Apifox 或浏览器验证接口和页面

## 当前范围和限制

- 仅支持 Java 8
- 仅支持 Spring Boot 2.x
- 当前 SQL 和 datasource 主要面向 MySQL
- 前端目前只支持 Vue2 + Element UI
- 不生成 Java 测试类
- 复杂报表 SQL 暂时不在范围内

## 使用建议

- 最好显式填写 `databaseName`，不要完全依赖 JDBC URL 推断
- 只要开放排序，就尽量配置 `sortableFields`
- 想生成更贴近生产的 DDL，优先写显式 `foreignKeys`
- `created_at`、`updated_at` 这类自动填充字段不要手工从请求体里传

## License

当前仓库里还没有单独的许可证文件。
