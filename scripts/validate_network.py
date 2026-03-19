#!/usr/bin/env python3
"""
使用 kweaver BKN Python SDK 加载本仓库知识网络（结构校验）。
安装: pip install -e /path/to/bkn-specification/sdk/python
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BKN_ROOT = REPO_ROOT / "bkn"


def main() -> int:
    try:
        from bkn import load_network
    except ImportError:
        print(
            "bkn 未安装。请执行: pip install -e /Users/cx/Work/kweaver-ai/bkn-specification/sdk/python",
            file=sys.stderr,
        )
        return 2

    try:
        network = load_network(BKN_ROOT)
    except Exception as e:
        print(f"加载失败: {e}", file=sys.stderr)
        return 1

    fm = network.root.frontmatter
    print(
        f"OK type={fm.type} id={fm.id} name={fm.name} "
        f"objects={len(network.all_objects)} relations={len(network.all_relations)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
