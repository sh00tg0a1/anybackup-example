# 灾备业务知识网络（BKN）

本仓库包含灾备/备份领域的 **BKN** 模型（`network.bkn`、`object_types/`、`relation_types/`、`concept_groups/`）及 **`data/`** 下与对象类对齐的 CSV 样例，便于导入数据库。

## 规范与协作约定

见根目录 [AGENTS.md](./AGENTS.md)。

## 结构速览

| 路径 | 说明 |
|------|------|
| `bkn/network.bkn` | 网络根；对象、关系、概念分组分别位于 `object_types/`、`relation_types/`、`concept_groups/` |
| `data/*.csv` | 实例数据（UTF-8 BOM），**严格来源于**《AnyBackup Family 8 AnyShare 备份恢复用户指南》；对象类一文件，关系为 `relations_<id>.csv` |

目录结构：`bkn/network.bkn`、`bkn/object_types/*.bkn`（10 个）、`bkn/relation_types/*.bkn`（8 个）、`bkn/concept_groups/dr_core.bkn`。

## 校验

**Python SDK**（推荐，与测试一致）：

```bash
pip install -e /Users/cx/Work/kweaver-ai/bkn-specification/sdk/python
pip install -r requirements-dev.txt
python scripts/validate_network.py
pytest
```

**Go CLI**（若本机可构建 `bkn-specification/cli`）：

```bash
cd /path/to/bkn-specification/cli && go run ./cmd/bkn validate network /path/to/anybackup
```

## Ralph 迭代

任务定义见 [RALPH_TASK.md](./RALPH_TASK.md)；状态与护栏见 [.ralph/](./.ralph/)。
