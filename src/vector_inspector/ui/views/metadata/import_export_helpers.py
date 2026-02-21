"""Import/export helpers for metadata view."""

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

if TYPE_CHECKING:
    from vector_inspector.services.settings_service import SettingsService
    from vector_inspector.ui.components.loading_dialog import LoadingDialog
    from vector_inspector.ui.views.metadata.context import MetadataContext


def start_import(
    parent: QWidget,
    ctx: "MetadataContext",
    format_type: str,
    settings_service: "SettingsService",
    loading_dialog: "LoadingDialog",
    import_thread_attr: str,
    finished_callback: Callable,
    error_callback: Callable,
    progress_callback: Callable,
) -> None:
    """
    Start data import from file.

    Args:
        parent: Parent widget for dialogs
        ctx: Metadata context
        format_type: Import format ('json', 'csv', 'parquet')
        settings_service: Settings service instance
        loading_dialog: Loading dialog instance
        import_thread_attr: Attribute name for storing thread on parent
        finished_callback: Callback for finished signal
        error_callback: Callback for error signal
        progress_callback: Callback for progress signal
    """
    if not ctx.current_collection:
        QMessageBox.warning(parent, "No Collection", "Please select a collection first.")
        return

    # Select file to import
    file_filters: dict[str, str] = {
        "json": "JSON Files (*.json)",
        "csv": "CSV Files (*.csv)",
        "parquet": "Parquet Files (*.parquet)",
    }

    # Get last used directory from settings
    last_dir = settings_service.get("last_import_export_dir", "")

    file_path, _ = QFileDialog.getOpenFileName(
        parent, f"Import from {format_type.upper()}", last_dir, file_filters[format_type]
    )

    if not file_path:
        return

    # Cancel any existing import thread
    existing_thread = getattr(parent, import_thread_attr, None)
    if existing_thread and existing_thread.isRunning():
        existing_thread.quit()
        existing_thread.wait()

    # Show loading dialog
    loading_dialog.show_loading("Importing data...")

    # Start import thread
    from vector_inspector.ui.views.metadata.metadata_threads import DataImportThread

    import_thread = DataImportThread(
        ctx.connection,
        ctx.current_collection,
        file_path,
        format_type,
        parent=parent,
    )
    import_thread.finished.connect(partial(finished_callback, file_path=file_path))
    import_thread.error.connect(error_callback)
    import_thread.progress.connect(progress_callback)
    import_thread.start()

    # Store thread reference
    setattr(parent, import_thread_attr, import_thread)


def on_import_finished(
    parent: QWidget,
    ctx: "MetadataContext",
    settings_service: "SettingsService",
    loading_dialog: "LoadingDialog",
    reload_callback: Callable,
    imported_data: dict,
    item_count: int,
    file_path: str,
) -> None:
    """
    Handle import completion.

    Args:
        parent: Parent widget for dialogs
        ctx: Metadata context
        settings_service: Settings service instance
        loading_dialog: Loading dialog instance
        reload_callback: Callback to reload data
        imported_data: Imported data dict
        item_count: Number of items imported
        file_path: Path to imported file
    """
    loading_dialog.hide_loading()

    # Save the directory for next time
    settings_service.set("last_import_export_dir", str(Path(file_path).parent))

    QMessageBox.information(parent, "Import Successful", f"Imported {item_count} items.")

    # Invalidate cache after import
    if ctx.current_database and ctx.current_collection:
        ctx.cache_manager.invalidate(ctx.current_database, ctx.current_collection)

    # Reload data
    reload_callback()


def on_import_error(
    loading_dialog: "LoadingDialog",
    parent: QWidget,
    error_message: str,
) -> None:
    """
    Handle import error.

    Args:
        loading_dialog: Loading dialog instance
        parent: Parent widget for dialogs
        error_message: Error message
    """
    loading_dialog.hide_loading()
    QMessageBox.warning(parent, "Import Failed", error_message)
