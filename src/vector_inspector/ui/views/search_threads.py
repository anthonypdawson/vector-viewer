"""Background threads for search view operations."""

from typing import Any, Optional

from PySide6.QtCore import QThread, Signal


class SearchThread(QThread):
    """Background thread for performing similarity searches."""

    finished = Signal(dict)  # Emits search results
    error = Signal(str)

    def __init__(
        self,
        connection: Any,
        collection: str,
        query_text: str,
        n_results: int,
        server_filter: Optional[dict] = None,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.connection = connection
        self.collection = collection
        self.query_text = query_text
        self.n_results = n_results
        self.server_filter = server_filter

    def run(self) -> None:
        """Perform search query."""
        try:
            if not self.connection:
                self.error.emit("No database connection available")
                return

            # Always pass query_texts; provider handles embedding if needed
            results = self.connection.query_collection(
                self.collection,
                query_texts=[self.query_text],
                n_results=self.n_results,
                where=self.server_filter,
            )

            if results:
                self.finished.emit(results)
            else:
                self.error.emit("Search failed")
        except Exception as e:
            self.error.emit(str(e))
