# Guardrails

## Sign: BKN 语法以 SPECIFICATION 为准

- **Trigger**: 编写或修改 `.bkn` 文件
- **Instruction**: 对照 `/Users/cx/Work/kweaver-ai/bkn-specification/docs/SPECIFICATION.md`；ObjectType 须含 Data Properties 与 Keys；RelationType direct 须含 Endpoint 与 Mapping Rules。

## Sign: CSV 列名与对象 Name 一致

- **Trigger**: 新增或修改 `data/*.csv`
- **Instruction**: 列名必须与对应 `object_type` 的 Data Properties `Name` 列完全一致；关系文件遵循 `relations_<relation_type_id>.csv` 约定。
