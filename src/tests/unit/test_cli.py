"""Unit tests for CLI orchestration."""

import unittest
from unittest import mock

import pytest

from restic_compose_backup import cli, enums

pytestmark = pytest.mark.unit


class BackupProcessLabelTests(unittest.TestCase):
    """Tests for labels propagated to the transient backup process."""

    def run_backup(self, backup_options_label):
        containers = mock.Mock()
        containers.backup_process_running = False
        containers.backup_process_label = "stack-back.process-test"
        containers.project_name = "test"
        containers.generate_backup_mounts.return_value = {}
        containers.this_container.volumes = {}
        containers.this_container.image = "stack-back:test"
        containers.this_container.environment = []
        containers.this_container.id = "container-id"
        containers.this_container.get_label.return_value = backup_options_label

        with mock.patch(
            "restic_compose_backup.cli.backup_runner.run", return_value=0
        ) as run:
            cli.backup(mock.Mock(), containers)

        return run.call_args.kwargs["labels"]

    def test_propagates_global_backup_options_without_reparsing(self):
        value = '--tag global --host "backup server"'

        labels = self.run_backup(value)

        self.assertEqual(labels[enums.LABEL_RESTIC_BACKUP_OPTIONS], value)

    def test_does_not_propagate_missing_or_blank_options(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                labels = self.run_backup(value)
                self.assertNotIn(enums.LABEL_RESTIC_BACKUP_OPTIONS, labels)
