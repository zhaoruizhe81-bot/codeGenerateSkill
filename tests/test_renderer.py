from __future__ import annotations

import json
import unittest
from pathlib import Path

from codegen.parser import parse_config
from codegen.render import CodeRenderer


class RendererTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.sample_payload = json.loads(
            (root / "examples" / "sample.json").read_text(encoding="utf-8")
        )
        self.student_class_payload = json.loads(
            (root / "examples" / "student_class_management.json").read_text(
                encoding="utf-8"
            )
        )
        self.sample_security_payload = json.loads(
            (root / "examples" / "sample_security.json").read_text(encoding="utf-8")
        )

    def test_render_application_uses_env_placeholders(self) -> None:
        project = parse_config(self.sample_payload)
        files = CodeRenderer().render_project(project)

        application_yml = files["backend/src/main/resources/application.yml"]
        self.assertIn(
            'url: "${DB_URL:jdbc:mysql://127.0.0.1:3306/demo?useSSL=false&serverTimezone=UTC&characterEncoding=UTF-8}"',
            application_yml,
        )
        self.assertIn('username: "${DB_USERNAME:root}"', application_yml)
        self.assertIn('password: "${DB_PASSWORD:root}"', application_yml)

    def test_render_create_and_update_dto_validation_annotations(self) -> None:
        project = parse_config(self.student_class_payload)
        files = CodeRenderer().render_project(project)

        create_dto = files[
            "backend/src/main/java/com/example/school/dto/StudentCreateRequest.java"
        ]
        update_dto = files[
            "backend/src/main/java/com/example/school/dto/StudentUpdateRequest.java"
        ]

        self.assertIn("import javax.validation.constraints.NotBlank;", create_dto)
        self.assertIn("import javax.validation.constraints.NotNull;", create_dto)
        self.assertIn("import javax.validation.constraints.Size;", create_dto)
        self.assertIn('@NotBlank(message = "studentNo must not be blank")', create_dto)
        self.assertIn(
            '@Size(max = 32, message = "studentNo length must be <= 32")', create_dto
        )
        self.assertIn('@NotNull(message = "classId must not be null")', create_dto)
        self.assertNotIn("createdAt", create_dto)
        self.assertNotIn("updatedAt", create_dto)
        self.assertIn(
            '@Size(max = 32, message = "studentNo length must be <= 32")', update_dto
        )
        self.assertNotIn("@NotBlank", update_dto)

    def test_render_query_dto_supports_sorting_and_validation(self) -> None:
        project = parse_config(self.student_class_payload)
        files = CodeRenderer().render_project(project)

        query_dto = files[
            "backend/src/main/java/com/example/school/dto/StudentQueryRequest.java"
        ]
        relation_query_dto = files[
            "backend/src/main/java/com/example/school/dto/PageStudentWithClassQuery.java"
        ]

        self.assertIn("import javax.validation.constraints.Max;", query_dto)
        self.assertIn("import javax.validation.constraints.Min;", query_dto)
        self.assertIn("import javax.validation.constraints.Pattern;", query_dto)
        self.assertIn('@Min(value = 1, message = "page must be >= 1")', query_dto)
        self.assertIn(
            '@Pattern(regexp = "ASC|DESC|asc|desc", message = "sortDir must be ASC or DESC")',
            query_dto,
        )
        self.assertIn("private String sortBy;", query_dto)
        self.assertIn("private String sortDir;", query_dto)
        self.assertIn("private String sortBy;", relation_query_dto)
        self.assertIn("private String sortDir;", relation_query_dto)

    def test_render_init_sql_contains_explicit_and_inferred_constraints(self) -> None:
        project = parse_config(self.student_class_payload)
        files = CodeRenderer().render_project(project)

        init_sql = files["backend/src/main/resources/init.sql"]
        self.assertIn("CREATE DATABASE IF NOT EXISTS `student_class_demo`", init_sql)
        self.assertIn("USE `student_class_demo`", init_sql)
        self.assertIn("KEY `idx_students_student_name` (`student_name`)", init_sql)
        self.assertIn("KEY `idx_students_class_id` (`class_id`)", init_sql)
        self.assertIn(
            "CONSTRAINT `fk_students_classes_student_class` FOREIGN KEY (`class_id`) REFERENCES `classes` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT",
            init_sql,
        )
        self.assertIn("INSERT INTO `students`", init_sql)
        self.assertIn("Li Lei", init_sql)

    def test_render_meta_object_handler_for_auto_fill_fields(self) -> None:
        project = parse_config(self.student_class_payload)
        files = CodeRenderer().render_project(project)

        handler = files[
            "backend/src/main/java/com/example/school/config/MybatisMetaObjectHandler.java"
        ]

        self.assertIn("implements MetaObjectHandler", handler)
        self.assertIn('strictInsertFill(metaObject, "createdAt"', handler)
        self.assertIn('strictInsertFill(metaObject, "updatedAt"', handler)
        self.assertIn('strictUpdateFill(metaObject, "updatedAt"', handler)

    def test_render_tenant_config_ignores_system_tables(self) -> None:
        payload = json.loads(json.dumps(self.sample_security_payload))
        payload["global"]["tenant"] = {"enabled": True, "column": "tenant_id"}

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        config_java = files[
            "backend/src/main/java/com/example/admin/config/MybatisPlusConfig.java"
        ]

        self.assertIn('"sys_user".equalsIgnoreCase(tableName)', config_java)
        self.assertIn('"sys_role".equalsIgnoreCase(tableName)', config_java)
        self.assertIn('"sys_dict_type".equalsIgnoreCase(tableName)', config_java)
        self.assertIn('"sys_log".equalsIgnoreCase(tableName)', config_java)

    def test_render_service_and_relation_mapper_support_extended_operators_and_sorting(
        self,
    ) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["tables"][1]["queryableFields"] = [
            {"name": "order_no", "operator": "LIKE"},
            {"name": "amount", "operator": "GE"},
            {"name": "user_id", "operator": "NE"},
        ]
        payload["tables"][1]["sortableFields"] = ["created_at", "amount"]
        payload["relations"][0]["filters"] = [
            {
                "table": "orders",
                "field": "order_no",
                "operator": "LIKE",
                "param": "orderNo",
            },
            {
                "table": "orders",
                "field": "amount",
                "operator": "GE",
                "param": "minAmount",
            },
            {
                "table": "users",
                "field": "username",
                "operator": "LIKE",
                "param": "username",
            },
        ]
        payload["relations"][0]["sortableFields"] = [
            {"table": "orders", "field": "created_at", "name": "createdAt"},
            {"table": "users", "field": "username", "name": "username"},
        ]

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        service_impl = files[
            "backend/src/main/java/com/example/demo/service/impl/OrderServiceImpl.java"
        ]
        mapper_xml = files["backend/src/main/resources/mapper/OrderMapper.xml"]
        relation_query = files[
            "backend/src/main/java/com/example/demo/dto/PageOrderWithUserQuery.java"
        ]

        self.assertIn("wrapper.ge(Order::getAmount, query.getAmount())", service_impl)
        self.assertIn("wrapper.ne(Order::getUserId, query.getUserId())", service_impl)
        self.assertIn("query.getSortBy()", service_impl)
        self.assertIn("orderBy", service_impl)
        self.assertIn("AND l.amount >= #{query.minAmount}", mapper_xml)
        self.assertIn("ORDER BY", mapper_xml)
        self.assertIn("l.created_at", mapper_xml)
        self.assertIn("r.username", mapper_xml)
        self.assertIn("private BigDecimal minAmount;", relation_query)
        self.assertIn("private String sortBy;", relation_query)

    def test_render_global_exception_handler_hides_internal_errors(self) -> None:
        project = parse_config(self.sample_payload)
        files = CodeRenderer().render_project(project)

        exception_handler = files[
            "backend/src/main/java/com/example/demo/exception/GlobalExceptionHandler.java"
        ]

        self.assertIn("LoggerFactory", exception_handler)
        self.assertIn("DataIntegrityViolationException", exception_handler)
        self.assertIn(
            '"operation failed due to related data constraints"', exception_handler
        )
        self.assertIn("Result.failure(ErrorCode.INTERNAL_ERROR)", exception_handler)
        self.assertNotIn(
            "ex.getMessage()", exception_handler.split("handleException")[1]
        )

    def test_render_common_result_and_service_support_export_and_upload(self) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["frontend"] = {
            "enabled": True,
            "framework": "vue2",
            "locale": "zh-CN",
        }
        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        result_java = files[
            "backend/src/main/java/com/example/demo/common/Result.java"
        ]
        service_java = files[
            "backend/src/main/java/com/example/demo/service/UserService.java"
        ]
        service_impl_java = files[
            "backend/src/main/java/com/example/demo/service/impl/UserServiceImpl.java"
        ]
        file_controller_java = files[
            "backend/src/main/java/com/example/demo/common/FileController.java"
        ]

        self.assertIn("public static <T> Result<T> error(int code, String message)", result_java)
        self.assertIn("List<User> list();", service_java)
        self.assertIn("public List<User> list()", service_impl_java)
        self.assertIn("return userMapper.selectList(null);", service_impl_java)
        self.assertIn("return Result.error(400, \"File is empty\");", file_controller_java)

    def test_render_security_user_details_handles_integer_enabled_flag(self) -> None:
        project = parse_config(self.sample_security_payload)
        files = CodeRenderer().render_project(project)

        user_details = files[
            "backend/src/main/java/com/example/admin/security/UserDetailsServiceImpl.java"
        ]
        init_sql = files["backend/src/main/resources/init.sql"]

        self.assertIn("sysUser.getEnabled() != null && sysUser.getEnabled() != 0", user_details)
        self.assertIn("registerUser", user_details)
        self.assertIn("passwordEncoder.encode", user_details)
        self.assertIn('DEFAULT_ROLE_CODES = Arrays.asList("ROLE_USER")', user_details)
        self.assertIn('authority = "ROLE_" + authority;', user_details)
        self.assertIn('Missing default registration role: ', user_details)
        self.assertIn("$2y$10$6nO2SjLp7N7EoenOqL8bgOHwNHF9h3Gq8rivStyFnx/SnwbBSfcBa", init_sql)

        auth_controller = files[
            "backend/src/main/java/com/example/admin/security/AuthController.java"
        ]
        self.assertIn("/register", auth_controller)
        self.assertIn("/me", auth_controller)
        self.assertIn("SecurityContextHolder", auth_controller)

        web_security = files[
            "backend/src/main/java/com/example/admin/security/WebSecurityConfig.java"
        ]
        self.assertIn("/auth/register", web_security)

    def test_render_security_swagger_and_rbac_bootstrap_are_aligned(self) -> None:
        payload = json.loads(json.dumps(self.sample_security_payload))
        payload["global"]["enableSwagger"] = True

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        init_sql = files["backend/src/main/resources/init.sql"]
        application_yml = files["backend/src/main/resources/application.yml"]
        web_security = files[
            "backend/src/main/java/com/example/admin/security/WebSecurityConfig.java"
        ]
        controller_java = files[
            "backend/src/main/java/com/example/admin/controller/ProductController.java"
        ]
        pom_xml = files["backend/pom.xml"]

        self.assertIn("matching-strategy: ant_path_matcher", application_yml)
        self.assertIn('"/doc.html"', web_security)
        self.assertIn('"/v2/api-docs"', web_security)
        self.assertIn("knife4j-spring-boot-starter", pom_xml)
        self.assertIn("hasAnyRole('ADMIN', 'MANAGER')", controller_java)
        self.assertIn('@PostMapping("/import")', controller_java)
        self.assertEqual(controller_java.count("@PreAuthorize(\"hasAnyRole('ADMIN', 'MANAGER')\")"), 6)
        self.assertIn("'ROLE_ADMIN'", init_sql)
        self.assertIn("'ROLE_USER'", init_sql)
        self.assertIn("'product:force_delete'", init_sql)

    def test_render_security_frontend_uses_me_for_route_menu_and_button_permissions(
        self,
    ) -> None:
        payload = json.loads(json.dumps(self.sample_security_payload))
        payload["frontend"] = {
            "enabled": True,
            "framework": "vue2",
            "locale": "en-US",
            "outputDir": "frontend",
            "appTitle": "Secure Admin",
            "backendUrl": "http://127.0.0.1:8080",
            "devPort": 8081,
        }

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        router_js = files["frontend/src/router/index.js"]
        layout_vue = files["frontend/src/layout/Layout.vue"]
        dashboard_vue = files["frontend/src/views/dashboard/index.vue"]
        request_js = files["frontend/src/utils/request.js"]
        auth_api = files["frontend/src/api/auth.js"]
        auth_util = files["frontend/src/utils/auth.js"]
        login_vue = files["frontend/src/views/login/index.vue"]
        products_view = files["frontend/src/views/products/index.vue"]

        self.assertIn("ensureCurrentUser", router_js)
        self.assertIn('"roles": ["ROLE_ADMIN", "ROLE_MANAGER"]', router_js)
        self.assertIn('"permissions": ["product:force_delete"]', products_view)
        self.assertIn("findFirstAccessiblePath", router_js)
        self.assertIn("filteredMenuGroups", layout_vue)
        self.assertIn("hasAccess(item.auth)", layout_vue)
        self.assertIn("visibleQuickLinks", dashboard_vue)
        self.assertIn("hasAccess(page.route_auth)", dashboard_vue)
        self.assertIn("fetchAuthMe", auth_api)
        self.assertIn("ensureCurrentUser", auth_util)
        self.assertIn("hasAccess(rule, currentUser = getCurrentUser())", auth_util)
        self.assertIn("window.location.hash = \"#/login\"", request_js)
        self.assertIn("setToken(token)", login_vue)
        self.assertIn("const redirectPath = this.$route.query.redirect || '/'", login_vue)
        self.assertIn("Secure Admin Login", login_vue)
        self.assertIn("const actionAuth =", products_view)
        self.assertIn("v-if=\"canCreate\"", products_view)
        self.assertIn("v-if=\"canUpdate\"", products_view)
        self.assertIn("v-if=\"canDelete\"", products_view)
        self.assertIn("v-if=\"canSave\"", products_view)
        self.assertIn("this.$message.error(\"You do not have permission to perform this action\")", products_view)

    def test_render_dictionaries_generate_backend_frontend_and_excel_mapping(self) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["security"] = {
            "enabled": True,
            "jwt": {"secret": "my-super-secret-key-that-is-very-long"},
        }
        payload["frontend"] = {
            "enabled": True,
            "framework": "vue2",
            "locale": "en-US",
            "outputDir": "frontend",
            "appTitle": "Demo Admin",
            "backendUrl": "http://127.0.0.1:8080",
            "devPort": 8081,
        }
        payload["dictionaries"] = [
            {
                "key": "user_status",
                "name": "User Status",
                "valueType": "integer",
                "items": [
                    {"label": "Disabled", "value": 0, "sort": 10, "enabled": True},
                    {"label": "Enabled", "value": 1, "sort": 20, "enabled": True},
                ],
            }
        ]
        payload["tables"][0]["fields"][2]["dictKey"] = "user_status"
        payload["relations"][0]["select"].append(
            {"table": "users", "field": "status", "alias": "userStatus"}
        )
        payload["relations"][0]["filters"].append(
            {"table": "users", "field": "status", "operator": "EQ", "param": "status"}
        )

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        init_sql = files["backend/src/main/resources/init.sql"]
        user_export_dto = files[
            "backend/src/main/java/com/example/demo/dto/UserExportDto.java"
        ]
        user_controller = files[
            "backend/src/main/java/com/example/demo/controller/UserController.java"
        ]
        dictionary_controller = files[
            "backend/src/main/java/com/example/demo/controller/DictionaryController.java"
        ]
        dictionary_service = files[
            "backend/src/main/java/com/example/demo/service/impl/DictionaryServiceImpl.java"
        ]
        users_view = files["frontend/src/views/users/index.vue"]
        relation_view = files["frontend/src/views/relations/order-user/index.vue"]
        dictionary_util = files["frontend/src/utils/dictionary.js"]
        dictionary_api = files["frontend/src/api/dictionary.js"]

        self.assertIn("CREATE TABLE IF NOT EXISTS `sys_dict_type`", init_sql)
        self.assertIn("INSERT INTO `sys_dict_type`", init_sql)
        self.assertIn("user_status", init_sql)
        self.assertIn("system:dict-type:view", init_sql)
        self.assertIn("system:dict-item:view", init_sql)
        self.assertIn("private String status;", user_export_dto)
        self.assertIn('dictionaryService.resolveLabel("user_status"', user_controller)
        self.assertIn('dictionaryService.resolveValue("user_status"', user_controller)
        self.assertIn('@GetMapping("/{dictKey}/items")', dictionary_controller)
        self.assertIn("listEnabledOptions", dictionary_service)
        self.assertIn("dictionaryOptions['user_status']", users_view)
        self.assertIn('import { loadDictionaryOptions, formatDictionaryValue } from "@/utils/dictionary"', users_view)
        self.assertIn("dictionaryOptions", relation_view)
        self.assertIn("fetchDictionaryItems", dictionary_api)
        self.assertIn("formatDictionaryValue", dictionary_util)

    def test_render_dictionaries_without_security_do_not_emit_security_imports(self) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["dictionaries"] = [
            {
                "key": "user_status",
                "name": "User Status",
                "valueType": "integer",
                "items": [
                    {"label": "Disabled", "value": 0},
                    {"label": "Enabled", "value": 1},
                ],
            }
        ]
        payload["tables"][0]["fields"][2]["dictKey"] = "user_status"

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        dict_type_controller = files[
            "backend/src/main/java/com/example/demo/controller/SysDictTypeController.java"
        ]
        system_log_aspect = files[
            "backend/src/main/java/com/example/demo/common/aspect/SystemLogAspect.java"
        ]

        self.assertNotIn("PreAuthorize", dict_type_controller)
        self.assertNotIn("SecurityContextHolder", system_log_aspect)

    def test_render_vue2_frontend_project(self) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["frontend"] = {
            "enabled": True,
            "framework": "vue2",
            "locale": "en-US",
            "outputDir": "frontend",
            "appTitle": "Demo Admin",
            "backendUrl": "http://127.0.0.1:8080",
            "devPort": 8081,
        }
        payload["tables"][0]["frontend"] = {
            "menuTitle": "User Center",
            "menuIcon": "el-icon-user-solid",
        }
        payload["tables"][0]["fields"][1]["frontend"] = {
            "label": "Login Name",
            "component": "textarea",
            "tableVisible": False,
            "formVisible": True,
            "detailVisible": True,
            "queryVisible": True,
            "placeholder": "Type username",
        }
        payload["tables"][0]["fields"][2]["frontend"] = {
            "component": "select",
            "queryComponent": "select",
            "options": [
                {"label": "Disabled", "value": 0},
                {"label": "Enabled", "value": 1},
            ],
        }
        payload["relations"][0]["frontend"] = {
            "menuTitle": "Order User Report",
            "menuIcon": "el-icon-data-analysis",
        }

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        package_json = files["frontend/package.json"]
        router_js = files["frontend/src/router/index.js"]
        layout_vue = files["frontend/src/layout/Layout.vue"]
        request_js = files["frontend/src/utils/request.js"]
        users_api = files["frontend/src/api/users.js"]
        orders_api = files["frontend/src/api/orders.js"]
        users_view = files["frontend/src/views/users/index.vue"]
        relation_view = files["frontend/src/views/relations/order-user/index.vue"]
        main_js = files["frontend/src/main.js"]
        public_html = files["frontend/public/index.html"]

        self.assertIn('"vue": "^2.7.16"', package_json)
        self.assertIn('"element-ui": "^2.15.14"', package_json)
        self.assertIn("/users", router_js)
        self.assertIn("/relations/order-user", router_js)
        self.assertIn("User Center", layout_vue)
        self.assertIn("el-icon-user-solid", layout_vue)
        self.assertIn("Order User Report", layout_vue)
        self.assertNotIn("element-ui/lib/locale/lang/zh-CN", main_js)
        self.assertIn('<html lang="en-US">', public_html)
        self.assertIn("response.data.code !== 0", request_js)
        self.assertIn('const baseUrl = "/users"', users_api)
        self.assertIn("fetchUsersPage", users_api)
        self.assertIn("createUser", users_api)
        self.assertIn("fetchPageOrderWithUser", orders_api)
        self.assertIn("el-table", users_view)
        self.assertIn("sortBy", users_view)
        self.assertIn("el-dialog", users_view)
        self.assertIn('prop="username"', users_view)
        self.assertIn("Login Name", users_view)
        self.assertIn("Type username", users_view)
        self.assertIn('label="Enabled"', users_view)
        self.assertIn('label="Disabled"', users_view)
        self.assertIn("textarea", users_view)
        self.assertIn("fetchPageOrderWithUser", relation_view)

    def test_render_vue2_frontend_defaults_to_zh_cn_and_uses_chinese_labels(
        self,
    ) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["frontend"] = {
            "enabled": True,
            "framework": "vue2",
            "outputDir": "frontend",
            "appTitle": "学生管理后台",
            "backendUrl": "http://127.0.0.1:8080",
            "devPort": 8081,
        }
        payload["tables"][0]["frontend"] = {
            "menuTitle": "用户管理",
            "menuIcon": "el-icon-user-solid",
        }
        payload["tables"][0]["fields"][1]["comment"] = "login account"
        payload["tables"][0]["fields"][1]["frontend"] = {
            "label": "登录名",
            "tableVisible": True,
            "queryVisible": True,
            "formVisible": True,
            "detailVisible": True,
        }
        payload["tables"][0]["fields"][2]["frontend"] = {
            "label": "状态",
            "component": "select",
            "queryComponent": "select",
            "options": [
                {"label": "禁用", "value": 0},
                {"label": "启用", "value": 1},
            ],
        }
        payload["tables"][1]["fields"][1]["comment"] = "order code"
        payload["tables"][1]["fields"][1]["frontend"] = {"label": "订单编号"}
        payload["relations"][0]["frontend"] = {
            "menuTitle": "订单用户报表",
            "menuIcon": "el-icon-data-analysis",
        }

        project = parse_config(payload)
        files = CodeRenderer().render_project(project)

        router_js = files["frontend/src/router/index.js"]
        layout_vue = files["frontend/src/layout/Layout.vue"]
        dashboard_vue = files["frontend/src/views/dashboard/index.vue"]
        users_view = files["frontend/src/views/users/index.vue"]
        relation_view = files["frontend/src/views/relations/order-user/index.vue"]
        main_js = files["frontend/src/main.js"]
        public_html = files["frontend/public/index.html"]
        format_js = files["frontend/src/utils/format.js"]
        request_js = files["frontend/src/utils/request.js"]

        self.assertEqual(project.frontend.locale, "zh-CN")
        self.assertIn('import locale from "element-ui/lib/locale/lang/zh-CN"', main_js)
        self.assertIn('Vue.use(ElementUI, { size: "small", locale })', main_js)
        self.assertIn('<html lang="zh-CN">', public_html)
        self.assertIn("此页面需要启用 JavaScript 才能运行。", public_html)
        self.assertIn('meta: { title: "仪表盘", auth: { enabled: false, roles: [], permissions: [] } }', router_js)
        self.assertIn("仪表盘", layout_vue)
        self.assertIn("filteredMenuGroups", layout_vue)
        self.assertIn('"title": "\\u6570\\u636e\\u7ba1\\u7406"', layout_vue)
        self.assertIn('"title": "\\u5173\\u8054\\u89c6\\u56fe"', layout_vue)
        self.assertIn("Vue2 管理工作台", layout_vue)
        self.assertIn("快速导航", dashboard_vue)
        self.assertIn("打开已生成的数据模块与关联查询页面。", dashboard_vue)
        self.assertIn("查询", users_view)
        self.assertIn("重置", users_view)
        self.assertIn("新增", users_view)
        self.assertIn("操作", users_view)
        self.assertIn("详情", users_view)
        self.assertIn("编辑", users_view)
        self.assertIn("删除", users_view)
        self.assertIn("记录详情", users_view)
        self.assertIn("请输入登录名", users_view)
        self.assertIn("请选择排序字段", users_view)
        self.assertIn("升序", users_view)
        self.assertIn("降序", users_view)
        self.assertIn("创建成功", users_view)
        self.assertIn("删除成功", users_view)
        self.assertIn('label="启用"', users_view)
        self.assertIn('label="禁用"', users_view)
        self.assertIn("登录名", users_view)
        self.assertIn("订单编号", relation_view)
        self.assertIn("登录名", relation_view)
        self.assertIn("查询", relation_view)
        self.assertIn('placeholder="请输入登录名"', users_view)
        self.assertNotIn("请输入请输入", users_view)
        self.assertIn('return value ? "是" : "否"', format_js)
        self.assertIn('Message.error(payload.message || "请求失败")', request_js)


if __name__ == "__main__":
    unittest.main()
