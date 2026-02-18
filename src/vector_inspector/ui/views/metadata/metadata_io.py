"""Import/export logic for metadata view."""

from typing import Any, Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from vector_inspector.services.import_export_service import ImportExportService
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.views.metadata.context import MetadataContext


def export_data(
    parent: QWidget,
    ctx: MetadataContext,
    format_type: str,
    table: Any = None,  # Optional QTableWidget
) -> bool:
    """Export current table data to file (visible rows or selected rows).

    Args:
        parent: Parent widget for dialogs
        ctx: MetadataContext containing data and collection info
        format_type: Export format ('json', 'csv', 'parquet')
        table: Optional QTableWidget to check for selected rows

    Returns:
        True if export succeeded, False otherwise
    """
    if not ctx.current_collection:
        QMessageBox.warning(parent, "No Collection", "Please select a collection first.")
        return False

    if not ctx.current_data or not ctx.current_data.get("ids"):
        QMessageBox.warning(parent, "No Data", "No data to export.")
        return False

    current_data = ctx.current_data
    current_collection = ctx.current_collection

    # Check if there are selected rows
    selected_rows = table.selectionModel().selectedRows() if table else []

    if selected_rows:
        # Export only selected rows
        export_data_subset: dict[str, list[Any]] = {
            "ids": [],
            "documents": [],
            "metadatas": [],
            "embeddings": [],
        }

        for index in selected_rows:
            row = index.row()
            if row < len(current_data["ids"]):
                export_data_subset["ids"].append(current_data["ids"][row])
                if "documents" in current_data and row < len(current_data["documents"]):
                    export_data_subset["documents"].append(current_data["documents"][row])
                if "metadatas" in current_data and row < len(current_data["metadatas"]):
                    export_data_subset["metadatas"].append(current_data["metadatas"][row])
                if "embeddings" in current_data and row < len(current_data["embeddings"]):
                    export_data_subset["embeddings"].append(current_data["embeddings"][row])
        final_export_data: dict[str, Any] = export_data_subset
    else:
        # Export all visible data from current table
        final_export_data = current_data

    # Select file path
    file_filters: dict[str, str] = {
        "json": "JSON Files (*.json)",
        "csv": "CSV Files (*.csv)",
        "parquet": "Parquet Files (*.parquet)",
    }

    # Get last used directory from settings
    settings_service = SettingsService()
    last_dir = settings_service.get("last_import_export_dir", "")
    default_path = (
        f"{last_dir}/{current_collection}.{format_type}"
        if last_dir
        else f"{current_collection}.{format_type}"
    )

    file_path, _ = QFileDialog.getSaveFileName(
        parent, f"Export to {format_type.upper()}", default_path, file_filters[format_type]
    )

    if not file_path:
        return False

    # Export
    service = ImportExportService()
    success: bool = False

    if format_type == "json":
        success = service.export_to_json(final_export_data, file_path)
    elif format_type == "csv":
        success = service.export_to_csv(final_export_data, file_path)
    elif format_type == "parquet":
        success = service.export_to_parquet(final_export_data, file_path)

    if success:
        # Save the directory for next time
        from pathlib import Path

        settings_service.set("last_import_export_dir", str(Path(file_path).parent))

        QMessageBox.information(
            parent,
            "Export Successful",
            f"Exported {len(final_export_data['ids'])} items to {file_path}",
        )
        return True
    QMessageBox.warning(parent, "Export Failed", "Failed to export data.")
    return False


def import_data(
    parent: QWidget,
    ctx: MetadataContext,
    format_type: str,
    loading_dialog: Any,  # LoadingDialog
) -> Optional[dict[str, Any]]:
    """Import data from file into collection.

    Args:
        parent: Parent widget for dialogs
        ctx: MetadataContext containing connection and collection info
        format_type: Import format ('json', 'csv', 'parquet')
        loading_dialog: Loading dialog to show progress

    Returns:
        Imported data dictionary if successful, None otherwise
    """
    from PySide6.QtWidgets import QApplication

    connection = ctx.connection
    current_collection = ctx.current_collection

    if not current_collection:
        QMessageBox.warning(parent, "No Collection", "Please select a collection first.")
        return None

    # Select file to import
    file_filters: dict[str, str] = {
        "json": "JSON Files (*.json)",
        "csv": "CSV Files (*.csv)",
        "parquet": "Parquet Files (*.parquet)",
    }

    # Get last used directory from settings
    settings_service = SettingsService()
    last_dir = settings_service.get("last_import_export_dir", "")

    file_path, _ = QFileDialog.getOpenFileName(
        parent, f"Import from {format_type.upper()}", last_dir, file_filters[format_type]
    )

    if not file_path:
        return None

    # Import
    loading_dialog.show_loading("Importing data...")
    QApplication.processEvents()

    try:
        service = ImportExportService()
        imported_data: Optional[dict[str, Any]] = None

        if format_type == "json":
            imported_data = service.import_from_json(file_path)
        elif format_type == "csv":
            imported_data = service.import_from_csv(file_path)
        elif format_type == "parquet":
            imported_data = service.import_from_parquet(file_path)

        if not imported_data:
            QMessageBox.warning(parent, "Import Failed", "Failed to parse import file.")
            return None

        # Add items to collection
        # Connection-specific preprocessing (e.g., embedding generation, ID conversion)
        # is handled by the connection's add_items method
        success = connection.add_items(
            current_collection,
            documents=imported_data["documents"],
            metadatas=imported_data.get("metadatas"),
            ids=imported_data.get("ids"),
            embeddings=imported_data.get("embeddings"),
        )
    finally:
        loading_dialog.hide_loading()

    if success:
        # Save the directory for next time
        from pathlib import Path

        settings_service.set("last_import_export_dir", str(Path(file_path).parent))

        QMessageBox.information(
            parent, "Import Successful", f"Imported {len(imported_data['ids'])} items."
        )
        return imported_data
    QMessageBox.warning(parent, "Import Failed", "Failed to import data.")
    return None
