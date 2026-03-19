# Progress

## Iteration 1

- 初始化 Ralph：`RALPH_TASK.md`、`.ralph/state.md`、`guardrails.md`
- 新增 `network.bkn`，4 个 `object_type`，3 个 `relation_type`，`concept_groups/dr_core.bkn`
- 新增 `data/` 下 4 个对象 CSV + 3 个关系 CSV（UTF-8 BOM）
- 新增 `scripts/validate_network.py`、`tests/test_bkn_load.py`、`tests/test_csv_headers.py`、`requirements-dev.txt`、`README.md`、`.gitignore`
- **验证**：`pytest` 9 passed；`bkn.load_network(repo)` 成功

## 单文件合并

- 全部 BKN 定义合并至根目录 `network.bkn`；已删除 `object_types/`、`relation_types/`、`concept_groups/` 下独立 `.bkn`。

## 下一迭代可选

- 扩展属性（存储库、副本、备份客户端等）与更多关系
- 对接真实导入管道（DB schema 与 CSV 的 ETL）
