# 配置文档

## 目录

- [先记住这 8 条](#先记住这-8-条)
- [顶层结构](#顶层结构)
- [安全与权限配置 (Security/RBAC)](#安全与权限配置-securityrbac)
- [多租户配置 (Multi-tenancy)](#多租户配置-multi-tenancy)
- [后端与其他配置](#后端与其他配置)
- [`tables[]` 完整说明](#tables-完整说明)
- [文件上传组件](#文件上传组件)
- [`relations[]` 完整说明](#relations-完整说明)
- [数据导出与测试生成](#数据导出与测试生成)

## 先记住这 8 条

1. 几乎所有对象都不允许出现未声明字段；多写一个键也会报错，因为 schema 大量使用了 `additionalProperties: false`。
2. 顶层必须有 `project`、`datasource`、`tables`、`relations`、`global`；`security`、`backend`、`frontend` 可选。
3. 如果开启 `security.enabled`，不要手动在 JSON 里建 `sys_user` 这种表，parser 会在内存里自动暗注给你！
4. `queryableFields` 在每张表里也是必填；如果不需要查询条件，写空数组 `[]`。
5. `relations` 顶层也是必填；如果没有联表关系，写空数组 `[]`。
6. `bootVersion` 必须以 `2.` 开头，`javaVersion` 当前只能是 `8`。
7. 单表和联表排序都必须显式走白名单，不能自由传任意字段名。
8. 联表查询遇到含有 `logicDelete: true` 的表时，渲染层会自动给你补上 `AND is_deleted = 0` 的判断。

## 顶层结构

合法骨架建议写成这样：

```json
{
  "project": {},
  "datasource": {},
  "security": {},
  "backend": {},
  "frontend": {},
  "tables": [],
  "relations": [],
  "global": {}
}
```

## 安全与权限配置 (Security/RBAC)

这部分配置负责生成 Spring Security + JWT，以及五张核心系统表。

### 顶层 `security`
```json
"security": {
  "enabled": true,
  "type": "jwt",
  "jwt": {
    "secret": "your-256-bit-secret-string",
    "expiration": 86400,
    "header": "Authorization",
    "prefix": "Bearer "
  },
  "rbac": {
    "strategy": "role_permission",
    "superAdminRole": "ROLE_ADMIN"
  }
}
```
**行为说明**：
- 一旦 `enabled: true`，生成的项目 `pom.xml` 自动引入 Security 和 JJWT。
- 自动生成 `WebSecurityConfig`、`JwtTokenUtil`、`AuthController` 等核心类。
- 生成三个开箱即用的认证接口：
  - `POST /api/auth/login` — 验证账密，返回 JWT Token
  - `POST /api/auth/register` — 注册新账号（BCrypt 加密密码，默认授予 `ROLE_USER` 角色）
  - `GET /api/auth/me` — 凭 Token 返回当前用户名 + 角色 + 权限列表（便于前端渲染菜单权限）
- Parser 会隐式生成 `sys_user`, `sys_role`, `sys_user_role`, `sys_menu_permission`, `sys_role_permission` 这 5 张表的 Entity, Mapper, Service, Controller。
- 默认在 `init.sql` 里塞入账号 `admin` / 密码 `123456`（经过 BCrypt 加密）的数据。

### 表级/关联级的 `auth`
```json
"tables": [
  {
    "name": "products",
    "auth": {
      "enabled": true,
      "roles": ["ADMIN", "MANAGER"],
      "permissions": {
        "query": "product:view",
        "create": "product:add",
        "update": "product:edit",
        "delete": "product:delete"
      }
    }
  }
]
```
**行为说明**：
- 如果没有写 `auth.permissions`，Parser 会自动按 `<table_name>:view` 这类规则兜底补全。
- 生成 Controller 时，会拼接为：`@PreAuthorize("hasAnyRole('ADMIN', 'MANAGER') or hasAuthority('product:add')")`。

## 全局功能特性 (Global Features)

除了常规的实体生成，可以在 `global` 下开启额外的拦截器或 API 增强。

### 多租户配置 (Multi-tenancy)

通过 MyBatis-Plus `TenantLineInnerInterceptor` 实现请求级别隔离。

```json
"global": {
  "apiPrefix": "/api",
  "author": "codegen",
  "dateTimeFormat": "yyyy-MM-dd HH:mm:ss",
  "enableSwagger": false,
  "tenant": {
    "enabled": true,
    "column": "tenant_id"
  }
}
```
**行为说明**：
- 开启后，生成的 `MybatisPlusConfig.java` 注入多租户拦截器。
- `JwtAuthenticationFilter` 会自动尝试从 HTTP Header 的 `X-Tenant-Id` 或 JWT claims 里读取 tenant ID 存入 `TenantContextHolder` (ThreadLocal)。
- 之后所有增删改查 SQL MyBatis-Plus 都会自动拼上 `WHERE tenant_id = ?`。

### Swagger/Knife4j 接口文档生成

这部分配置负责自动引入依赖和生成详尽的接口文档注释配置。

```json
"global": {
  "enableSwagger": true
}
```
**行为说明**：
- 当 `enableSwagger: true` 时，生成的后端 `pom.xml` 中将自动注入 `@github.xiaoymin:knife4j-spring-boot-starter` 依赖。
- 生成一个支持分组的全局 `SwaggerConfig.java` 配置文件。
- 自动分析所有表(`table.comment`)及字段(`field.comment`)信息，利用 `@Api`、`@ApiOperation`、`@ApiModel`、`@ApiModelProperty` 等注解在生成的 Controller、Entities 以及 DTO 类上提供清晰友好的文档注释。启动后可访问 `/doc.html` 查看。

## 后端与其他配置

### `backend`
```json
"backend": {
  "outputDir": "backend",
  "uploadDir": "uploads"
}
```
- `uploadDir` 会在生成的项目中产生一个 `FileController.java`，暴露 `/api/common/upload` 端点供前端调用。该端点将文件存入本地该目录，并提供静态资源映射。

## `tables[]` 完整说明

必填字段：`name`, `comment`, `entityName`, `fields`, `primaryKey`, `queryableFields`。

### 逻辑删除与联表
如果你的表中配置了：
```json
{"name": "is_deleted", "type": "tinyint(1)", "logicDelete": true, "comment": "是否删除"}
```
工具不仅为它加上 `@TableLogic`，而且当这表参与 `relations` 联查时，Mapper XML 会智能探测到，并在 `WHERE 1=1` 后强行加上 `AND l.is_deleted = 0` 防止脏数据泄露！

## 文件上传组件

在 `fields[].frontend.component` 中支持新组件：
- `image-upload`
- `file-upload`

配置示例：
```json
"frontend": {
  "label": "产品封面",
  "component": "image-upload"
}
```
渲染层在遇到这两个组件时，不仅会输出 `<el-upload>`，还会自动获取 JWT Token (`localStorage.getItem('token')`) 注入请求头，防止上传接口报 401 错误。

## 智能前端表单校验 (Vue Form Validation)

生成器能够通过提取数据库字段的约束要求，自动在 `<el-form>` 以及 `$data.formRules` 中埋入对应的校验逻辑。这是**开箱即用**的功能。

- **必填校验 (`required`)**：如果某个字段设为 `nullable: false`，则会在 `rules` 里自动生成 `{ required: true, message: "xxx is required", trigger: "..." }`，在前端弹窗点击”保存“时自动拦截空输入。
- **长度校验 (`max`)**：如果字段类型为 `varchar(50)` (即携带最大长度约束的 `db_type`)，表单验证规则会自动附加上 `{ max: 50, message: "长度不能超过 50 个字符" }`。

## `relations[]` 完整说明

每一个 relation 都会生成一个只读联表分页接口。

必填：`name`, `leftTable`, `rightTable`, `joinType`, `dtoName`, `methodName`, `on`, `select`, `filters`。

注意：现在联表接口同样受 `relation.auth` 的权限保护。

## 数据导出与测试生成

这两个特性**开箱即用，无需额外 JSON 配置**：

1. **Excel 导出**：每个普通的 Table 都会生成一个 `XxxExportDto.java` 类（字段自动打上中文的 `@ExcelProperty`），Controller 里自动暴露 `@GetMapping("/export")` 端点，流式输出 Excel 文件。
2. **单元测试**：生成器会在 `src/test/java/.../controller/` 目录下为所有表生成基于 `@WebMvcTest` + `@MockBean` 的 Spring Boot 集成测试代码，确保项目交付即拥有基础覆盖率。
