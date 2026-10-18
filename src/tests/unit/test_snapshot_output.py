"""Regression tests for parsing restic's snapshot table."""

import pytest

from tests.integration.test_volume_backups import parse_snapshots


@pytest.mark.unit
def test_snapshot_parser_ignores_timezone_footer():
    output = """ID        Time                 Host          Tags                   Paths                                 Size
-------------------------------------------------------------------------------------------------------------------
25ffd9e5  2026-10-18 22:27:24  backup-host   test-tag               /volumes                              1.400 KiB
9fa1b22a  2026-10-18 22:27:24  backup-host   test-tag               /databases/postgres/testdb.sql        1.123 KiB
b98cc134  2026-10-18 22:27:25  backup-host   test-tag               /databases/mariadb/all_databases.sql  3.056 MiB
ae7f8163  2026-10-18 22:27:26  backup-host   test-tag,mysql-target  /databases/mysql/all_databases.sql    3.579 MiB
-------------------------------------------------------------------------------------------------------------------
Timestamps shown in UTC
4 snapshots
"""

    snapshots = parse_snapshots(output)

    assert len(snapshots) == 4
    assert {snapshot.id for snapshot in snapshots} == {
        "25ffd9e5",
        "9fa1b22a",
        "b98cc134",
        "ae7f8163",
    }
