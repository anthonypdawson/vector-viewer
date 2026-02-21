"""Reusable pagination controls widget."""

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QWidget


class PaginationControls(QWidget):
    """
    Reusable pagination controls for table views.

    Signals:
        page_changed: Emitted when page changes (new_page, old_page)
        page_size_changed: Emitted when page size changes (new_size)
        previous_clicked: Emitted when previous button clicked
        next_clicked: Emitted when next button clicked
    """

    page_changed = Signal(int, int)  # new_page, old_page
    page_size_changed = Signal(int)  # new_size
    previous_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._current_page = 0
        self._total_pages = 0
        self._page_size = 50
        self._has_next = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI controls."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Previous button
        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.clicked.connect(self._on_previous)
        self.prev_button.setEnabled(False)
        layout.addWidget(self.prev_button)

        # Page label
        self.page_label = QLabel("0 / 0")
        layout.addWidget(self.page_label)

        # Next button
        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(self._on_next)
        self.next_button.setEnabled(False)
        layout.addWidget(self.next_button)

        layout.addWidget(QLabel("  Items per page:"))

        # Page size spinner
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setMinimum(10)
        self.page_size_spin.setMaximum(500)
        self.page_size_spin.setValue(self._page_size)
        self.page_size_spin.setSingleStep(10)
        self.page_size_spin.valueChanged.connect(self._on_page_size_changed)
        layout.addWidget(self.page_size_spin)

        layout.addStretch()

    def _on_previous(self):
        """Handle previous button click."""
        if self._current_page > 0:
            old_page = self._current_page
            self._current_page -= 1
            self.page_changed.emit(self._current_page, old_page)
            self.previous_clicked.emit()
            self._update_ui()

    def _on_next(self):
        """Handle next button click."""
        old_page = self._current_page
        self._current_page += 1
        self.page_changed.emit(self._current_page, old_page)
        self.next_clicked.emit()
        self._update_ui()

    def _on_page_size_changed(self, new_size: int):
        """Handle page size change."""
        old_size = self._page_size
        if new_size != old_size:
            self._page_size = new_size
            self._current_page = 0  # Reset to first page
            self.page_size_changed.emit(new_size)
            self._update_ui()

    def _update_ui(self):
        """Update UI state based on current page."""
        # Update label
        if self._total_pages > 0:
            self.page_label.setText(f"{self._current_page + 1} / {self._total_pages}")
        else:
            self.page_label.setText(f"{self._current_page + 1} / ?")

        # Update button states
        self.prev_button.setEnabled(self._current_page > 0)
        self.next_button.setEnabled(self._has_next)

    def set_state(self, current_page: int, total_pages: int = 0, has_next: bool = False):
        """
        Set pagination state.

        Args:
            current_page: Current page number (0-indexed)
            total_pages: Total number of pages (0 if unknown)
            has_next: Whether there's a next page
        """
        self._current_page = current_page
        self._total_pages = total_pages
        self._has_next = has_next
        self._update_ui()

    def reset(self):
        """Reset to first page."""
        self._current_page = 0
        self._total_pages = 0
        self._has_next = False
        self._update_ui()

    @property
    def current_page(self) -> int:
        """Get current page number (0-indexed)."""
        return self._current_page

    @property
    def page_size(self) -> int:
        """Get current page size."""
        return self._page_size

    def set_page_size(self, size: int):
        """Set page size programmatically."""
        self.page_size_spin.setValue(size)
