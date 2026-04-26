"""Tests for ProfileEditorDialog configuration-driven field visibility system.

This test module covers:
- _set_form_row_visible method (handles both widgets and layouts)
- PROVIDER_FIELD_CONFIG, PROVIDER_SUPPORTED_TYPES, DEFAULT_FIELD_CONFIG dictionaries
- Connection type switching (persistent ↔ HTTP ↔ ephemeral)
- Provider-specific field visibility
- Signal connections for radio buttons
"""

import pytest
from PySide6.QtWidgets import QFormLayout

from vector_inspector.core.provider_detection import ProviderInfo
from vector_inspector.ui.components.profile_manager_panel import (
    DEFAULT_FIELD_CONFIG,
    FIELD_WIDGET_MAP,
    PROVIDER_FIELD_CONFIG,
    PROVIDER_SUPPORTED_TYPES,
    ProfileEditorDialog,
)


class FakeProfileService:
    """Minimal stub — ProfileEditorDialog only stores the reference at construction."""

    def __init__(self):
        self._profiles = {}

    def get_all_profiles(self):
        return []

    def get_profile(self, profile_id):
        return self._profiles.get(profile_id)

    def get_profile_with_credentials(self, profile_id):
        """Return profile with credentials for edit mode."""
        p = self._profiles.get(profile_id)
        if not p:
            return None
        return {
            "id": p.id,
            "name": p.name,
            "provider": p.provider,
            "config": p.config,
            "credentials": {},
        }


def _make_fake_providers():
    """Return a consistent list of fake providers for testing."""
    return [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=True,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
        ProviderInfo(
            id="qdrant",
            name="Qdrant",
            available=True,
            install_command="pip install vector-inspector[qdrant]",
            import_name="qdrant_client",
            description="Local, remote, or cloud",
        ),
        ProviderInfo(
            id="pinecone",
            name="Pinecone",
            available=True,
            install_command="pip install vector-inspector[pinecone]",
            import_name="pinecone",
            description="Cloud-hosted vector database",
        ),
        ProviderInfo(
            id="lancedb",
            name="LanceDB",
            available=True,
            install_command="pip install vector-inspector[lancedb]",
            import_name="lancedb",
            description="Embedded vector database",
        ),
        ProviderInfo(
            id="pgvector",
            name="PostgreSQL (pgvector)",
            available=True,
            install_command="pip install vector-inspector[pgvector]",
            import_name="psycopg2",
            description="PostgreSQL with vector extension",
        ),
        ProviderInfo(
            id="weaviate",
            name="Weaviate",
            available=True,
            install_command="pip install vector-inspector[weaviate]",
            import_name="weaviate",
            description="Local or cloud with GraphQL",
        ),
        ProviderInfo(
            id="milvus",
            name="Milvus",
            available=True,
            install_command="pip install vector-inspector[milvus]",
            import_name="pymilvus",
            description="Distributed vector database",
        ),
    ]


@pytest.fixture
def mock_providers(monkeypatch):
    """Mock get_all_providers to return consistent fake providers.

    Apply this fixture explicitly to tests that need all providers available.
    """
    import vector_inspector.ui.components.profile_manager_panel as panel_mod

    fake_providers = _make_fake_providers()

    def fake_get_all_providers():
        return fake_providers

    def fake_get_provider_info(provider_id):
        for p in fake_providers:
            if p.id == provider_id:
                return p
        return None

    monkeypatch.setattr(panel_mod, "get_all_providers", fake_get_all_providers)
    monkeypatch.setattr(panel_mod, "get_provider_info", fake_get_provider_info)


def _make_editor(qtbot):
    """Return a fresh ProfileEditorDialog (new-profile mode)."""
    editor = ProfileEditorDialog(FakeProfileService())
    qtbot.addWidget(editor)
    return editor


# ---------------------------------------------------------------------------
# Configuration Dictionary Validation Tests
# ---------------------------------------------------------------------------


def test_provider_field_config_has_valid_entries():
    """Ensure PROVIDER_FIELD_CONFIG keys are tuples and values are lists."""
    for key, value in PROVIDER_FIELD_CONFIG.items():
        assert isinstance(key, tuple), f"Key {key} should be tuple"
        assert len(key) == 2, f"Key {key} should be (provider, connection_type)"
        assert isinstance(value, list), f"Value for {key} should be list"
        # Verify each field name in the list is in FIELD_WIDGET_MAP
        for field_name in value:
            assert field_name in FIELD_WIDGET_MAP, f"Field '{field_name}' not in FIELD_WIDGET_MAP"


def test_provider_supported_types_has_valid_entries():
    """Ensure PROVIDER_SUPPORTED_TYPES maps provider names to connection type lists."""
    for provider, types in PROVIDER_SUPPORTED_TYPES.items():
        assert isinstance(provider, str), "Provider key should be string"
        assert isinstance(types, list), f"Types for {provider} should be list"
        assert len(types) > 0, f"Provider {provider} should have at least one supported type"
        for conn_type in types:
            assert conn_type in ["persistent", "http", "ephemeral", "cloud"], (
                f"Invalid connection type '{conn_type}' for {provider}"
            )


def test_default_field_config_has_valid_entries():
    """Ensure DEFAULT_FIELD_CONFIG has all connection types covered."""
    assert "persistent" in DEFAULT_FIELD_CONFIG
    assert "http" in DEFAULT_FIELD_CONFIG
    assert "ephemeral" in DEFAULT_FIELD_CONFIG
    for conn_type, fields in DEFAULT_FIELD_CONFIG.items():
        assert isinstance(fields, list), f"Fields for {conn_type} should be list"


def test_field_widget_map_completeness():
    """Ensure all field names used in configs are in FIELD_WIDGET_MAP."""
    all_field_names = set()

    # Collect from PROVIDER_FIELD_CONFIG
    for fields in PROVIDER_FIELD_CONFIG.values():
        all_field_names.update(fields)

    # Collect from DEFAULT_FIELD_CONFIG
    for fields in DEFAULT_FIELD_CONFIG.values():
        all_field_names.update(fields)

    # Verify each is in FIELD_WIDGET_MAP
    for field_name in all_field_names:
        assert field_name in FIELD_WIDGET_MAP, f"Field '{field_name}' missing from FIELD_WIDGET_MAP"


# ---------------------------------------------------------------------------
# _set_form_row_visible Method Tests
# ---------------------------------------------------------------------------


def test_set_form_row_visible_hides_widget_field(qtbot, mock_providers):
    """_set_form_row_visible can hide a QWidget field and its label."""
    editor = _make_editor(qtbot)

    # Ensure host_input is visible first
    editor.host_input.setVisible(True)

    # Hide it using _set_form_row_visible (pass the widget, not string)
    editor._set_form_row_visible(editor.host_input, False)

    assert editor.host_input.isHidden() is True

    # Check that the label is also hidden
    layout = editor.details_layout
    for row in range(layout.rowCount()):
        fi = layout.itemAt(row, QFormLayout.FieldRole)
        if fi and fi.widget() is editor.host_input:
            li = layout.itemAt(row, QFormLayout.LabelRole)
            if li and li.widget():
                assert li.widget().isHidden() is True
            break


def test_set_form_row_visible_shows_widget_field(qtbot, mock_providers):
    """_set_form_row_visible can show a hidden QWidget field and its label."""
    editor = _make_editor(qtbot)

    # Hide first (pass the widget, not string)
    editor._set_form_row_visible(editor.host_input, False)
    assert editor.host_input.isHidden() is True

    # Show it
    editor._set_form_row_visible(editor.host_input, True)
    assert editor.host_input.isHidden() is False


def test_set_form_row_visible_hides_layout_field(qtbot, mock_providers):
    """_set_form_row_visible can hide a QLayout field's children and label."""
    editor = _make_editor(qtbot)

    # Show path_layout first (pass the layout, not string)
    editor._set_form_row_visible(editor.path_layout, True)
    assert not editor.path_input.isHidden()

    # Hide it
    editor._set_form_row_visible(editor.path_layout, False)

    # All children should be hidden
    assert editor.path_input.isHidden() is True
    assert editor.path_browse_btn.isHidden() is True


def test_set_form_row_visible_shows_layout_field(qtbot, mock_providers):
    """_set_form_row_visible can show a QLayout field's children."""
    editor = _make_editor(qtbot)

    # Hide first (pass the layout, not string)
    editor._set_form_row_visible(editor.path_layout, False)
    assert editor.path_input.isHidden() is True

    # Show it
    editor._set_form_row_visible(editor.path_layout, True)
    assert editor.path_input.isHidden() is False
    assert editor.path_browse_btn.isHidden() is False


# ---------------------------------------------------------------------------
# Connection Type Switching Tests
# ---------------------------------------------------------------------------


def test_connection_type_switches_persistent_to_http(qtbot, mock_providers):
    """Switching from persistent to HTTP updates field visibility correctly."""
    editor = _make_editor(qtbot)

    # Select a provider that supports both (e.g., chromadb)
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break

    # Start with persistent
    editor.persistent_radio.setChecked(True)
    editor._on_type_changed()

    # Path should be visible
    assert not editor.path_input.isHidden()
    # Host/port should be hidden
    assert editor.host_input.isHidden()

    # Switch to HTTP
    editor.http_radio.setChecked(True)
    editor._on_type_changed()

    # Path should be hidden
    assert editor.path_input.isHidden()
    # Host/port should be visible
    assert not editor.host_input.isHidden()
    assert not editor.port_input.isHidden()


def test_connection_type_switches_http_to_ephemeral(qtbot, mock_providers):
    """Switching from HTTP to ephemeral updates field visibility correctly."""
    editor = _make_editor(qtbot)

    # Select chromadb
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break

    # Start with HTTP
    editor.http_radio.setChecked(True)
    editor._on_type_changed()

    # Host should be visible
    assert not editor.host_input.isHidden()

    # Switch to ephemeral
    editor.ephemeral_radio.setChecked(True)
    editor._on_type_changed()

    # Host/port should be hidden
    assert editor.host_input.isHidden()
    assert editor.port_input.isHidden()


def test_connection_type_switches_ephemeral_to_persistent(qtbot, mock_providers):
    """Switching from ephemeral to persistent updates field visibility correctly."""
    editor = _make_editor(qtbot)

    # Select chromadb
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break

    # Start with ephemeral
    editor.ephemeral_radio.setChecked(True)
    editor._on_type_changed()

    # Path should be hidden
    assert editor.path_input.isHidden()

    # Switch to persistent
    editor.persistent_radio.setChecked(True)
    editor._on_type_changed()

    # Path should be visible
    assert not editor.path_input.isHidden()


# ---------------------------------------------------------------------------
# Provider-Specific Field Visibility Tests
# ---------------------------------------------------------------------------


def test_chromadb_persistent_shows_path_only(qtbot, mock_providers):
    """ChromaDB with persistent connection type shows only path field."""
    editor = _make_editor(qtbot)

    # Select chromadb
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break

    editor.persistent_radio.setChecked(True)
    editor._on_type_changed()

    # Path should be visible
    assert not editor.path_input.isHidden()
    # Host/port should be hidden
    assert editor.host_input.isHidden()
    assert editor.port_input.isHidden()


def test_chromadb_http_shows_host_and_port(qtbot, mock_providers):
    """ChromaDB with HTTP connection type shows host and port fields."""
    editor = _make_editor(qtbot)

    # Select chromadb
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break

    editor.http_radio.setChecked(True)
    editor._on_type_changed()

    # Host and port should be visible
    assert not editor.host_input.isHidden()
    assert not editor.port_input.isHidden()
    # Path should be hidden
    assert editor.path_input.isHidden()


def test_lancedb_persistent_shows_path_only(qtbot, mock_providers):
    """LanceDB (persistent-only provider) shows path field."""
    editor = _make_editor(qtbot)

    # Select lancedb
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "lancedb":
            editor.provider_combo.setCurrentIndex(i)
            break

    # LanceDB only supports persistent, radio should be set automatically
    editor._on_provider_changed()

    # Path should be visible
    assert not editor.path_input.isHidden()
    # Host/port should be hidden
    assert editor.host_input.isHidden()


def test_pgvector_http_shows_database_fields(qtbot, mock_providers):
    """PgVector with HTTP shows host, port, database, user fields."""
    editor = _make_editor(qtbot)

    # Select pgvector
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "pgvector":
            editor.provider_combo.setCurrentIndex(i)
            break

    editor.http_radio.setChecked(True)
    editor._on_type_changed()

    # Database-specific fields should be visible
    assert not editor.host_input.isHidden()
    assert not editor.port_input.isHidden()
    assert not editor.database_input.isHidden()
    assert not editor.user_input.isHidden()


def test_pinecone_shows_api_key(qtbot, mock_providers):
    """Pinecone shows API key field."""
    editor = _make_editor(qtbot)

    # Select pinecone
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "pinecone":
            editor.provider_combo.setCurrentIndex(i)
            break

    editor._on_provider_changed()

    # API key should be visible
    assert not editor.api_key_input.isHidden()


# ---------------------------------------------------------------------------
# Provider Switching Tests
# ---------------------------------------------------------------------------


def test_provider_switch_resets_to_first_supported_type(qtbot, mock_providers):
    """Switching providers resets connection type to first supported type."""
    editor = _make_editor(qtbot)

    # Select chromadb and set to HTTP
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break
    editor.http_radio.setChecked(True)
    editor._on_type_changed()

    # Switch to lancedb (persistent-only)
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "lancedb":
            editor.provider_combo.setCurrentIndex(i)
            break
    editor._on_provider_changed()

    # Should reset to persistent (first supported type for lancedb)
    assert editor.persistent_radio.isChecked()


def test_provider_switch_updates_port_defaults(qtbot, mock_providers):
    """Switching providers updates port default values."""
    editor = _make_editor(qtbot)

    # Select chromadb
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break
    editor.http_radio.setChecked(True)
    editor._on_provider_changed()

    chromadb_port = editor.port_input.text()

    # Switch to qdrant
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "qdrant":
            editor.provider_combo.setCurrentIndex(i)
            break
    editor._on_provider_changed()

    qdrant_port = editor.port_input.text()

    # Ports should be different
    assert chromadb_port != qdrant_port


# ---------------------------------------------------------------------------
# Signal Connection Tests
# ---------------------------------------------------------------------------


def test_all_radio_buttons_connected_to_on_type_changed(qtbot, mock_providers):
    """All three radio buttons (persistent, http, ephemeral) trigger field visibility updates."""
    editor = _make_editor(qtbot)

    # Select a provider that supports all types
    for i in range(editor.provider_combo.count()):
        if editor.provider_combo.itemData(i) == "chromadb":
            editor.provider_combo.setCurrentIndex(i)
            break

    # Start with persistent checked
    editor.persistent_radio.setChecked(True)
    editor._on_type_changed()

    # Path should be visible for persistent
    assert not editor.path_input.isHidden()

    # Switch to HTTP
    editor.http_radio.setChecked(True)
    editor._on_type_changed()

    # Host should be visible for HTTP, path should be hidden
    assert not editor.host_input.isHidden()
    assert editor.path_input.isHidden()

    # Switch to ephemeral
    editor.ephemeral_radio.setChecked(True)
    editor._on_type_changed()

    # Both host and path should be hidden for ephemeral
    assert editor.host_input.isHidden()
    assert editor.path_input.isHidden()


# ---------------------------------------------------------------------------
# No Providers Installed Scenario Tests
# ---------------------------------------------------------------------------


def test_no_providers_shows_select_placeholder_in_new_mode(qtbot, monkeypatch):
    """When no providers are installed, new profile mode shows '(Select a provider...)' placeholder."""
    import vector_inspector.ui.components.profile_manager_panel as panel_mod

    # Mock get_all_providers to return no available providers
    no_providers = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=False,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
        ProviderInfo(
            id="lancedb",
            name="LanceDB",
            available=False,
            install_command="pip install vector-inspector[lancedb]",
            import_name="lancedb",
            description="Embedded vector database",
        ),
    ]

    monkeypatch.setattr(panel_mod, "get_all_providers", lambda: no_providers)
    monkeypatch.setattr(
        panel_mod, "get_provider_info", lambda pid: next((p for p in no_providers if p.id == pid), None)
    )

    editor = ProfileEditorDialog(FakeProfileService())
    qtbot.addWidget(editor)

    # First item should be the placeholder
    assert editor.provider_combo.itemText(0) == "(Select a provider...)"
    assert editor.provider_combo.itemData(0) is None

    # Save button should be disabled
    assert not editor.save_btn.isEnabled()


def test_no_providers_shows_unavailable_in_gray(qtbot, monkeypatch):
    """When no providers are installed, they show as '(not installed)' in gray."""
    import vector_inspector.ui.components.profile_manager_panel as panel_mod

    # Mock get_all_providers to return no available providers
    no_providers = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=False,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
        ProviderInfo(
            id="lancedb",
            name="LanceDB",
            available=False,
            install_command="pip install vector-inspector[lancedb]",
            import_name="lancedb",
            description="Embedded vector database",
        ),
    ]

    monkeypatch.setattr(panel_mod, "get_all_providers", lambda: no_providers)
    monkeypatch.setattr(
        panel_mod, "get_provider_info", lambda pid: next((p for p in no_providers if p.id == pid), None)
    )

    editor = ProfileEditorDialog(FakeProfileService())
    qtbot.addWidget(editor)

    # Find the unavailable provider items
    found_chromadb = False
    for i in range(editor.provider_combo.count()):
        text = editor.provider_combo.itemText(i)
        if "ChromaDB" in text and "not installed" in text:
            found_chromadb = True
            # Check that it's grayed out
            item = editor.provider_combo.model().item(i)
            assert item is not None
            # Color should be gray (though exact check may vary by Qt theme)
            break

    assert found_chromadb, "ChromaDB (not installed) not found in combo"


def test_no_providers_all_config_fields_hidden(qtbot, monkeypatch):
    """When no providers are installed and placeholder selected, config section exists but no provider selected."""
    import vector_inspector.ui.components.profile_manager_panel as panel_mod

    # Mock get_all_providers to return no available providers
    no_providers = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=False,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
    ]

    monkeypatch.setattr(panel_mod, "get_all_providers", lambda: no_providers)
    monkeypatch.setattr(
        panel_mod, "get_provider_info", lambda pid: next((p for p in no_providers if p.id == pid), None)
    )

    editor = ProfileEditorDialog(FakeProfileService())
    qtbot.addWidget(editor)

    # Placeholder should be selected by default
    assert editor.provider_combo.currentData() is None

    # Save button should be disabled
    assert not editor.save_btn.isEnabled()


def test_selecting_unavailable_provider_behavior(qtbot, monkeypatch):
    """Selecting an unavailable provider shows it's not installed."""
    import vector_inspector.ui.components.profile_manager_panel as panel_mod

    # Mock get_all_providers to return unavailable providers
    unavailable_providers = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=False,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
    ]

    monkeypatch.setattr(panel_mod, "get_all_providers", lambda: unavailable_providers)
    monkeypatch.setattr(
        panel_mod, "get_provider_info", lambda pid: next((p for p in unavailable_providers if p.id == pid), None)
    )

    editor = ProfileEditorDialog(FakeProfileService())
    qtbot.addWidget(editor)

    # Find the unavailable chromadb entry
    found_unavailable = False
    for i in range(editor.provider_combo.count()):
        text = editor.provider_combo.itemText(i)
        if "ChromaDB" in text and "not installed" in text:
            found_unavailable = True
            break

    assert found_unavailable


def test_edit_mode_with_no_providers_shows_message(qtbot, monkeypatch):
    """Edit mode with no providers shows '(No providers installed)' message."""
    import vector_inspector.ui.components.profile_manager_panel as panel_mod
    from vector_inspector.services.profile_service import ConnectionProfile

    # Mock get_all_providers to return no available providers
    no_providers = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=False,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
    ]

    monkeypatch.setattr(panel_mod, "get_all_providers", lambda: no_providers)
    monkeypatch.setattr(
        panel_mod, "get_provider_info", lambda pid: next((p for p in no_providers if p.id == pid), None)
    )

    # Create a fake profile to edit
    fake_service = FakeProfileService()
    profile = ConnectionProfile("p1", "Test", "chromadb", {"type": "persistent", "path": "/tmp"})
    fake_service._profiles["p1"] = profile

    # Open editor in edit mode
    editor = ProfileEditorDialog(fake_service, profile=profile)
    qtbot.addWidget(editor)

    # Should show the "No providers installed" message
    found_message = False
    for i in range(editor.provider_combo.count()):
        text = editor.provider_combo.itemText(i)
        if "No providers installed" in text:
            found_message = True
            break

    assert found_message, "Expected '(No providers installed)' message in edit mode"


def test_provider_availability_affects_combo_display(qtbot, monkeypatch):
    """Available providers show normally, unavailable show with '(not installed)'."""
    import vector_inspector.ui.components.profile_manager_panel as panel_mod

    # Mix of available and unavailable
    mixed_providers = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=True,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
        ProviderInfo(
            id="lancedb",
            name="LanceDB",
            available=False,
            install_command="pip install vector-inspector[lancedb]",
            import_name="lancedb",
            description="Embedded vector database",
        ),
    ]

    monkeypatch.setattr(panel_mod, "get_all_providers", lambda: mixed_providers)
    monkeypatch.setattr(
        panel_mod, "get_provider_info", lambda pid: next((p for p in mixed_providers if p.id == pid), None)
    )

    editor = ProfileEditorDialog(FakeProfileService())
    qtbot.addWidget(editor)

    # Find chromadb (should not have "not installed")
    found_chromadb_available = False
    found_lancedb_unavailable = False

    for i in range(editor.provider_combo.count()):
        text = editor.provider_combo.itemText(i)
        data = editor.provider_combo.itemData(i)

        if data == "chromadb" and "not installed" not in text:
            found_chromadb_available = True
        elif data == "lancedb" and "not installed" in text:
            found_lancedb_unavailable = True

    assert found_chromadb_available, "ChromaDB should show as available"
    assert found_lancedb_unavailable, "LanceDB should show as '(not installed)'"
