# AGENTS.md

本文件定义本仓库（灾备 BKN / CSV）的 Agent 工作规则。规范权威来源：`/Users/cx/Work/kweaver-ai/bkn-specification`。

---

## 1. 规范前置（强制）

- **MUST** 在本仓库做任何 BKN 或 CSV 产出前，先阅读以下文档：
  - `/Users/cx/Work/kweaver-ai/bkn-specification/docs/SPECIFICATION.md`（至少：Frontmatter、ObjectType、RelationType、文件组织、数据文件 CSV 一节）
  - `/Users/cx/Work/kweaver-ai/bkn-specification/docs/ARCHITECTURE.md`（类型职责与架构）
- 重大歧义以 SPECIFICATION.md 为准；英文版 `SPECIFICATION.en.md` 可作对照。

---

## 2. 本仓库领域与版本边界

- **领域**：灾备 / 备份业务知识网络，面向灾备管理员的**指导性知识**（非具体服务器实例）。
- **MUST 包含**的业务对象类型（`object_type`）：
  - 核心：`backup_software`（备份软件）、`protected_application`（被保护应用）
  - 备份操作：`backup_method`（备份方式）、`backup_scope`（备份范围）
  - 恢复操作：`recovery_scope`（恢复范围）、`recovery_method`（恢复方式）
  - 保护特性：`protection_option`（保护选项）
  - 基础设施：`infra_component`（基础设施组件）、`supported_database`（支持的数据库类型）
  - 约束：`constraint`（使用约束）
- **MUST NOT** 建模 `action_type`（及工具/MCP/调度等），除非用户明确要求。
- **SHOULD NOT** 新增 `risk_type`，除非用户明确要求。
- **CSV 实例数据**：MUST 严格来源于权威文档（如《AnyBackup Family 8 AnyShare 备份恢复用户指南》），不得臆造超出文档范畴的实例。
- **SHOULD 包含**：`network.bkn`、与对象配套的 `relation_type`、可选的 `concept_group`

---

## 3. BKN 编写规则

- **id**：MUST 使用小写字母、数字、下划线；显示名与描述默认中文。
- **文件组织**：MUST 与 bkn-specification 一致；**允许**将全部 `object_type` / `relation_type` / `concept_group` 合并进单个 `network.bkn`（本仓库采用单文件），**或**按规范拆分为 `object_types/`、`relation_types/` 等目录（每类型一文件）。
- **RelationType**：
  - `Endpoint` 的 `Source` / `Target` MUST 为已声明的 `object_type` id
  - `direct` 关系 MUST 给出与映射字段一致的 `Mapping Rules`
- **MUST NOT** 生成规范禁止的补丁/删除类型文件（更新语义以文件 upsert 为主）。

---

## 4. CSV 实例数据规则（对接数据库导入）

- **编码**：MUST 使用 UTF-8；SHOULD 带 BOM 以兼容 Excel（见 SPECIFICATION）。
- **目录**：MUST 放置于本仓库 `data/` 目录。
- **对象实例**：
  - 每个 CSV 对应单一逻辑表；SHOULD 一对象类型一文件
  - 列名 MUST 与对应 `ObjectType` 的 Data Properties `Name` 列完全一致
- **关系实例**：
  - 文件名 SHOULD 为 `data/relations_<relation_type_id>.csv`
  - 列 SHOULD 包含参与关联的两端主键属性名（与 `Mapping Rules` 一致），及可选的 `relation_type_id`、生效时间等扩展字段，便于导入边表或关联表

---

## 5. 一致性与校验

- **MUST** 保证属性、键、CSV 列、关系映射字段四方对齐；提交前自检引用完整性（关系端点 id、外键列）。
- **SHOULD** 若环境已安装 bkn-specification 的 CLI，对 BKN 目录执行校验，例如：
  ```bash
  cd /Users/cx/Work/kweaver-ai/bkn-specification/cli && go run ./cmd/bkn validate network <本仓库 BKN 根目录>
  ```
  （实际命令以该仓库 `cli/README.md` 为准）

---

## 6. 代码与测试

- **MUST** 本仓库内新增或修改的**所有可执行代码**（脚本、CLI、库、导入/校验工具等）必须配套**可重复执行的测试**（单元测试、集成测试或等价自动化校验），并在提交或合并前**实际运行且通过**。
- **MUST NOT** 仅交付代码而不提供测试或不经测试即视为完成。
- **SHOULD** 测试覆盖关键路径与边界情况；若仅含声明式资产（BKN/CSV）而无代码，则以第 5 节的 BKN 校验与数据自检作为该变更的“测试”门槛。

---

## 7. 参考仓库路径

- 规范与示例路径：`/Users/cx/Work/kweaver-ai/bkn-specification`
- 不得臆造 BKN 语法；遇不确定处查阅 SPECIFICATION.md 或 bkn-creator 参考文档（`.cursor/skills/bkn-creator/references/specification.md`）。
