"""Unit tests for database backup configuration"""

import unittest
from unittest import mock
import pytest

from restic_compose_backup.containers import Container, RunningContainers
from restic_compose_backup.containers_db import (
    MariadbContainer,
    MysqlContainer,
    PostgresContainer,
)
from . import fixtures
from .conftest import BaseTestCase

pytestmark = pytest.mark.unit

list_containers_func = "restic_compose_backup.utils.list_containers"


def make_db_container_data(service, labels, env_vars):
    """Build the minimal metadata required for a database container."""
    return {
        "Id": fixtures.generate_sha256(),
        "Name": service,
        "Config": {
            "Image": "image:latest",
            "Labels": {
                "com.docker.compose.oneoff": "False",
                "com.docker.compose.project": "test",
                "com.docker.compose.service": service,
                **labels,
            },
            "Env": [f"{key}={value}" for key, value in env_vars.items()],
        },
        "Mounts": [],
        "State": {"Status": "running", "Running": True},
    }


class DatabaseConfigurationTests(BaseTestCase):
    """Tests for database backup configuration"""

    def test_databases_for_backup(self):
        """Test identifying databases marked for backup"""
        containers = self.createContainers()
        containers += [
            {
                "service": "mysql",
                "labels": {
                    "stack-back.mysql": True,
                },
                "mounts": [
                    {
                        "Source": "/srv/mysql/data",
                        "Destination": "/var/lib/mysql",
                        "Type": "bind",
                    }
                ],
            },
            {
                "service": "mariadb",
                "labels": {
                    "stack-back.mariadb": True,
                },
                "mounts": [
                    {
                        "Source": "/srv/mariadb/data",
                        "Destination": "/var/lib/mysql",
                        "Type": "bind",
                    },
                ],
            },
            {
                "service": "postgres",
                "labels": {
                    "stack-back.postgres": True,
                },
                "mounts": [
                    {
                        "Source": "/srv/postgres/data",
                        "Destination": "/var/lib/postgresql/data",
                        "Type": "bind",
                    },
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        mysql_service = cnt.get_service("mysql")
        self.assertNotEqual(mysql_service, None, msg="MySQL service not found")
        self.assertTrue(mysql_service.mysql_backup_enabled)
        mariadb_service = cnt.get_service("mariadb")
        self.assertNotEqual(mariadb_service, None, msg="MariaDB service not found")
        self.assertTrue(mariadb_service.mariadb_backup_enabled)
        postgres_service = cnt.get_service("postgres")
        self.assertNotEqual(postgres_service, None, msg="Posgres service not found")
        self.assertTrue(postgres_service.postgresql_backup_enabled)

    def test_stop_container_during_backup_database(self):
        """Test that stop-during-backup label doesn't apply to databases"""
        containers = self.createContainers()
        containers += [
            {
                "service": "mysql",
                "labels": {
                    "stack-back.mysql": True,
                    "stack-back.volumes.stop-during-backup": True,
                },
                "mounts": [
                    {
                        "Source": "/srv/mysql/data",
                        "Destination": "/var/lib/mysql",
                        "Type": "bind",
                    }
                ],
            },
        ]
        with mock.patch(
            list_containers_func, fixtures.containers(containers=containers)
        ):
            cnt = RunningContainers()
        mysql_service = cnt.get_service("mysql")
        self.assertNotEqual(mysql_service, None, msg="MySQL service not found")
        self.assertTrue(mysql_service.mysql_backup_enabled)
        self.assertFalse(mysql_service.stop_during_backup)


class ResticBackupOptionsTests(unittest.TestCase):
    """Tests for container-scoped restic backup options."""

    def test_parses_quoted_options(self):
        data = make_db_container_data(
            "postgres",
            {"stack-back.restic.backup.options": '--tag local --host "db server"'},
            {},
        )

        self.assertEqual(
            Container(data).restic_backup_options,
            ["--tag", "local", "--host", "db server"],
        )

    def test_missing_or_blank_options_are_empty(self):
        for value in (None, "", "   "):
            labels = (
                {} if value is None else {"stack-back.restic.backup.options": value}
            )
            data = make_db_container_data("postgres", labels, {})

            with self.subTest(value=value):
                self.assertEqual(Container(data).restic_backup_options, [])

    def test_malformed_quoting_is_reported(self):
        data = make_db_container_data(
            "postgres",
            {"stack-back.restic.backup.options": '--tag "unfinished'},
            {},
        )

        with self.assertRaisesRegex(ValueError, "No closing quotation"):
            Container(data).restic_backup_options

    def test_database_backups_append_target_options(self):
        cases = [
            (
                MariadbContainer,
                "mariadb",
                {"MARIADB_ROOT_PASSWORD": "secret"},
            ),
            (MysqlContainer, "mysql", {"MYSQL_ROOT_PASSWORD": "secret"}),
            (
                PostgresContainer,
                "postgres",
                {
                    "POSTGRES_USER": "user",
                    "POSTGRES_PASSWORD": "secret",
                    "POSTGRES_DB": "database",
                },
            ),
        ]
        global_options = ["--tag", "global"]

        for container_class, service, env_vars in cases:
            data = make_db_container_data(
                service,
                {
                    f"stack-back.{service}": "true",
                    "stack-back.restic.backup.options": (
                        '--tag local --host "db server"'
                    ),
                },
                env_vars,
            )
            container = container_class(data)

            with (
                self.subTest(service=service),
                mock.patch(
                    "restic_compose_backup.containers_db.restic.backup_from_stdin",
                    return_value=0,
                ) as backup_from_stdin,
            ):
                container.backup(global_options)

                self.assertEqual(
                    backup_from_stdin.call_args.kwargs["restic_backup_options"],
                    [
                        "--tag",
                        "global",
                        "--tag",
                        "local",
                        "--host",
                        "db server",
                    ],
                )

        self.assertEqual(global_options, ["--tag", "global"])
