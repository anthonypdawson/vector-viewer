"""Service for managing application dialogs."""

from PySide6.QtWidgets import QMessageBox, QDialog, QWidget
from vector_inspector.core.connection_manager import ConnectionManager


class DialogService:
    """Service for launching application dialogs."""

    @staticmethod
    def show_about(parent: QWidget = None):
        """Show about dialog."""
        from vector_inspector.utils.version import get_app_version

        version = get_app_version()
        version_html = (
            f"<h2>Vector Inspector {version}</h2>" if version else "<h2>Vector Inspector</h2>"
        )
        about_text = (
            version_html + "<p>A comprehensive desktop application for visualizing, "
            "querying, and managing multiple vector databases simultaneously.</p>"
            '<p><a href="https://github.com/anthonypdawson/vector-inspector" style="color:#2980b9;">GitHub Project Page</a></p>'
            "<hr />"
            "<p>Built with PySide6</p>"
            "<p><b>New:</b> Pinecone support!</p>"
        )
        QMessageBox.about(parent, "About Vector Inspector", about_text)

    @staticmethod
    def show_backup_restore_dialog(
        connection, collection_name: str = "", parent: QWidget = None
    ) -> int:
        """Show backup/restore dialog.

        Args:
            connection: Active connection instance
            collection_name: Optional collection name
            parent: Parent widget

        Returns:
            QDialog.Accepted or QDialog.Rejected
        """
        if not connection:
            QMessageBox.information(parent, "No Connection", "Please connect to a database first.")
            return QDialog.Rejected

        # Show info if no collection selected
        if not collection_name:
            QMessageBox.information(
                parent,
                "No Collection Selected",
                "You can restore backups without a collection selected.\n"
                "To create a backup, please select a collection first.",
            )

        from vector_inspector.ui.components.backup_restore_dialog import BackupRestoreDialog

        # Pass through the connection object (ConnectionInstance expected by UI)
        dialog = BackupRestoreDialog(connection, collection_name or "", parent)
        return dialog.exec()

    @staticmethod
    def show_migration_dialog(connection_manager: ConnectionManager, parent: QWidget = None) -> int:
        """Show cross-database migration dialog.

        Args:
            connection_manager: Connection manager instance
            parent: Parent widget

        Returns:
            QDialog.Accepted or QDialog.Rejected
        """
        if connection_manager.get_connection_count() < 2:
            QMessageBox.information(
                parent,
                "Insufficient Connections",
                "You need at least 2 active connections to migrate data.\n"
                "Please connect to additional databases first.",
            )
            return QDialog.Rejected

        from vector_inspector.ui.dialogs.cross_db_migration import CrossDatabaseMigrationDialog

        dialog = CrossDatabaseMigrationDialog(connection_manager, parent)
        return dialog.exec()

    @staticmethod
    def show_profile_editor_prompt(parent: QWidget = None):
        """Show message prompting user to create a new profile."""
        QMessageBox.information(
            parent,
            "Connect to Profile",
            "Select a profile from the list and click 'Connect', or click '+' to create a new profile.",
        )

    @staticmethod
    def show_update_details(latest_release: dict, parent: QWidget = None):
        """Show update details dialog.

        Args:
            latest_release: Latest release info from GitHub API
            parent: Parent widget
        """
        from vector_inspector.ui.components.update_details_dialog import UpdateDetailsDialog
        from vector_inspector.services.update_service import UpdateService

        version = latest_release.get("tag_name", "?")
        notes = latest_release.get("body", "")
        instructions = UpdateService.get_update_instructions()
        pip_cmd = instructions["pip"]
        github_url = instructions["github"]

        dialog = UpdateDetailsDialog(version, notes, pip_cmd, github_url, parent)
        dialog.exec()
