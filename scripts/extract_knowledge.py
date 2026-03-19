#!/usr/bin/env python3
"""
知识抽取工具 — 基于 BKN schema 从文档中自动抽取知识实例。

通过 ``codex exec`` 调用 LLM，按 BKN 对象/关系定义提取结构化数据，
输出为可直接导入数据库的 CSV 文件。

Usage::

    python scripts/extract_knowledge.py <doc_path> [options]

Examples::

    # 基本用法
    python scripts/extract_knowledge.py "AnyBackup Family 8 AnyShare备份恢复用户指南.docx"

    # 指定模型和输出目录
    python scripts/extract_knowledge.py doc.docx --model o3 --output-dir data/

    # 仅生成 prompt（不调用 codex）
    python scripts/extract_knowledge.py doc.docx --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema data structures
# ---------------------------------------------------------------------------

@dataclass
class PropertyDef:
    name: str
    display_name: str
    prop_type: str
    description: str


@dataclass
class ObjectTypeDef:
    id: str
    name: str
    description: str
    properties: list[PropertyDef] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)


@dataclass
class RelationEndpoint:
    source: str
    target: str
    rel_type: str


@dataclass
class MappingRule:
    source_property: str
    target_property: str


@dataclass
class RelationTypeDef:
    id: str
    name: str
    description: str
    endpoint: RelationEndpoint | None = None
    mapping_rules: list[MappingRule] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BKN schema parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML frontmatter between ``---`` markers."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = val[1:-1]
            result[key.strip()] = val
    return result


def _parse_md_table(text: str, section_header: str) -> list[dict[str, str]]:
    """Return rows of a Markdown table under a ``### <section_header>`` heading."""
    pattern = rf"###\s+{re.escape(section_header)}\s*\n\n?"
    m = re.search(pattern, text)
    if not m:
        return []

    table_lines: list[str] = []
    for line in text[m.end():].splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break

    if len(table_lines) < 3:
        return []

    headers = [h.strip() for h in table_lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for tl in table_lines[2:]:
        cells = [c.strip() for c in tl.split("|")[1:-1]]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def parse_object_type(filepath: Path) -> ObjectTypeDef:
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    desc_m = re.search(r"\*\*.*?\*\*\s*-\s*(.+)", text)
    desc = desc_m.group(1).strip() if desc_m else ""

    props: list[PropertyDef] = []
    for row in _parse_md_table(text, "Data Properties"):
        props.append(PropertyDef(
            name=row.get("Name", ""),
            display_name=row.get("Display Name", ""),
            prop_type=row.get("Type", "string"),
            description=row.get("Description", ""),
        ))

    pk_m = re.search(r"Primary Keys:\s*(.+)", text)
    pks = [k.strip() for k in pk_m.group(1).split(",")] if pk_m else ["id"]

    return ObjectTypeDef(
        id=fm.get("id", filepath.stem),
        name=fm.get("name", ""),
        description=desc,
        properties=props,
        primary_keys=pks,
    )


def parse_relation_type(filepath: Path) -> RelationTypeDef:
    text = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)

    desc_m = re.search(r"\*\*.*?\*\*\s*-\s*(.+)", text)
    desc = desc_m.group(1).strip() if desc_m else ""

    endpoint: RelationEndpoint | None = None
    ep_rows = _parse_md_table(text, "Endpoint")
    if ep_rows:
        r = ep_rows[0]
        endpoint = RelationEndpoint(
            source=r.get("Source", ""),
            target=r.get("Target", ""),
            rel_type=r.get("Type", "direct"),
        )

    mappings: list[MappingRule] = []
    for r in _parse_md_table(text, "Mapping Rules"):
        mappings.append(MappingRule(
            source_property=r.get("Source Property", ""),
            target_property=r.get("Target Property", ""),
        ))

    return RelationTypeDef(
        id=fm.get("id", filepath.stem),
        name=fm.get("name", ""),
        description=desc,
        endpoint=endpoint,
        mapping_rules=mappings,
    )


def load_bkn_schema(
    bkn_dir: Path,
) -> tuple[list[ObjectTypeDef], list[RelationTypeDef]]:
    """Load all object & relation type definitions from *bkn_dir*."""
    objects: list[ObjectTypeDef] = []
    relations: list[RelationTypeDef] = []

    obj_dir = bkn_dir / "object_types"
    if obj_dir.is_dir():
        for f in sorted(obj_dir.glob("*.bkn")):
            objects.append(parse_object_type(f))

    rel_dir = bkn_dir / "relation_types"
    if rel_dir.is_dir():
        for f in sorted(rel_dir.glob("*.bkn")):
            relations.append(parse_relation_type(f))

    return objects, relations


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------

def build_extraction_prompt(
    doc_path: str,
    objects: list[ObjectTypeDef],
    relations: list[RelationTypeDef],
) -> str:
    lines = [
        "你是一个知识抽取专家。请从指定文档中抽取结构化知识数据。",
        "",
        "## 任务",
        "",
        f"阅读文档 `{doc_path}`，根据以下 BKN schema 定义，"
        "抽取所有对象实例和关系实例。",
        "",
        "## Schema 定义",
        "",
        "### 对象类型",
        "",
    ]

    for obj in objects:
        lines.append(f"#### {obj.id} ({obj.name})")
        lines.append(f"说明: {obj.description}")
        props_desc = ", ".join(
            f"{p.name} ({p.prop_type}, {p.display_name})" for p in obj.properties
        )
        lines.append(f"属性: {props_desc}")
        lines.append(f"主键: {', '.join(obj.primary_keys)}")
        lines.append("")

    lines += ["### 关系类型", ""]

    for rel in relations:
        lines.append(f"#### {rel.id} ({rel.name})")
        lines.append(f"说明: {rel.description}")
        if rel.endpoint:
            lines.append(
                f"方向: {rel.endpoint.source} → {rel.endpoint.target} "
                f"(类型: {rel.endpoint.rel_type})"
            )
        if rel.mapping_rules:
            lines.append(
                "映射: "
                + ", ".join(
                    f"{m.source_property} → {m.target_property}"
                    for m in rel.mapping_rules
                )
            )
        if rel.endpoint:
            lines.append(
                f"CSV 列: {rel.endpoint.source}_id, "
                f"{rel.endpoint.target}_id, relation_type_id"
            )
        lines.append("")

    lines += [
        "## 抽取规则",
        "",
        "1. 所有实例必须严格来源于文档内容，不得臆造或添加文档中未提及的内容",
        "2. id 使用小写英文加下划线，简洁且有语义，保证唯一性",
        "3. 描述文字直接使用文档原文或基于原文的准确概括",
        "4. 关系实例中的 relation_type_id 必须使用对应的关系类型 id",
        "5. 确保引用完整性：关系实例中引用的对象 id 必须在对象实例中存在",
        '6. 不要出现"同上"等引用性描述，每条记录的描述必须完整独立',
        "",
        "## 输出格式",
        "",
        "请直接输出 JSON（不要包裹在 markdown 代码块中），结构如下：",
        "",
        "{",
        '  "objects": {',
    ]

    for i, obj in enumerate(objects):
        example = ", ".join(f'"{p.name}": "..."' for p in obj.properties)
        comma = "," if i < len(objects) - 1 else ""
        lines.append(f'    "{obj.id}": [{{{example}}}]{comma}')

    lines += ["  },", '  "relations": {']

    for i, rel in enumerate(relations):
        if rel.endpoint:
            example = (
                f'"{rel.endpoint.source}_id": "...", '
                f'"{rel.endpoint.target}_id": "...", '
                f'"relation_type_id": "{rel.id}"'
            )
        else:
            example = '"...": "..."'
        comma = "," if i < len(relations) - 1 else ""
        lines.append(f'    "{rel.id}": [{{{example}}}]{comma}')

    lines += ["  }", "}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output JSON Schema (for ``codex exec --output-schema``)
# ---------------------------------------------------------------------------

def build_output_schema(
    objects: list[ObjectTypeDef],
    relations: list[RelationTypeDef],
) -> dict:
    obj_props: dict = {}
    for obj in objects:
        item_props = {p.name: {"type": "string"} for p in obj.properties}
        obj_props[obj.id] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": item_props,
                "required": [p.name for p in obj.properties],
            },
        }

    rel_props: dict = {}
    for rel in relations:
        item_props: dict = {"relation_type_id": {"type": "string"}}
        required = ["relation_type_id"]
        if rel.endpoint:
            src_fk = f"{rel.endpoint.source}_id"
            tgt_fk = f"{rel.endpoint.target}_id"
            item_props[src_fk] = {"type": "string"}
            item_props[tgt_fk] = {"type": "string"}
            required = [src_fk, tgt_fk, "relation_type_id"]
        rel_props[rel.id] = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": item_props,
                "required": required,
            },
        }

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "objects": {
                "type": "object",
                "properties": obj_props,
                "required": list(obj_props),
            },
            "relations": {
                "type": "object",
                "properties": rel_props,
                "required": list(rel_props),
            },
        },
        "required": ["objects", "relations"],
    }


# ---------------------------------------------------------------------------
# Codex invocation
# ---------------------------------------------------------------------------

def invoke_codex(
    prompt: str,
    output_schema_path: Path,
    output_path: Path,
    *,
    model: str | None = None,
    working_dir: Path | None = None,
    timeout: int = 600,
) -> str:
    """Call ``codex exec`` and return its final-message content."""
    cmd: list[str] = [
        "codex", "exec",
        "--full-auto",
        "--output-schema", str(output_schema_path),
        "-o", str(output_path),
    ]
    if model:
        cmd.extend(["-m", model])
    if working_dir:
        cmd.extend(["-C", str(working_dir)])
    cmd.append(prompt)

    print(f"  调用: codex exec -m {model or 'default'} ...", file=sys.stderr)
    print(f"  工作目录: {working_dir or '.'}", file=sys.stderr)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        raise RuntimeError(
            f"codex exec failed (exit {result.returncode}): "
            f"{result.stderr[:500]}"
        )

    if not output_path.exists():
        raise RuntimeError(f"codex 未生成输出文件: {output_path}")

    return output_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------

def parse_extraction_result(raw: str) -> dict:
    """Extract the JSON object from codex output (may contain surrounding text)."""
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(raw[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 codex 输出中解析 JSON（前 300 字符）:\n{raw[:300]}")


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

_BOM = "\ufeff"


def write_object_csv(
    output_dir: Path,
    obj_type: ObjectTypeDef,
    instances: list[dict],
) -> Path:
    filepath = output_dir / f"{obj_type.id}.csv"
    columns = [p.name for p in obj_type.properties]

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(_BOM)
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for inst in instances:
            writer.writerow(inst)
    return filepath


def write_relation_csv(
    output_dir: Path,
    rel_type: RelationTypeDef,
    instances: list[dict],
) -> Path:
    filepath = output_dir / f"relations_{rel_type.id}.csv"

    if rel_type.endpoint:
        columns = [
            f"{rel_type.endpoint.source}_id",
            f"{rel_type.endpoint.target}_id",
            "relation_type_id",
        ]
    elif instances:
        columns = list(instances[0].keys())
    else:
        columns = []

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(_BOM)
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for inst in instances:
            writer.writerow(inst)
    return filepath


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_result(
    data: dict,
    objects: list[ObjectTypeDef],
    relations: list[RelationTypeDef],
) -> list[str]:
    """Return a list of human-readable warnings (empty == OK)."""
    warnings: list[str] = []
    obj_data = data.get("objects", {})
    rel_data = data.get("relations", {})

    for obj in objects:
        if obj.id not in obj_data:
            warnings.append(f"缺少对象类型 {obj.id} 的实例")
        elif not obj_data[obj.id]:
            warnings.append(f"对象类型 {obj.id} 没有实例数据")

    for rel in relations:
        if rel.id not in rel_data:
            warnings.append(f"缺少关系类型 {rel.id} 的实例")

    all_obj_ids: dict[str, set[str]] = {}
    for obj in objects:
        ids = {
            inst.get("id", "") for inst in obj_data.get(obj.id, []) if inst.get("id")
        }
        all_obj_ids[obj.id] = ids

    for rel in relations:
        if not rel.endpoint:
            continue
        src_fk = f"{rel.endpoint.source}_id"
        tgt_fk = f"{rel.endpoint.target}_id"
        src_ids = all_obj_ids.get(rel.endpoint.source, set())
        tgt_ids = all_obj_ids.get(rel.endpoint.target, set())

        for inst in rel_data.get(rel.id, []):
            src_val = inst.get(src_fk, "")
            if src_val and src_val not in src_ids:
                warnings.append(
                    f"关系 {rel.id}: {src_fk}={src_val} "
                    f"不存在于 {rel.endpoint.source} 实例中"
                )
            tgt_val = inst.get(tgt_fk, "")
            if tgt_val and tgt_val not in tgt_ids:
                warnings.append(
                    f"关系 {rel.id}: {tgt_fk}={tgt_val} "
                    f"不存在于 {rel.endpoint.target} 实例中"
                )

    return warnings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="基于 BKN schema 从文档中自动抽取知识实例",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            '  python scripts/extract_knowledge.py "用户指南.docx"\n'
            "  python scripts/extract_knowledge.py doc.docx -m o3 --output-dir data/\n"
            "  python scripts/extract_knowledge.py doc.docx --dry-run\n"
        ),
    )
    parser.add_argument("doc_path", help="待抽取的文档路径 (DOCX/TXT)")
    parser.add_argument(
        "--bkn-dir", default="bkn", help="BKN schema 目录 (default: bkn)"
    )
    parser.add_argument(
        "--output-dir", default="data", help="CSV 输出目录 (default: data)"
    )
    parser.add_argument("--model", "-m", default=None, help="LLM 模型 (如 o3, o4-mini)")
    parser.add_argument(
        "--dry-run", action="store_true", help="只生成 prompt 和 schema，不调用 codex"
    )
    parser.add_argument("--working-dir", "-C", default=None, help="codex 工作目录")
    parser.add_argument(
        "--timeout", type=int, default=600, help="codex 超时秒数 (default: 600)"
    )

    args = parser.parse_args(argv)

    bkn_dir = Path(args.bkn_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    doc_path = Path(args.doc_path)
    working_dir = (
        Path(args.working_dir).resolve()
        if args.working_dir
        else doc_path.parent.resolve()
    )

    if not bkn_dir.is_dir():
        print(f"错误: BKN 目录不存在: {bkn_dir}", file=sys.stderr)
        return 1

    # ---- Step 1: Parse BKN schema ----
    print(">> 解析 BKN schema ...", file=sys.stderr)
    objects, relations = load_bkn_schema(bkn_dir)
    print(
        f"   对象类型: {len(objects)} ({', '.join(o.id for o in objects)})",
        file=sys.stderr,
    )
    print(
        f"   关系类型: {len(relations)} ({', '.join(r.id for r in relations)})",
        file=sys.stderr,
    )

    # ---- Step 2: Build prompt ----
    print(">> 生成抽取提示词 ...", file=sys.stderr)
    prompt = build_extraction_prompt(str(doc_path), objects, relations)

    # ---- Step 3: Build output schema ----
    print(">> 生成输出 JSON Schema ...", file=sys.stderr)
    output_schema = build_output_schema(objects, relations)

    if args.dry_run:
        print("\n=== PROMPT ===\n", file=sys.stderr)
        print(prompt, file=sys.stderr)
        print("\n=== OUTPUT SCHEMA ===\n", file=sys.stderr)
        print(json.dumps(output_schema, indent=2, ensure_ascii=False), file=sys.stderr)
        print("\n[dry-run] 跳过 codex 调用", file=sys.stderr)
        return 0

    # ---- Step 4: Call codex ----
    print(">> 调用 codex exec 进行知识抽取 ...", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmpdir:
        schema_file = Path(tmpdir) / "output_schema.json"
        result_file = Path(tmpdir) / "result.json"

        schema_file.write_text(
            json.dumps(output_schema, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        try:
            raw_output = invoke_codex(
                prompt=prompt,
                output_schema_path=schema_file,
                output_path=result_file,
                model=args.model,
                working_dir=working_dir,
                timeout=args.timeout,
            )
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"错误: {e}", file=sys.stderr)
            return 1

    # ---- Step 5: Parse result ----
    print(">> 解析抽取结果 ...", file=sys.stderr)
    try:
        data = parse_extraction_result(raw_output)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    # ---- Step 6: Validate ----
    print(">> 校验引用完整性 ...", file=sys.stderr)
    warnings = validate_result(data, objects, relations)
    for w in warnings:
        print(f"   WARN: {w}", file=sys.stderr)

    # ---- Step 7: Write CSVs ----
    print(f">> 写入 CSV 到 {output_dir}/ ...", file=sys.stderr)
    output_dir.mkdir(parents=True, exist_ok=True)

    obj_data = data.get("objects", {})
    rel_data = data.get("relations", {})

    for obj in objects:
        instances = obj_data.get(obj.id, [])
        fp = write_object_csv(output_dir, obj, instances)
        print(f"   {fp.name}: {len(instances)} 条", file=sys.stderr)

    for rel in relations:
        instances = rel_data.get(rel.id, [])
        fp = write_relation_csv(output_dir, rel, instances)
        print(f"   {fp.name}: {len(instances)} 条", file=sys.stderr)

    total_objs = sum(len(obj_data.get(o.id, [])) for o in objects)
    total_rels = sum(len(rel_data.get(r.id, [])) for r in relations)
    print(
        f"\n>> 完成: {total_objs} 个对象实例, {total_rels} 条关系实例",
        file=sys.stderr,
    )

    if warnings:
        print(f"   {len(warnings)} 个警告，请检查", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
