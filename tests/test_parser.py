from __future__ import annotations

import json
import unittest
from pathlib import Path

from codegen.parser import ConfigError, parse_config


class ParserTest(unittest.TestCase):
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

    def test_like_on_non_string_should_fail(self) -> None:
        broken = json.loads(json.dumps(self.sample_payload))
        broken["tables"][0]["queryableFields"] = [
            {"name": "status", "operator": "LIKE"}
        ]

        with self.assertRaises(ConfigError):
            parse_config(broken)

    def test_range_on_string_should_fail(self) -> None:
        broken = json.loads(json.dumps(self.sample_payload))
        broken["tables"][0]["queryableFields"] = [
            {"name": "username", "operator": "GE"}
        ]

        with self.assertRaises(ConfigError):
            parse_config(broken)

    def test_invalid_index_field_should_fail(self) -> None:
        broken = json.loads(json.dumps(self.student_class_payload))
        broken["tables"][1]["indexes"] = [{"columns": ["missing_column"]}]

        with self.assertRaises(ConfigError):
            parse_config(broken)

    def test_invalid_foreign_key_reference_should_fail(self) -> None:
        broken = json.loads(json.dumps(self.student_class_payload))
        broken["tables"][1]["foreignKeys"] = [
            {
                "columns": ["class_id"],
                "refTable": "classes",
                "refColumns": ["missing_id"],
            }
        ]

        with self.assertRaises(ConfigError):
            parse_config(broken)

    def test_invalid_sortable_field_should_fail(self) -> None:
        broken = json.loads(json.dumps(self.sample_payload))
        broken["tables"][1]["sortableFields"] = ["missing_field"]

        with self.assertRaises(ConfigError):
            parse_config(broken)

    def test_relation_filter_param_keeps_camel_case(self) -> None:
        project = parse_config(self.sample_payload)

        self.assertEqual(project.relations[0].filters[0].param_name, "orderNo")
        self.assertEqual(project.relations[0].filters[1].param_name, "username")

    def test_parse_explicit_indexes_foreign_keys_and_sorting(self) -> None:
        project = parse_config(self.student_class_payload)
        classes_table = next(item for item in project.tables if item.name == "classes")
        students_table = next(
            item for item in project.tables if item.name == "students"
        )
        relation = project.relations[0]

        self.assertEqual(project.datasource["databaseName"], "student_class_demo")
        self.assertTrue(classes_table.infer_indexes)
        self.assertTrue(students_table.infer_foreign_keys)
        self.assertGreaterEqual(len(students_table.indexes), 1)
        self.assertGreaterEqual(len(students_table.foreign_keys), 1)
        self.assertEqual(students_table.sortable_fields[0].request_name, "studentName")
        self.assertEqual(relation.sortable_fields[0].request_name, "studentName")

    def test_parse_frontend_config(self) -> None:
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
            "menuIcon": "el-icon-user",
            "menuVisible": True,
        }
        payload["tables"][0]["fields"][1]["frontend"] = {
            "label": "Login Name",
            "component": "textarea",
            "queryComponent": "text",
            "tableVisible": False,
            "formVisible": True,
            "detailVisible": True,
            "queryVisible": True,
            "placeholder": "Enter username",
            "options": [],
        }
        payload["relations"][0]["frontend"] = {
            "menuTitle": "Order User Report",
            "menuIcon": "el-icon-data-analysis",
            "menuVisible": True,
        }

        project = parse_config(payload)

        self.assertTrue(project.frontend.enabled)
        self.assertEqual(project.frontend.framework, "vue2")
        self.assertEqual(project.frontend.locale, "en-US")
        self.assertEqual(project.frontend.output_dir, "frontend")
        self.assertEqual(project.frontend.app_title, "Demo Admin")
        self.assertEqual(project.frontend.backend_url, "http://127.0.0.1:8080")
        self.assertEqual(project.frontend.dev_port, 8081)
        self.assertEqual(project.tables[0].frontend.menu_title, "User Center")
        self.assertEqual(project.tables[0].frontend.menu_icon, "el-icon-user")
        self.assertFalse(project.tables[0].fields[1].frontend.table_visible)
        self.assertEqual(project.tables[0].fields[1].frontend.label, "Login Name")
        self.assertEqual(project.tables[0].fields[1].frontend.component, "textarea")
        self.assertEqual(project.relations[0].frontend.menu_title, "Order User Report")

    def test_parse_frontend_defaults_to_zh_cn_locale(self) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["frontend"] = {
            "enabled": True,
            "framework": "vue2",
            "outputDir": "frontend",
        }

        project = parse_config(payload)

        self.assertEqual(project.frontend.locale, "zh-CN")

    def test_invalid_frontend_locale_should_fail(self) -> None:
        payload = json.loads(json.dumps(self.sample_payload))
        payload["frontend"] = {
            "enabled": True,
            "framework": "vue2",
            "locale": "ja-JP",
            "outputDir": "frontend",
        }

        with self.assertRaises(ConfigError):
            parse_config(payload)


if __name__ == "__main__":
    unittest.main()
