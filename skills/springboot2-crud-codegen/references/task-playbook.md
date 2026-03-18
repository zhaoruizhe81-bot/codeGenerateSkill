# 任务执行手册

## 目录

- [编写或修改配置](#编写或修改配置)
- [排查配置报错](#排查配置报错)
- [生成并验收输出](#生成并验收输出)
- [修改生成器实现](#修改生成器实现)
- [检查前端生成结果](#检查前端生成结果)

## 编写或修改配置

1. 先选最近的示例：
   - `examples/student_single_table.json`：单表 CRUD
   - `examples/sample.json`：基础双表与联表
   - `examples/student_class_management.json`：更完整的学生/班级管理
   - `examples/sample_security.json`：权限、多租户、前端、企业级能力
   - `examples/preset_api_only.json`：纯后台 API
   - `examples/preset_backend_frontend.json`：后台 + 前端 + 字典
   - `examples/preset_saas_multi_tenant.json`：多租户 SaaS
   - `examples/preset_audit_admin.json`：审计后台
   - `examples/preset_light_auth.json`：轻权限项目
2. 再读 `references/config-guide.md`，确认顶层键、`tables[]`、`relations[]`、`global`、`security`、`frontend` 的要求。
3. 增量修改配置，优先保持已有结构；不要一次性引入大量新字段。
4. 修改后立即运行：
   - `python -m codegen -c <config> -o /tmp/codegen-out`
5. 再检查 `<output>/<artifactId>/backend/src/main/resources/init.sql` 和核心 Java 文件是否与配置一致。
6. 如果改了 `security.rbac` 或 `global.enableSwagger`，额外检查：
   - `init.sql` 是否补齐默认角色和权限种子
   - `application.yml` 是否写入 `ant_path_matcher`
   - `WebSecurityConfig.java` 是否放行文档路径

## 排查配置报错

1. 先看报错来自哪一层：
   - 缺字段、枚举错误、额外字段：先看 `codegen/schema.py`
   - 主键、联表字段、操作符、排序白名单、隐式系统表：再看 `codegen/parser.py`
2. 结构错误时，回到 `references/config-guide.md` 对照合法骨架和字段约束。
3. 语义错误时，重点检查：
   - `tables[].primaryKey`
   - `tables[].queryableFields`
   - `tables[].sortableFields`
   - `relations[].on`
   - `relations[].select`
   - `relations[].filters`
4. 遇到权限相关问题时，记住 `security.enabled=true` 会暗注 5 张 RBAC 表，不要手动重复声明。
5. 遇到“注册成功但没权限 / 管理员进不去接口”这类问题时，优先检查角色名是否被规范成 `ROLE_*`，以及 `init.sql` 中是否真的存在默认注册角色和权限映射。
6. 遇到多租户场景下登录、注册、字典查询直接 500 时，优先检查生成的 `MybatisPlusConfig` 是否忽略了系统表，而不是先怀疑数据库本身。
7. 修完后重新运行 `python -m codegen -c <config> -o <tmp>`，不要只看 schema 是否通过。

## 生成并验收输出

1. 使用真实配置运行：
   - `python -m codegen -c <config> -o /tmp/codegen-out`
2. 先确认输出目录结构：
   - `<output>/<artifactId>/backend`
   - `<output>/<artifactId>/frontend`（仅当前端启用）
3. 验收后端关键文件：
   - `backend/pom.xml`
   - `backend/src/main/resources/application.yml`
   - `backend/src/main/resources/init.sql`
   - `backend/src/main/java/.../controller/*`
   - `backend/src/main/java/.../service/*`
   - `backend/src/main/resources/mapper/*`
4. 验收高级功能时重点看：
  - 权限：`.../security/*` 与 `AuthController`
  - 上传：`.../common/FileController.java`
  - 日志：`SystemLog.java` 与 `SystemLogAspect.java`
  - 仪表盘：`DashboardController.java`
  - 单测：`backend/src/test/java/.../controller/*Test.java`
   - Swagger：`application.yml`、`SwaggerConfig.java`、`WebSecurityConfig.java`
5. 最后运行基础校验：
   - `python -m compileall codegen tests`
   - `python -m unittest discover -s tests -v`

## 修改生成器实现

1. 先定位改动层：
   - CLI 与错误展示：`codegen/cli.py`
   - Schema：`codegen/schema.py`
   - 语义与 IR：`codegen/parser.py`、`codegen/ir.py`
   - 渲染：`codegen/render.py`
   - 模板：`codegen/templates/`
   - 写盘：`codegen/writer.py`
2. 改 schema 语义时，同时更新：
   - `codegen/schema.py`
   - `codegen/parser.py`（如果语义也变）
   - 示例配置
   - 对应测试
3. 改输出结构时，同时更新：
   - `codegen/render.py`
   - 对应模板
   - 断言具体路径或内容片段的测试
4. 改完后优先跑最窄测试，再跑全量：
   - `python -m unittest discover -s tests -p 'test_parser.py' -v`
   - `python -m unittest discover -s tests -p 'test_renderer.py' -v`
   - `python -m unittest discover -s tests -v`
5. 需要单个测试方法时，优先用：
   - `python -m unittest discover -s tests -k <substring> -v`
   - 如果本机 Python 不支持 `-k`，退回到文件粒度测试。

## 检查前端生成结果

1. 先确认顶层 `frontend.enabled=true`，并检查 `framework`、`locale`、`outputDir`、`backendUrl`、`devPort`。
2. 再检查表和字段上的 `frontend` 配置，尤其是：
   - `menuTitle`
   - `menuIcon`
   - `menuVisible`
   - `component`
   - `queryComponent`
   - `tableVisible`
   - `formVisible`
3. 上传组件问题优先检查字段 `frontend.component` 是否为 `image-upload` 或 `file-upload`，以及后端 `backend.uploadDir` 是否存在。
4. 表单校验问题优先检查字段的 `nullable`、`varchar(n)` 长度与生成的 `rules`。
5. 前端结果不对时，同时看：
   - `codegen/render.py`
   - 相关前端模板
   - 生成后的 `frontend/src/views/*`
6. 如果问题与权限有关，额外检查：
   - 生成后的 `frontend/src/api/auth.js`
   - 生成后的 `frontend/src/utils/auth.js`
   - 生成后的 `frontend/src/router/index.js`
   - 生成后的 `frontend/src/layout/Layout.vue`
   - 生成后的 `frontend/src/views/*/index.vue`
7. 不要只验证“有没有 token”；要验证 `/auth/me` 的 `roles` / `permissions` 是否真的参与了路由守卫、菜单过滤、仪表盘入口过滤和 CRUD 按钮显隐。
8. 如果继续做权限优化，再额外验证：
   - 登录成功后是否会回跳到 `redirect` 指向的原始地址
   - `POST /import` 是否和 create 使用同一套角色/权限规则
