import os
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER_PATH = os.path.join(PROJECT_ROOT, "wp-install-helper.sh")


class WordPressCoreUpdateHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(HELPER_PATH) as f:
            cls.source = f.read()

    def test_helper_has_restricted_core_update_mode(self):
        self.assertIn('"--core-update"', self.source)
        self.assertIn('ARCHIVE_PATH="$PHP_VER"', self.source)
        self.assertIn('"$INSTALL_PATH/wp-config.php"', self.source)
        self.assertIn('"$INSTALL_PATH/wp-content"', self.source)

    def test_helper_uses_maintenance_mode_and_always_removes_it(self):
        self.assertIn('MAINTENANCE_FILE="$INSTALL_PATH/.maintenance"', self.source)
        # Trap now calls a cleanup function that removes the maintenance file
        # and conditionally restores the backup on failure.
        self.assertIn("cleanup()", self.source)
        self.assertIn("trap cleanup EXIT", self.source)

    def test_helper_extracts_only_the_official_archive_and_updates_core_paths(self):
        self.assertIn('EXPECTED_ARCHIVE="$SCRIPT_DIR/cache/wordpress/latest.tar.gz"', self.source)
        self.assertIn('tar -xzf "$ARCHIVE_PATH"', self.source)
        # Old core dirs are moved to a backup location (not rm -rf'd) so they
        # can be restored if the new copy fails.
        self.assertIn('BACKUP_DIR=', self.source)
        self.assertIn('mv "$INSTALL_PATH/wp-admin" "$BACKUP_DIR/wp-admin"', self.source)
        self.assertIn('mv "$INSTALL_PATH/wp-includes" "$BACKUP_DIR/wp-includes"', self.source)
        self.assertIn('cp -a "$STAGE_DIR/wordpress/wp-admin"', self.source)

    def test_helper_restores_backup_on_copy_failure(self):
        # Rollback contract: on copy failure the cleanup function restores the
        # previous wp-admin/wp-includes from the backup directory.
        core_block = self.source.split('if [ "$INSTALL_PATH" = "--core-update" ]; then')[1].split('\nfi\n')[0]
        self.assertIn('RESTORE_NEEDED=1', core_block)
        self.assertIn('RESTORE_NEEDED=0', core_block)
        self.assertIn('mv "$BACKUP_DIR/wp-admin" "$BACKUP_DIR/wp-includes" "$INSTALL_PATH/"', core_block)
        # Backup is only removed after success.
        self.assertIn('rm -rf "$BACKUP_DIR"', core_block)

    def test_helper_maintenance_file_removed_on_success_and_failure(self):
        # Maintenance file must be removed in both success and failure paths.
        core_block = self.source.split('if [ "$INSTALL_PATH" = "--core-update" ]; then')[1].split('\nfi\n')[0]
        # cleanup() always removes the maintenance file.
        self.assertIn('rm -f "$MAINTENANCE_FILE"', core_block)
        # Success path also removes it explicitly before exit.
        self.assertGreaterEqual(core_block.count('rm -f "$MAINTENANCE_FILE"'), 2)


if __name__ == "__main__":
    unittest.main()
