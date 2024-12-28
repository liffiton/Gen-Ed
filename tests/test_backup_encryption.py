# SPDX-FileCopyrightText: 2024 Mark Liffiton <liffiton@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-only

import platform
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory


def test_db_download_status(app, monkeypatch):
    """Test that db_download_status correctly reflects encryption availability"""
    with app.app_context():
        from gened.admin.download import get_encryption_status

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


def test_backup_db_encryption(app):
    """Test that backup_db handles encryption configuration correctly"""
    # test does not run on Windows, where gened does not support db backups
    if platform.system() == "Windows":
        return

    with app.app_context():
        from gened.db import backup_db

        # Test unencrypted backup (no key configured)
        app.config['AGE_PUBLIC_KEY'] = None
        with NamedTemporaryFile() as backup_file:
            backup_db(Path(backup_file.name))
            header = backup_file.read(16)
            assert header.startswith(b'SQLite format 3')  # unencrypted SQLite file

        # Test encrypted backup with a real SSH key
        with TemporaryDirectory() as temp_dir:
            # Generate SSH keypair
            key_path = Path(temp_dir) / "temp_key"
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path)],
                check=True, capture_output=True
            )
            pubkey = (key_path.with_suffix(".pub")).read_text().strip()

            # Configure and test encryption
            app.config['AGE_PUBLIC_KEY'] = pubkey

            backup_path = Path(temp_dir) / "backup.db"
            backup_db(backup_path)
            with backup_path.open('rb') as f:
                header = f.read(6)
                assert header == b'age-en'  # age encryption header
