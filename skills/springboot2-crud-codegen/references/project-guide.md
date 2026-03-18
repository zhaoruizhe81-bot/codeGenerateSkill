# 项目总览

## 目录

- [仓库定位](#仓库定位)
- [先做任务分流](#先做任务分流)
- [核心流程](#核心流程)
- [模块职责](#模块职责)
- [示例配置起点](#示例配置起点)
- [关键命令](#关键命令)
- [测试与校验要点](#测试与校验要点)
- [重要输入与输出](#重要输入与输出)
- [项目边界](#项目边界)
- [修改时的仓库约束](#修改时的仓库约束)

## 仓库定位

`springboot2-crud-codegen` 是一个 Python CLI。它把 JSON 配置转换成企业级 Spring Boot 2 + MyBatis-Plus CRUD 工程，并可选生成独立 Vue 2 + Element UI 管理前端。

默认可生成或注入的能力包括：

- Spring Security + JWT + RBAC
- 多租户拦截器
- Swagger/Knife4j 文档
- Excel 导入/导出
- 文件上传
- 操作日志 AOP
- 批量删除
- 仪表盘统计
- MockMvc 单元测试
- 带表单校验的 Vue 2 管理前端

当前仓库里有两条容易踩坑的默认约束，排查时要优先想到：

- RBAC 角色名会在 parser 层统一规范成 `ROLE_*`，并同步影响 `init.sql`、注册默认角色、`@PreAuthorize` 与 `/me` 返回。
- 当前端启用且安全开启时，前端不会只看 token；还必须消费 `/auth/me`，并把角色/权限同时用在路由守卫、菜单、仪表盘入口和 CRUD 按钮显隐上。
- CRUD 周边动作也要闭环：`POST /import` 应与 create 权限一致，登录页成功后应尽量回跳到原始受保护地址。
- `global.enableSwagger = true` 时，除了依赖与 `SwaggerConfig`，还要检查生成的 `application.yml` 是否写入 `ant_path_matcher`，以及安全配置是否放行文档路径。
- `global.tenant.enabled = true` 时，多租户拦截器必须忽略系统表；认证、字典、日志相关问题优先检查 `MybatisPlusConfig` 里的 `ignoreTable` 逻辑。

## 先做任务分流

- 用户要“写配置 / 改配置”：先从示例配置开始，再读 `references/config-guide.md`
- 用户要“生成项目 / 检查输出”：先跑 CLI，再检查生成目录
- 用户要“修配置报错”：先判断是 schema 还是 parser 层
- 用户要“修生成器 bug / 扩能力”：先定位在 `cli`、`schema`、`parser`、`render`、`templates` 还是 `writer`

## 核心流程

仓库主流程固定为：`load -> validate -> parse -> render -> write`。

不要跳过中间层直接猜问题：配置是否有效看 `validate`，语义是否正确看 `parse`，输出内容是否正确看 `render`，落盘行为是否正确看 `write`。

## 模块职责

- `codegen/cli.py`：命令行参数、顶层错误处理、退出码、`--force/--no-force`
- `codegen/schema.py`：JSON Schema 定义、错误路径格式化
- `codegen/parser.py`：语义校验、IR 构建、RBAC 系统表暗注
- `codegen/ir.py`：`ProjectIR`、`TableIR`、`RelationIR` 等内部结构
- `codegen/render.py`：渲染后端、SQL、测试、前端等文件映射
- `codegen/type_mapping.py`：DB 类型、Java 类型、命名转换
- `codegen/writer.py`：把文件映射写入磁盘
- `codegen/templates/`：Jinja 模板目录

## 示例配置起点

- `examples/student_single_table.json`：单表 CRUD 最小起点
- `examples/sample.json`：双表与基础联表查询
- `examples/student_class_management.json`：更完整的教学管理示例
- `examples/sample_security.json`：权限、多租户、前端、企业级能力最全的起点
- `examples/preset_api_only.json`：纯后台 API 起步
- `examples/preset_backend_frontend.json`：后台 + 前端 + 字典起步
- `examples/preset_saas_multi_tenant.json`：SaaS 多租户起步
- `examples/preset_audit_admin.json`：审计型后台起步
- `examples/preset_light_auth.json`：轻权限起步

优先复制最近的示例再增量修改，不要从空白 JSON 开始拼大配置。

## 关键命令

- 安装：`python -m pip install -e .`
- 运行模块：`python -m codegen -c examples/sample_security.json -o /tmp/codegen-out`
- 运行控制台命令：`codegen -c examples/sample_security.json -o /tmp/codegen-out`
- 全量测试：`python -m unittest discover -s tests -v`
- 语法检查：`python -m compileall codegen tests`

## 测试与校验要点

- `tests/` 不是 Python package，不要用 `tests.test_xxx...` 这种 dotted path。
- 单文件测试可用：
  - `python -m unittest discover -s tests -p 'test_parser.py' -v`
  - `python -m unittest discover -s tests -p 'test_renderer.py' -v`
- 单方法测试优先用：
  - `python -m unittest discover -s tests -k <substring> -v`
- 不要使用：
  - pytest node id
  - `python -m unittest -v`

改行为时的最低验证标准：

1. `python -m compileall codegen tests`
2. `python -m unittest discover -s tests -v`
3. `python -m codegen -c <config> -o <tmp>`

## 重要输入与输出

- 典型输入：`examples/sample_security.json`
- 后端输出：`<output>/<artifactId>/backend/...`
- 前端输出：`<output>/<artifactId>/frontend/...`，仅在 `frontend.enabled = true` 时生成

常看生成文件：

- `backend/pom.xml`
- `backend/src/main/resources/application.yml`
- `backend/src/main/resources/init.sql`
- `backend/src/main/java/<basePackage>/security/*`
- `backend/src/main/java/<basePackage>/controller/*`
- `backend/src/main/java/<basePackage>/common/FileController.java`
- `backend/src/main/java/<basePackage>/common/annotation/SystemLog.java`
- `backend/src/main/java/<basePackage>/common/aspect/SystemLogAspect.java`
- `backend/src/main/java/<basePackage>/controller/DashboardController.java`
- `backend/src/test/java/<basePackage>/controller/*Test.java`
- `frontend/src/views/login/index.vue`
- `frontend/src/views/<xxx>/index.vue`
- `frontend/src/utils/request.js`
- `frontend/src/api/auth.js`
- `frontend/src/utils/auth.js`
- `frontend/src/router/index.js`
- `frontend/src/layout/Layout.vue`

权限或文档相关问题优先额外检查：

- `backend/src/main/java/<basePackage>/security/UserDetailsServiceImpl.java`
- `backend/src/main/java/<basePackage>/security/WebSecurityConfig.java`
- `backend/src/main/java/<basePackage>/config/SwaggerConfig.java`
- `frontend/src/api/auth.js`
- `frontend/src/utils/auth.js`
- `frontend/src/router/index.js`
- `frontend/src/layout/Layout.vue`

## 项目边界

- 仅支持 Java 8
- 仅支持 Spring Boot 2.x
- SQL 与 datasource 以 MySQL 为主
- 前端仅支持 Vue 2 + Element UI
- Python 测试框架是 `unittest`，不是 pytest

## 修改时的仓库约束

- 不要无声改变 schema 语义
- 改解析或渲染逻辑时，同时看模板和测试
- 改生成结构时，保证导入、路径、命名稳定且可重复生成
- 改 parser 或 render 行为时，优先补针对性的成功/失败测试
- 改模板时，同时检查对应的 `render.py` 分支和输出路径
- 改 RBAC 或 Swagger 行为时，同时更新仓库里的 Markdown 文档，避免 README、技能参考和代理说明出现旧规则
- 改前端权限行为时，同时更新仓库里的 Markdown 文档，避免 README、技能参考和代理说明继续描述“前端只看 token、不分角色”的旧行为
