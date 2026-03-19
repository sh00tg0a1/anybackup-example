"""BKN 网络可被 Python SDK 加载（需安装 kweaver bkn SDK）。"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("bkn")

from bkn import load_network

REPO_ROOT = Path(__file__).resolve().parents[1]
BKN_ROOT = REPO_ROOT / "bkn"


def test_load_dr_backup_network() -> None:
    network = load_network(BKN_ROOT)
    assert network.root.frontmatter.id == "dr_backup_network"
    ids = {o.id for o in network.all_objects}
    assert ids == {
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
    rids = {r.id for r in network.all_relations}
    assert rids == {
        "rs_software_protects_app",
        "rs_app_supports_backup_method",
        "rs_backup_method_applies_scope",
        "rs_app_recoverable_at_scope",
        "rs_recovery_scope_uses_method",
        "rs_software_provides_option",
        "rs_software_depends_component",
        "rs_app_uses_database",
    }
