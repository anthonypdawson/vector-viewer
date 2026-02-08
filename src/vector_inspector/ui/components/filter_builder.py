"""Advanced metadata filter builder component."""

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class FilterRule(QWidget):
    """A single filter rule widget."""

    remove_requested = Signal(object)  # Signal to remove this rule
    apply_requested = Signal()  # Signal to apply filters
    field_input: QComboBox
    operator_combo: QComboBox
    value_input: QLineEdit

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the rule UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Field name
        self.field_input = QComboBox()
        self.field_input.setEditable(True)
        self.field_input.setPlaceholderText("field name")
        self.field_input.setMinimumWidth(120)
        layout.addWidget(self.field_input)

        # Operator
        self.operator_combo = QComboBox()
        self.operator_combo.addItems(
            [
                "=",
                "!=",
                ">",
                ">=",
                "<",
                "<=",
                "in",
                "not in",
                "contains (client-side)",
                "not contains (client-side)",
            ]
        )
        self.operator_combo.setMinimumWidth(150)
        self.operator_combo.setMinimumWidth(100)
        layout.addWidget(self.operator_combo)

        # Value
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("value")
        self.value_input.setMinimumWidth(150)
        # Apply filters on Enter key or when clicking away
        self.value_input.returnPressed.connect(self.apply_requested.emit)
        self.value_input.editingFinished.connect(self.apply_requested.emit)
        layout.addWidget(self.value_input)

        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setMaximumWidth(30)
        remove_btn.setStyleSheet("QPushButton { color: red; font-weight: bold; }")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(remove_btn)

        layout.addStretch()

    def set_operators(self, operators: list[dict[str, Any]]):
        """Set available operators from connection provider."""
        self.operators = operators
        self.operator_combo.clear()
        for op in operators:
            name = op["name"]
            server_side = op.get("server_side", True)
            if not server_side:
                name = f"{name} (client-side)"
            self.operator_combo.addItem(name)

    def set_available_fields(self, fields: list[str]):
        """Set the available field names in the dropdown."""
        current_text = self.field_input.currentText()
        self.field_input.clear()
        self.field_input.addItems(fields)
        # Restore the current text if it was set
        if current_text:
            self.field_input.setEditText(current_text)

    def get_filter_dict(self) -> Optional[dict[str, Any]]:
        """Get the filter as a dictionary."""
        field = self.field_input.currentText().strip()
        operator_display = self.operator_combo.currentText()
        value_text = self.value_input.text().strip()

        if not field or not value_text:
            return None

        # Strip (client-side) suffix if present
        operator = operator_display.replace(" (client-side)", "")

        # Check if this is a client-side operator
        is_client_side = "(client-side)" in operator_display

        # Parse value (try to convert to appropriate type)
        value = self._parse_value(value_text)

        # Handle client-side operators
        if is_client_side:
            if operator == "contains":
                return {"__client_side__": True, "field": field, "op": "contains", "value": value}
            if operator == "not contains":
                return {
                    "__client_side__": True,
                    "field": field,
                    "op": "not_contains",
                    "value": value,
                }

        # For server-side text operators, use special syntax
        if operator == "contains":
            return {field: {"$contains": value}}
        if operator == "not contains":
            return {field: {"$not_contains": value}}

        # Map operator to database syntax (server-side)
        if operator == "=":
            return {field: {"$eq": value}}
        if operator == "!=":
            return {field: {"$ne": value}}
        if operator == ">":
            return {field: {"$gt": value}}
        if operator == ">=":
            return {field: {"$gte": value}}
        if operator == "<":
            return {field: {"$lt": value}}
        if operator == "<=":
            return {field: {"$lte": value}}
        if operator == "in":
            # Value should be comma-separated list
            values = [self._parse_value(v.strip()) for v in value_text.split(",")]
            return {field: {"$in": values}}
        if operator == "not in":
            values = [self._parse_value(v.strip()) for v in value_text.split(",")]
            return {field: {"$nin": values}}

        return None

    def _parse_value(self, value_text: str) -> Any:
        """Parse value text to appropriate type."""
        # Try to parse as number
        try:
            if "." in value_text:
                return float(value_text)
            return int(value_text)
        except ValueError:
            pass

        # Try to parse as boolean
        if value_text.lower() == "true":
            return True
        if value_text.lower() == "false":
            return False

        # Return as string
        return value_text


class FilterBuilder(QWidget):
    """Advanced metadata filter builder widget."""

    filter_changed = Signal()  # Signal when filter changes
    apply_filters = Signal()  # Signal when user wants to apply filters
    rules: list
    available_fields: list
    operators: list
    logic_combo: QComboBox

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        self.available_fields = []
        self.operators = []
        self._setup_ui()

    def _setup_ui(self):
        """Setup the filter builder UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with controls
        header_layout = QHBoxLayout()

        # Logic operator (AND/OR)
        header_layout.addWidget(QLabel("Combine rules with:"))
        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["AND", "OR"])
        self.logic_combo.currentTextChanged.connect(self.filter_changed.emit)
        header_layout.addWidget(self.logic_combo)

        header_layout.addStretch()

        # Add rule button
        add_btn = QPushButton("+ Add Filter Rule")
        add_btn.clicked.connect(self._add_rule)
        header_layout.addWidget(add_btn)

        # Clear all button
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Scroll area for rules
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self.rules_container = QWidget()
        self.rules_layout = QVBoxLayout(self.rules_container)
        self.rules_layout.setAlignment(Qt.AlignTop)
        self.rules_layout.setContentsMargins(0, 5, 0, 5)

        # Placeholder label
        self.placeholder_label = QLabel("No filters applied. Click '+ Add Filter Rule' to start.")
        self.placeholder_label.setStyleSheet("color: gray; font-style: italic; padding: 20px;")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.rules_layout.addWidget(self.placeholder_label)

        scroll_area.setWidget(self.rules_container)
        layout.addWidget(scroll_area)

    def _add_rule(self):
        """Add a new filter rule."""
        rule = FilterRule()
        rule.remove_requested.connect(self._remove_rule)
        rule.apply_requested.connect(self.apply_filters.emit)
        rule.field_input.editTextChanged.connect(lambda: self.filter_changed.emit())
        rule.operator_combo.currentTextChanged.connect(lambda: self.filter_changed.emit())
        rule.value_input.textChanged.connect(lambda: self.filter_changed.emit())

        # Apply available fields if we have them
        if self.available_fields:
            rule.set_available_fields(self.available_fields)

        # Apply operators if we have them
        if self.operators:
            rule.set_operators(self.operators)

        self.rules.append(rule)

        # Hide placeholder if this is the first rule
        if len(self.rules) == 1:
            self.placeholder_label.hide()

        self.rules_layout.addWidget(rule)
        self.filter_changed.emit()

    def _remove_rule(self, rule: FilterRule):
        """Remove a filter rule."""
        if rule in self.rules:
            self.rules.remove(rule)
            rule.deleteLater()

            # Show placeholder if no more rules
            if len(self.rules) == 0:
                self.placeholder_label.show()

            self.filter_changed.emit()

    def _clear_all(self):
        """Clear all filter rules."""
        for rule in self.rules[:]:
            self._remove_rule(rule)

    def get_filter(self) -> Optional[dict[str, Any]]:
        """
        Get the complete filter as a dictionary suitable for vector DB queries.

        Returns:
            Filter dictionary or None if no rules
        """
        if not self.rules:
            return None

        # Get all rule filters
        rule_filters = []
        for rule in self.rules:
            rule_filter = rule.get_filter_dict()
            if rule_filter:
                rule_filters.append(rule_filter)

        if not rule_filters:
            return None

        # Combine with logic operator
        logic = self.logic_combo.currentText().lower()

        if len(rule_filters) == 1:
            return rule_filters[0]

        # Combine multiple filters
        return {f"${logic}": rule_filters}

    def get_filters_split(self) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
        """
        Get filters split into server-side and client-side filters.

        Returns:
            Tuple of (server_side_filter, client_side_filters_list)
        """
        if not self.rules:
            return None, []

        server_side_filters = []
        client_side_filters = []

        for rule in self.rules:
            rule_filter = rule.get_filter_dict()
            if rule_filter:
                if rule_filter.get("__client_side__"):
                    client_side_filters.append(rule_filter)
                else:
                    server_side_filters.append(rule_filter)

        # Build server-side filter
        server_filter = None
        if server_side_filters:
            logic = self.logic_combo.currentText().lower()
            if len(server_side_filters) == 1:
                server_filter = server_side_filters[0]
            else:
                server_filter = {f"${logic}": server_side_filters}

        return server_filter, client_side_filters

    def has_filters(self) -> bool:
        """Check if any filters are defined."""
        return len(self.rules) > 0

    def set_available_fields(self, fields: list[str]):
        """Set available field names for all filter rules."""
        self.available_fields = fields  # Store for future rules
        for rule in self.rules:
            rule.set_available_fields(fields)

    def set_operators(self, operators: list[dict[str, Any]]):
        """Set available operators for all filter rules."""
        self.operators = operators  # Store for future rules
        for rule in self.rules:
            rule.set_operators(operators)

    def get_filter_summary(self) -> str:
        """Get a human-readable summary of the current filters."""
        if not self.rules:
            return "No filters"

        logic = self.logic_combo.currentText()
        rule_summaries = []

        for rule in self.rules:
            field = rule.field_input.currentText().strip()
            operator = rule.operator_combo.currentText()
            value = rule.value_input.text().strip()

            if field and value:
                rule_summaries.append(f"{field} {operator} {value}")

        if not rule_summaries:
            return "No valid filters"

        return f" {logic} ".join(rule_summaries)
