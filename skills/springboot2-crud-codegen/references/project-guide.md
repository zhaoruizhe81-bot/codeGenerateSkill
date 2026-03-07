# 项目总览

## 仓库定位

`springboot2-crud-codegen` 是一个 Python CLI。它把 JSON 配置转换成企业级可运行的 Spring Boot 2 + MyBatis-Plus CRUD 工程（内置 Spring Security, JJWT, EasyExcel, MockMvc 测试，多租户），并生成带有种子数据的 `init.sql`；启用 `frontend` 后，还能生成包含登录逻辑的独立 Vue2 + Element UI 管理前端。

## 核心流程

仓库主流程固定为：`load -> validate -> parse -> render -> write`。

- `codegen/cli.py`：解析命令行参数、处理退出码、调用主流程。
- `codegen/schema.py`：定义 JSON Schema，并把 schema 报错格式化成 `tables[0].field` 风格路径。
- `codegen/parser.py`：做语义校验并把配置转换成内部 IR；这也是处理 **RBAC 系统表隐式注入（暗注）** 的核心。
- `codegen/ir.py`：定义 `ProjectIR`、`TableIR`、`RelationIR`、`SecurityIR`、`TenantIR` 等数据结构。
- `codegen/render.py`：把 IR 渲染为内存中文件映射；负责后端、SQL、导出 DTO、单元测试、联表查询（自带 logicDelete 过滤）、可选前端。
- `codegen/writer.py`：把文件映射写到磁盘。
- `codegen/templates/`：Jinja 模板，包含 `test/` 目录和 `security/` 目录等高级企业级特性模板。

## 重要输入与输出

- 典型输入：`examples/sample_security.json`
- 典型输出：`<output>/<artifactId>/backend/...`
- 前端输出：`<output>/<artifactId>/frontend/...`，仅当顶层 `frontend.enabled = true`

常见输出文件：

- `backend/pom.xml`（包含 spring-boot-starter-security, jjwt, easyexcel 等）
- `backend/src/main/resources/application.yml`
- `backend/src/main/resources/init.sql`（包含生成的业务表与 RBAC 五张系统表）
- `backend/src/main/java/<basePackage>/security/WebSecurityConfig.java` 等
- `backend/src/main/java/<basePackage>/common/FileController.java` (本地上传接口)
- `backend/src/test/java/<basePackage>/controller/XxxControllerTest.java` (MockMvc 单元测试)
- `frontend/src/views/login/index.vue`
- `frontend/src/utils/request.js` (含 Token 注入与 401 拦截)

## 关键命令

- 安装：`python -m pip install -e .`
- 运行示例：`python -m codegen -c examples/sample_security.json -o /tmp/codegen-out`
- 控制台命令：`codegen -c examples/sample_security.json -o /tmp/codegen-out`
- 全量测试：`python -m unittest discover -s tests -v`
- 语法检查：`python -m compileall codegen tests`

## 项目边界

- 仅支持 Java 8。
- 仅支持 Spring Boot 2.x。
- SQL 和 datasource 以 MySQL 为主。
- 前端仅支持 Vue2 + Element UI。
- Python 测试框架是 `unittest`，不是 pytest。

## 修改时的仓库约束

- 不要无声改变 schema 语义。
- 改解析或渲染逻辑时，同时看模板和测试。
- 改生成结构时，确保导入、路径、命名保持稳定且可重复生成。