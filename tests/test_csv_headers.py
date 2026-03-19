"""CSV 表头与各 object_type 的 Data Properties Name 列一致（关系 CSV 单独约定）。"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA = REPO_ROOT / "data"

OBJECT_CSV_EXPECTED = {
    "backup_software.csv": ["id", "name", "version", "description"],
    "protected_application.csv": [
        "id",
        "name",
        "supported_versions",
        "backup_software_id",
        "description",
    ],
    "backup_method.csv": [
        "id",
        "name",
        "protected_application_id",
        "description",
    ],
    "backup_scope.csv": [
        "id",
        "name",
        "target_level",
        "backup_method_id",
        "description",
    ],
    "recovery_scope.csv": [
        "id",
        "name",
        "target_level",
        "applicable_after",
        "protected_application_id",
        "description",
    ],
    "recovery_method.csv": [
        "id",
        "name",
        "recovery_scope_id",
        "description",
    ],
    "protection_option.csv": [
        "id",
        "name",
        "category",
        "configurable_params",
        "backup_software_id",
        "description",
    ],
    "infra_component.csv": [
        "id",
        "name",
        "role",
        "backup_software_id",
        "description",
    ],
    "supported_database.csv": [
        "id",
        "name",
        "db_category",
        "default_port",
        "protected_application_id",
        "description",
    ],
    "constraint.csv": ["id", "name", "category", "description"],
}

RELATION_CSV_EXPECTED = {
    "relations_rs_software_protects_app.csv": [
        "backup_software_id",
        "protected_application_id",
        "relation_type_id",
    ],
    "relations_rs_app_supports_backup_method.csv": [
        "protected_application_id",
        "backup_method_id",
        "relation_type_id",
    ],
    "relations_rs_backup_method_applies_scope.csv": [
        "backup_method_id",
        "backup_scope_id",
        "relation_type_id",
    ],
    "relations_rs_app_recoverable_at_scope.csv": [
        "protected_application_id",
        "recovery_scope_id",
        "relation_type_id",
    ],
    "relations_rs_recovery_scope_uses_method.csv": [
        "recovery_scope_id",
        "recovery_method_id",
        "relation_type_id",
    ],
    "relations_rs_software_provides_option.csv": [
        "backup_software_id",
        "protection_option_id",
        "relation_type_id",
    ],
    "relations_rs_software_depends_component.csv": [
        "backup_software_id",
        "infra_component_id",
        "relation_type_id",
    ],
    "relations_rs_app_uses_database.csv": [
        "protected_application_id",
        "supported_database_id",
        "relation_type_id",
    ],
}


def _read_header(path: Path) -> list[str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8")
    first = text.splitlines()[0] if text else ""
    return next(csv.reader([first]))


@pytest.mark.parametrize("filename,expected", list(OBJECT_CSV_EXPECTED.items()))
def test_object_csv_headers_match_bkn(filename: str, expected: list[str]) -> None:
    path = DATA / filename
    assert path.is_file(), f"missing {path}"
    assert _read_header(path) == expected


@pytest.mark.parametrize("filename,expected", list(RELATION_CSV_EXPECTED.items()))
def test_relation_csv_headers(filename: str, expected: list[str]) -> None:
    path = DATA / filename
    assert path.is_file(), f"missing {path}"
    assert _read_header(path) == expected


def test_csv_referential_sample_rows() -> None:
    """样例数据外键在表内存在（轻量一致性）。"""
    import csv as csv_mod

    def rows(name: str) -> list[dict[str, str]]:
        p = DATA / name
        raw = p.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        r = csv_mod.DictReader(raw.decode("utf-8").splitlines())
        return list(r)

    sw = {r["id"] for r in rows("backup_software.csv")}
    app = {r["id"] for r in rows("protected_application.csv")}
    bm = {r["id"] for r in rows("backup_method.csv")}
    bsc = {r["id"] for r in rows("backup_scope.csv")}
    rsc = {r["id"] for r in rows("recovery_scope.csv")}
    rm = {r["id"] for r in rows("recovery_method.csv")}
    po = {r["id"] for r in rows("protection_option.csv")}
    ic = {r["id"] for r in rows("infra_component.csv")}
    db = {r["id"] for r in rows("supported_database.csv")}

    for r in rows("protected_application.csv"):
        assert r["backup_software_id"] in sw

    for r in rows("backup_method.csv"):
        assert r["protected_application_id"] in app

    for r in rows("backup_scope.csv"):
        assert r["backup_method_id"] in bm

    for r in rows("recovery_scope.csv"):
        assert r["protected_application_id"] in app

    for r in rows("recovery_method.csv"):
        assert r["recovery_scope_id"] in rsc

    for r in rows("protection_option.csv"):
        assert r["backup_software_id"] in sw

    for r in rows("infra_component.csv"):
        assert r["backup_software_id"] in sw

    for r in rows("supported_database.csv"):
        assert r["protected_application_id"] in app

    for r in rows("relations_rs_software_protects_app.csv"):
        assert r["backup_software_id"] in sw
        assert r["protected_application_id"] in app

    for r in rows("relations_rs_app_supports_backup_method.csv"):
        assert r["protected_application_id"] in app
        assert r["backup_method_id"] in bm

    for r in rows("relations_rs_backup_method_applies_scope.csv"):
        assert r["backup_method_id"] in bm
        assert r["backup_scope_id"] in bsc

    for r in rows("relations_rs_app_recoverable_at_scope.csv"):
        assert r["protected_application_id"] in app
        assert r["recovery_scope_id"] in rsc

    for r in rows("relations_rs_recovery_scope_uses_method.csv"):
        assert r["recovery_scope_id"] in rsc
        assert r["recovery_method_id"] in rm

    for r in rows("relations_rs_software_provides_option.csv"):
        assert r["backup_software_id"] in sw
        assert r["protection_option_id"] in po

    for r in rows("relations_rs_software_depends_component.csv"):
        assert r["backup_software_id"] in sw
        assert r["infra_component_id"] in ic

    for r in rows("relations_rs_app_uses_database.csv"):
        assert r["protected_application_id"] in app
        assert r["supported_database_id"] in db
