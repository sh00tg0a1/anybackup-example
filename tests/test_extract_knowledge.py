"""tests for scripts.extract_knowledge — schema parsing, prompt, CSV, validation."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from scripts.extract_knowledge import (
    MappingRule,
    ObjectTypeDef,
    PropertyDef,
    RelationEndpoint,
    RelationTypeDef,
    build_extraction_prompt,
    build_output_schema,
    load_bkn_schema,
    parse_extraction_result,
    parse_object_type,
    parse_relation_type,
    validate_result,
    write_object_csv,
    write_relation_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BKN_DIR = REPO_ROOT / "bkn"


# ---------------------------------------------------------------------------
# Schema parsing
# ---------------------------------------------------------------------------


class TestSchemaParser:
    def test_parse_object_type_backup_software(self):
        obj = parse_object_type(BKN_DIR / "object_types" / "backup_software.bkn")
        assert obj.id == "backup_software"
        assert obj.name == "备份软件"
        prop_names = [p.name for p in obj.properties]
        assert prop_names == ["id", "name", "version", "description"]
        assert obj.primary_keys == ["id"]

    def test_parse_object_type_protected_application(self):
        obj = parse_object_type(
            BKN_DIR / "object_types" / "protected_application.bkn"
        )
        assert obj.id == "protected_application"
        assert len(obj.properties) == 5
        assert any(p.name == "backup_software_id" for p in obj.properties)

    def test_parse_relation_type(self):
        rel = parse_relation_type(
            BKN_DIR / "relation_types" / "rs_software_protects_app.bkn"
        )
        assert rel.id == "rs_software_protects_app"
        assert rel.endpoint is not None
        assert rel.endpoint.source == "backup_software"
        assert rel.endpoint.target == "protected_application"
        assert rel.endpoint.rel_type == "direct"
        assert len(rel.mapping_rules) == 1
        assert rel.mapping_rules[0].source_property == "id"
        assert rel.mapping_rules[0].target_property == "backup_software_id"

    def test_load_bkn_schema_counts(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        assert len(objects) == 10
        assert len(relations) == 8

    def test_load_bkn_schema_ids(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        obj_ids = {o.id for o in objects}
        expected_obj_ids = {
            "backup_software",
            "protected_application",
            "backup_method",
            "backup_scope",
            "recovery_scope",
            "recovery_method",
            "protection_option",
            "infra_component",
            "supported_database",
            "constraint",
        }
        assert obj_ids == expected_obj_ids

        rel_ids = {r.id for r in relations}
        expected_rel_ids = {
            "rs_software_protects_app",
            "rs_app_supports_backup_method",
            "rs_backup_method_applies_scope",
            "rs_app_recoverable_at_scope",
            "rs_recovery_scope_uses_method",
            "rs_software_provides_option",
            "rs_software_depends_component",
            "rs_app_uses_database",
        }
        assert rel_ids == expected_rel_ids


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------


class TestPromptGeneration:
    def test_prompt_contains_all_object_types(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        prompt = build_extraction_prompt("test.docx", objects, relations)
        for obj in objects:
            assert obj.id in prompt, f"object type {obj.id} missing from prompt"
            assert obj.name in prompt

    def test_prompt_contains_all_relation_types(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        prompt = build_extraction_prompt("test.docx", objects, relations)
        for rel in relations:
            assert rel.id in prompt, f"relation type {rel.id} missing from prompt"

    def test_prompt_includes_extraction_rules(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        prompt = build_extraction_prompt("test.docx", objects, relations)
        assert "引用完整性" in prompt
        assert "不得臆造" in prompt
        assert "同上" in prompt

    def test_prompt_includes_doc_path(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        prompt = build_extraction_prompt("my_doc.docx", objects, relations)
        assert "my_doc.docx" in prompt


# ---------------------------------------------------------------------------
# Output JSON Schema
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_schema_has_all_object_types(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        schema = build_output_schema(objects, relations)

        obj_schema = schema["properties"]["objects"]["properties"]
        for obj in objects:
            assert obj.id in obj_schema

    def test_schema_has_all_relation_types(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        schema = build_output_schema(objects, relations)

        rel_schema = schema["properties"]["relations"]["properties"]
        for rel in relations:
            assert rel.id in rel_schema

    def test_schema_is_valid_json(self):
        objects, relations = load_bkn_schema(BKN_DIR)
        schema = build_output_schema(objects, relations)
        serialized = json.dumps(schema, ensure_ascii=False)
        parsed = json.loads(serialized)
        assert parsed["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert parsed["required"] == ["objects", "relations"]

    def test_object_schema_properties_match_bkn(self):
        objects, _ = load_bkn_schema(BKN_DIR)
        schema = build_output_schema(objects, [])
        obj_schema = schema["properties"]["objects"]["properties"]

        bs = obj_schema["backup_software"]["items"]
        assert set(bs["properties"].keys()) == {"id", "name", "version", "description"}
        assert set(bs["required"]) == {"id", "name", "version", "description"}


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


class TestParseResult:
    def test_plain_json(self):
        data = '{"objects": {}, "relations": {}}'
        assert parse_extraction_result(data) == {"objects": {}, "relations": {}}

    def test_json_in_markdown_block(self):
        raw = 'Some text\n```json\n{"objects": {}, "relations": {}}\n```\nmore'
        result = parse_extraction_result(raw)
        assert "objects" in result

    def test_json_with_surrounding_text(self):
        raw = 'Result:\n{"objects": {"a": []}, "relations": {}}\nDone.'
        result = parse_extraction_result(raw)
        assert result["objects"]["a"] == []

    def test_invalid_raises_valueerror(self):
        with pytest.raises(ValueError, match="无法从 codex 输出中解析"):
            parse_extraction_result("this is not json at all")


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------


def _make_obj_type(obj_id: str = "test_obj") -> ObjectTypeDef:
    return ObjectTypeDef(
        id=obj_id,
        name="测试",
        description="测试对象",
        properties=[
            PropertyDef("id", "主键", "string", "唯一标识"),
            PropertyDef("name", "名称", "string", "名称"),
        ],
        primary_keys=["id"],
    )


def _make_rel_type(rel_id: str = "rs_test") -> RelationTypeDef:
    return RelationTypeDef(
        id=rel_id,
        name="测试关系",
        description="测试",
        endpoint=RelationEndpoint("src_type", "tgt_type", "direct"),
        mapping_rules=[MappingRule("id", "src_type_id")],
    )


class TestCSVWriter:
    def test_object_csv_filename_and_content(self):
        obj = _make_obj_type()
        instances = [{"id": "t1", "name": "测试1"}, {"id": "t2", "name": "测试2"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            fp = write_object_csv(Path(tmpdir), obj, instances)
            assert fp.name == "test_obj.csv"
            content = fp.read_text(encoding="utf-8-sig")
            assert "id,name" in content
            assert "t1,测试1" in content
            assert "t2,测试2" in content

    def test_object_csv_has_bom(self):
        obj = _make_obj_type()
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = write_object_csv(Path(tmpdir), obj, [{"id": "x", "name": "y"}])
            raw = fp.read_bytes()
            assert raw[:3] == b"\xef\xbb\xbf"

    def test_relation_csv_filename_and_columns(self):
        rel = _make_rel_type()
        instances = [
            {
                "src_type_id": "s1",
                "tgt_type_id": "t1",
                "relation_type_id": "rs_test",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            fp = write_relation_csv(Path(tmpdir), rel, instances)
            assert fp.name == "relations_rs_test.csv"
            content = fp.read_text(encoding="utf-8-sig")
            assert "src_type_id,tgt_type_id,relation_type_id" in content
            assert "s1,t1,rs_test" in content

    def test_object_csv_ignores_extra_fields(self):
        obj = _make_obj_type()
        instances = [{"id": "x", "name": "y", "extra_field": "ignored"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            fp = write_object_csv(Path(tmpdir), obj, instances)
            content = fp.read_text(encoding="utf-8-sig")
            assert "extra_field" not in content


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_data_no_warnings(self):
        objects = [_make_obj_type("a")]
        relations = [
            RelationTypeDef(
                id="r1",
                name="",
                description="",
                endpoint=RelationEndpoint("a", "b", "direct"),
            )
        ]
        data = {
            "objects": {"a": [{"id": "x1"}]},
            "relations": {"r1": []},
        }
        assert validate_result(data, objects, relations) == []

    def test_missing_object_type_warns(self):
        objects = [_make_obj_type("missing_type")]
        data = {"objects": {}, "relations": {}}
        warnings = validate_result(data, objects, [])
        assert any("缺少对象类型 missing_type" in w for w in warnings)

    def test_empty_instances_warns(self):
        objects = [_make_obj_type("empty_type")]
        data = {"objects": {"empty_type": []}, "relations": {}}
        warnings = validate_result(data, objects, [])
        assert any("没有实例数据" in w for w in warnings)

    def test_broken_reference_warns(self):
        objects = [_make_obj_type("src"), _make_obj_type("tgt")]
        relations = [
            RelationTypeDef(
                id="r1",
                name="",
                description="",
                endpoint=RelationEndpoint("src", "tgt", "direct"),
            )
        ]
        data = {
            "objects": {
                "src": [{"id": "s1"}],
                "tgt": [{"id": "t1"}],
            },
            "relations": {
                "r1": [
                    {
                        "src_id": "s1",
                        "tgt_id": "NONEXISTENT",
                        "relation_type_id": "r1",
                    }
                ],
            },
        }
        warnings = validate_result(data, objects, relations)
        assert any("NONEXISTENT" in w for w in warnings)
