# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import platform
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest
from flask import Flask

from gened.admin.download import get_encryption_status
from gened.db_admin import backup_db

# Throwaway ed25519 key generated for testing; only the public key is needed.
TEST_SSH_PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHsHhD55MQMlYxt/Tj/RMrtMI64SNqMGkjr4ICJDdjXP gened-test-key"


def test_db_download_status(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that db_download_status correctly reflects encryption availability"""
    with app.app_context():

        # No key configured
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        app.config['AGE_PUBLIC_KEY'] = None
        status = get_encryption_status()
        assert not status.encrypted
        assert status.reason is not None
        assert "No encryption key configured" in status.reason

        # Mock Windows platform
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        app.config['AGE_PUBLIC_KEY'] = "ssh-ed25519 AAAAC3..."
        status = get_encryption_status()
        assert not status.encrypted
        assert status.reason is not None
        assert "Windows" in status.reason

        # Mock non-Windows platform
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        status = get_encryption_status()
        assert status.encrypted
        assert status.reason is None


def test_backup_db_encryption(app: Flask) -> None:
    """Test that backup_db handles encryption configuration correctly"""
    # test does not run on Windows, where gened does not support db backups
    if platform.system() == "Windows":
        return

    with app.app_context():
        # Test unencrypted backup (no key configured)
        app.config['AGE_PUBLIC_KEY'] = None
        with NamedTemporaryFile() as backup_file:
            backup_db(Path(backup_file.name))
            header = backup_file.read(16)
            assert header.startswith(b'SQLite format 3')  # unencrypted SQLite file

        # Test encrypted backup with a real SSH key
        with TemporaryDirectory() as temp_dir:
            app.config['AGE_PUBLIC_KEY'] = TEST_SSH_PUBLIC_KEY

            backup_path = Path(temp_dir) / "backup.db"
            backup_db(backup_path)
            with backup_path.open('rb') as f:
                header = f.read(6)
                assert header == b'age-en'  # age encryption header
