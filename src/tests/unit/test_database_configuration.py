"""Unit tests for database backup configuration"""

import unittest
from unittest import mock
import pytest

from restic_compose_backup.containers import RunningContainers
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
    """Build the minimal container data dict required to construct a db container."""
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
            "Env": [f"{k}={v}" for k, v in env_vars.items()],
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


class DatabaseBackupTagTests(unittest.TestCase):
    """Tests that backup() passes the vendor tag to restic"""

    def _run_backup(self, container):
        with mock.patch(
            "restic_compose_backup.containers_db.restic.backup_from_stdin",
            return_value=0,
        ) as mock_backup, mock.patch(
            "restic_compose_backup.containers_db.Config"
        ) as mock_config:
            mock_config.return_value.repository = "test-repo"
            container.backup()
        return mock_backup

    def test_mariadb_backup_tag(self):
        data = make_db_container_data(
            "mariadb",
            {"stack-back.mariadb": "true"},
            {"MARIADB_ROOT_PASSWORD": "secret"},
        )
        mock_backup = self._run_backup(MariadbContainer(data))
        _, kwargs = mock_backup.call_args
        self.assertIn("--tag", kwargs["extra_args"])
        self.assertIn("mariadb", kwargs["extra_args"])

    def test_mysql_backup_tag(self):
        data = make_db_container_data(
            "mysql",
            {"stack-back.mysql": "true"},
            {"MYSQL_ROOT_PASSWORD": "secret"},
        )
        mock_backup = self._run_backup(MysqlContainer(data))
        _, kwargs = mock_backup.call_args
        self.assertIn("--tag", kwargs["extra_args"])
        self.assertIn("mysql", kwargs["extra_args"])

    def test_postgres_backup_tag(self):
        data = make_db_container_data(
            "postgres",
            {"stack-back.postgres": "true"},
            {
                "POSTGRES_USER": "user",
                "POSTGRES_PASSWORD": "secret",
                "POSTGRES_DB": "mydb",
            },
        )
        mock_backup = self._run_backup(PostgresContainer(data))
        _, kwargs = mock_backup.call_args
        self.assertIn("--tag", kwargs["extra_args"])
        self.assertIn("postgres", kwargs["extra_args"])
