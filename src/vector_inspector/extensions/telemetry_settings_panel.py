from PySide6.QtWidgets import QCheckBox, QHBoxLayout
from vector_inspector.extensions import settings_panel_hook


def add_telemetry_section(parent_layout, settings_service, dialog=None):
    telemetry_checkbox = QCheckBox("Enable anonymous telemetry (app launch events)")
    # Default to checked if not set
    checked = settings_service.get("telemetry.enabled")
    if checked is None:
        checked = True
    telemetry_checkbox.setChecked(checked)
    telemetry_checkbox.setToolTip(
        "Allow the app to send anonymous launch events to help improve reliability. No personal or document data is sent."
    )

    def on_state_changed(state):
        settings_service.set_telemetry_enabled(bool(state))

    telemetry_checkbox.stateChanged.connect(on_state_changed)
    layout = QHBoxLayout()
    layout.addWidget(telemetry_checkbox)
    parent_layout.addLayout(layout)


settings_panel_hook.register(add_telemetry_section)
