"""Background threads for metadata view operations."""

from typing import Optional

from PySide6.QtCore import QThread, Signal

from vector_inspector.ui.views.metadata.context import MetadataContext


class DataLoadThread(QThread):
    """Background thread for loading collection data."""

    finished = Signal(dict)
    error = Signal(str)

    ctx: MetadataContext
    req_limit: Optional[int]
    req_offset: Optional[int]

    def __init__(
        self,
        ctx: MetadataContext,
        req_limit: Optional[int],
        req_offset: Optional[int],
    ) -> None:
        super().__init__()
        self.ctx = ctx
        self.req_limit = req_limit
        self.req_offset = req_offset

    def run(self) -> None:
        """Load data from database."""
        try:
            if not self.ctx.connection:
                self.error.emit("No database connection available")
                return

            data = self.ctx.connection.get_all_items(
                self.ctx.current_collection,
                limit=self.req_limit,
                offset=self.req_offset,
                where=self.ctx.server_filter,
            )
            if data:
                self.finished.emit(data)
            else:
                self.error.emit("Failed to load data")
        except Exception as e:
            self.error.emit(str(e))
