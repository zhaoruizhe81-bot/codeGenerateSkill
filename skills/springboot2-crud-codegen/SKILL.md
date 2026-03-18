---
name: springboot2-crud-codegen
description: Work with the `springboot2-crud-codegen` repository to create or revise JSON configs, run the CLI, inspect generated Spring Boot 2 + MyBatis-Plus backends and optional Vue 2 admin frontends, diagnose config/schema/parser/render/template bugs, and extend generator features such as RBAC, multi-tenancy, Swagger/Knife4j, Excel import/export, file upload, operation log AOP, batch delete, dashboard stats, and MockMvc tests. Use when users ask to scaffold projects from this repo, edit `examples/*.json`, debug generation failures, inspect generated Java/SQL/Vue output, or change generator behavior in `codegen/*` or `codegen/templates/*`.
---

# springboot2-crud-codegen

- 先判定任务类型：编写配置、排查配置错误、生成并验收输出、修生成器、扩展新能力。
- 只读当前任务需要的参考资料：
  - `references/project-guide.md`：仓库结构、命令、测试方式、模块职责。
  - `references/config-guide.md`：JSON 结构、功能开关、字段级规则。
  - `references/task-playbook.md`：按任务类型拆好的执行步骤。
- 始终保持主流程稳定：`load -> validate -> parse -> render -> write`。
- 始终遵守项目边界：Java 8、Spring Boot 2.x、MySQL 导向 SQL、Vue 2 + Element UI、Python `unittest`。
- 遇到 RBAC 相关任务时，默认要同时核对角色名规范化、`init.sql` 种子、`UserDetailsServiceImpl` 授权逻辑、`@PreAuthorize` 表达式。
- 遇到“前端不同角色显示一样”这类 RBAC 任务时，默认还要核对 `/auth/me`、`frontend/src/utils/auth.js`、`router`、`Layout`、`dashboard` 和 CRUD 页按钮显隐是否闭环。
- 如果任务继续延伸到“权限再优化”，默认还要核对 `POST /import` 是否沿用 create 权限，以及登录后是否能回跳原始目标地址。
- 遇到 Swagger/Knife4j 相关任务时，默认要同时核对 `pom.xml`、`application.yml`、`WebSecurityConfig` 三处是否闭环。

## 默认执行流程

1. 选择最接近的示例配置作为起点。
   - 完整后台 + 权限 + 多租户 + 前端：`examples/sample_security.json` 或 `examples/preset_saas_multi_tenant.json`
   - 单表最小 CRUD：`examples/student_single_table.json`
   - 双表或联表：`examples/sample.json` 或 `examples/student_class_management.json`
   - 纯后台 API：`examples/preset_api_only.json`
   - 后台 + 前端 + 字典：`examples/preset_backend_frontend.json`
2. 先改配置或源码，再用真实命令验证；不要只靠静态阅读判断结果。
3. 每次配置改动后至少重新运行一次 `python -m codegen -c <config> -o <tmp>`，确认输出目录为 `<output>/<artifactId>/`。
4. 每次生成器行为改动后至少运行：
   - `python -m compileall codegen tests`
   - `python -m unittest discover -s tests -v`
5. 需要人工验收时，直接检查生成文件，而不是只看模板：
   - `backend/pom.xml`
   - `backend/src/main/resources/application.yml`
   - `backend/src/main/resources/init.sql`
   - `backend/src/main/java/.../security/*`
   - `backend/src/main/java/.../controller/*`
   - `backend/src/main/java/.../common/annotation/SystemLog.java`
   - `backend/src/main/java/.../common/aspect/SystemLogAspect.java`
   - `frontend/src/views/*`

## 模块定位

- `codegen/cli.py`：命令行参数、退出码、用户可见错误、`--force/--no-force`
- `codegen/schema.py`：JSON Schema 规则、必填项、枚举、额外字段限制、错误路径格式化
- `codegen/parser.py`：语义校验、IR 构建、RBAC 系统表暗注、联表/排序/操作符规则
- `codegen/parser.py`：也负责角色名规范化、默认注册角色兜底、RBAC 权限种子补齐
- `codegen/ir.py`：解析层到渲染层的内部契约
- `codegen/render.py`：后端/前端/SQL 文件渲染、导入、路径、代码片段拼装
- `codegen/templates/`：Jinja 模板本体
- `codegen/writer.py`：磁盘写入与覆盖策略

## 工作规则

- 优先从最近的示例配置增量修改，不要无依据地从空白 JSON 开始堆字段。
- 把 schema 错误和 parser 错误分开处理；前者看结构，后者看语义。
- 改 schema、parser、render 或模板行为时，同时更新示例、测试和文档。
- 改渲染结果时，同时读 `codegen/render.py` 和对应模板，避免只改一侧。
- 需要单测时，优先用 `unittest discover` 或文件粒度命令；不要使用 pytest node id，也不要用 `python -m unittest -v`。
