---
task: 灾备业务知识网络（BKN + CSV）
completion_criteria:
  - network.bkn 单文件内含 4 对象类型、3 关系类型、概念分组，符合 bkn-specification
  - data/ 下对象类 CSV 列名与各 ObjectType Data Properties 的 Name 一致
  - data/ 下关系实例 CSV 命名与列符合 AGENTS.md
  - bkn validate network 通过（若本机有 Go + bkn cli）
  - Python 测试通过：CSV 列与 BKN 定义一致、bkn 校验脚本可执行
max_iterations: 30
---

## Requirements

1. 参考 `/Users/cx/Work/kweaver-ai/bkn-specification/docs` 设计灾备 BKN。
2. 业务对象：备份软件、保护对象、保护策略、恢复策略；不含 action_type。
3. 实例数据：按对象类分 CSV，便于导入数据库；关系实例单独 CSV。

## Constraints

- 遵循仓库根目录 `AGENTS.md`。
- ID 小写蛇形；显示名中文。
