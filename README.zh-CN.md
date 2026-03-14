# springboot2-crud-codegen

[English](README.md) | 简体中文

`springboot2-crud-codegen` 是一个高级的 Python CLI 工具，用来根据 JSON 配置生成企业级的 Spring Boot 2 + MyBatis-Plus CRUD 项目。

它不仅能快速搭建后台管理类接口项目，还超越了简单的 CRUD，内置生成了 **RBAC 权限安全体系**、**多租户隔离**、**Excel 导出**、**MockMvc 单元测试**，以及配套的独立 Vue 2 管理前端。

## 能生成什么

- 完整 Maven 项目结构
- 基于 Java 8 的 Spring Boot 2.x 工程
- 集成 Spring Security + JWT 的 RBAC 权限体系
- 自动生成完整的 `/register`（注册，密码 BCrypt 加密存储）、`/login`（登录）、`/me`（获取当前用户信息）三个认证接口
- 支持多租户拦截器（TenantLineInnerInterceptor）的单表 CRUD
- 联表分页查询接口与包含逻辑删除过滤的 MyBatis XML SQL
- 基于 EasyExcel 的数据导出接口 (`/export`)
- 全自动生成的 MockMvc 控制器单元测试 (`@WebMvcTest`)
- 请求 DTO 校验注解
- 统一返回结构 `Result<T>` 和 `PageResult<T>`
- 本地文件上传接口 (`FileController`) 及静态资源映射
- 包含内置 RBAC 系统表（`sys_user` 等）、外键、索引及种子数据的 `init.sql`
- 开箱即用的 Swagger/Knife4j API 接口文档
- 每张业务表自动生成 `POST /import` Excel 批量导入接口（EasyExcel）
- `POST /auth/change-password` 密码修改接口（验旧后 BCrypt 加密保存）
- 操作日志 AOP（`@SystemLog` 注解 + 切面 + `sys_log` 表，create/update/delete/import 自动留痕）
- 包含登录页、Axios 拦截器、上传组件、以及智能表单校验的独立 Vue2 + Element UI 管理前端

## 当前支持的能力

- **查询与关联**：单表与 Left/Inner Join 支持 `EQ`、`NE`、`LIKE`、`GT`、`GE`、`LT`、`LE`。
- **安全管控**：内置 JWT 生成与校验，接口生成 `@PreAuthorize` 注解，自动暗注 5 张标准 RBAC 权限表，并自动生成 **`/register`（BCrypt 加密注册）、`/login`（登录）、`/me`（返回当前用户角色 + 权限列表）** 三个开箱即用的完整鉴权接口。
- **多租户**：基于请求头 `X-Tenant-Id` 或 JWT Claim 实现请求级别的租户上下文绑定与数据隔离。
- **数据导出**：自动生成 `XxxExportDto` (带 `@ExcelProperty` 注解) 并利用 EasyExcel 写入响应流。
- **Excel 批量导入**：每张表自动生成 `POST /import` 接口，使用 EasyExcel 读取上传的表格并批量插入数据库。
- **密码修改**：`POST /auth/change-password` 接口先用 BCrypt 校验旧密码，再加密保存新密码。
- **操作日志 AOP**：`@SystemLog` 注解自动加到 create/update/delete/import 方法上，切面将操作者、URI、IP、时间存入 `sys_log` 表，零配置实现操作审计。
- **接口文档**: 根据表和字段注释自动整合 Swagger/Knife4j，自动生成完整的 `@Api`、`@ApiModelProperty` 等注解。
- **前端表单校验**: 根据字段是否必填以及数据库预设长度，自动在前端 Vue 页面中挂载含有 `:rules` 和 `maxlength` 的校验拦截逻辑。
- **前端生成**：动态路由、字典翻译、国际化切换 (`zh-CN` / `en-US`) 的全功能后台页面。

## 安装

```bash
python -m pip install -e .
```

## 快速开始

使用带有权限配置的示例生成项目：

```bash
python -m codegen -c examples/sample_security.json -o /tmp/codegen-out
```

输出目录结构类似：

```text
/tmp/codegen-out/<artifactId>/
```

常见生成文件：

- `pom.xml`（包含 Security, JJWT, EasyExcel 依赖）
- `src/main/resources/application.yml`
- `src/main/resources/init.sql`
- `src/main/java/<basePackage>/security/*`（JWT 过滤器、登录服务）
- `src/main/java/<basePackage>/controller/*`（包含鉴权注解和导出接口）
- `src/test/java/<basePackage>/controller/*Test.java`（单元测试）
- `frontend/src/views/login/index.vue`（前端登录页）

## 核心新配置规则说明

### 安全与权限 (`security`)

在顶层配置 `security` 即可开启 RBAC 和 JWT：

```json
"security": {
  "enabled": true,
  "jwt": {
    "secret": "my-super-secret-key-that-is-very-long",
    "expiration": 86400,
    "header": "Authorization",
    "prefix": "Bearer "
  },
  "rbac": {
    "superAdminRole": "ROLE_ADMIN"
  }
}
```
开启后，解析器会自动隐式注入 `sys_user`、`sys_role`、`sys_user_role` 等 5 张表及初始的 admin 用户数据。

自动生成以下三个开箱即用的认证接口：

| 端点 | 方法 | 是否需要鉴权 | 说明 |
|---|---|---|---|
| `/api/auth/login` | POST | 否 | 返回已签名的 JWT Token |
| `/api/auth/register` | POST | 否 | 创建账号，密码 BCrypt 加密，默认授予 `ROLE_USER` 角色 |
| `/api/auth/me` | GET | 是 | 返回当前用户名、角色列表以及按钮权限列表 |

你可以在具体业务表中配置 `auth` 来生成控制权限：

```json
"tables": [
  {
    "name": "orders",
    "auth": {
      "roles": ["ADMIN", "MANAGER"],
      "permissions": {
        "query": "order:view",
        "create": "order:add",
        "update": "order:edit",
        "delete": "order:delete"
      }
    }
  }
]
```

### 多租户 (`global.tenant`)

在 `global` 节点下开启：

```json
"global": {
  "tenant": {
    "enabled": true,
    "column": "tenant_id"
  }
}
```

### 接口文档 (`global.enableSwagger`)

在 `global` 节点下开启即可生成开箱即用的带有所有注释的 API 文档：

```json
"global": {
  "enableSwagger": true
}
```
开启后后端的项目 `pom.xml` 中将自动注入 `@github.xiaoymin:knife4j-spring-boot-starter` 依赖，并附带针对所有 DTO 类以及控制器的各种注解说明。

### 文件上传 (`backend.uploadDir`)

在 `backend` 节点中配置 `uploadDir` 设置本地上传目录。在字段的前端配置中，将 `component` 设置为 `image-upload` 或 `file-upload` 即可自动渲染上传组件。

## 构建与测试命令

安装可编辑包：

```bash
python -m pip install -e .
```

运行 Python 侧测试：

```bash
python -m unittest discover -s tests -v
```

语法检查：

```bash
python -m compileall codegen tests
```

编译生成出来的 Java 项目：

```bash
mvn package -DskipTests
```

## 当前范围和限制

- 仅支持 Java 8
- 仅支持 Spring Boot 2.x
- 当前 SQL 和 datasource 主要面向 MySQL
- 前端目前只支持 Vue2 + Element UI

## License

当前仓库里还没有单独的许可证文件。