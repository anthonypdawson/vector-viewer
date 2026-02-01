"""Updated main window with multi-database support."""

from typing import Optional

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QStatusBar,
    QToolBar,
)

from vector_inspector.core.connection_manager import ConnectionInstance, ConnectionManager
from vector_inspector.services.profile_service import ProfileService
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.components.connection_manager_panel import ConnectionManagerPanel
from vector_inspector.ui.components.profile_manager_panel import ProfileManagerPanel
from vector_inspector.ui.controllers.connection_controller import ConnectionController
from vector_inspector.ui.main_window_shell import InspectorShell
from vector_inspector.ui.services.dialog_service import DialogService
from vector_inspector.ui.tabs import InspectorTabs


class MainWindow(InspectorShell):
    """Main application window with multi-database support."""

    def __init__(self):
        super().__init__()

        # Core services
        self.connection_manager = ConnectionManager()
        self.profile_service = ProfileService()
        self.settings_service = SettingsService()

        # Controller for connection operations
        self.connection_controller = ConnectionController(
            self.connection_manager, self.profile_service, self
        )

        # State
        self.visualization_view = None

        # View references (will be set in _setup_ui)
        self.info_panel = None
        self.metadata_view = None
        self.search_view = None
        self.connection_panel = None
        self.profile_panel = None

        self.setWindowTitle("Vector Inspector")
        self.setGeometry(100, 100, 1600, 900)

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._restore_session()
        # Listen for settings changes so updates apply immediately
        try:
            self.settings_service.signals.setting_changed.connect(self._on_setting_changed)
        except Exception:
            pass
        # Restore window geometry if present
        try:
            geom = self.settings_service.get_window_geometry()
            if geom and self.settings_service.get_window_restore_geometry():
                try:
                    # restoreGeometry accepts QByteArray; wrap bytes accordingly
                    if isinstance(geom, (bytes, bytearray)):
                        self.restoreGeometry(QByteArray(geom))
                    else:
                        self.restoreGeometry(geom)
                except Exception:
                    # fallback: try passing raw bytes
                    try:
                        self.restoreGeometry(geom)
                    except Exception:
                        pass
        except Exception:
            pass
        # Show splash after main window is visible
        QTimer.singleShot(0, self._maybe_show_splash)

    def _maybe_show_splash(self):
        # Only show splash if not hidden in settings
        if not self.settings_service.get("hide_splash_window", False):
            try:
                from vector_inspector.ui.components.splash_window import SplashWindow

                splash = SplashWindow(self)
                splash.setWindowModality(Qt.ApplicationModal)
                splash.raise_()
                splash.activateWindow()
                if splash.exec() == QDialog.Accepted and splash.should_hide():
                    self.settings_service.set("hide_splash_window", True)
            except Exception as e:
                print(f"[SplashWindow] Failed to show splash: {e}")

    def _setup_ui(self):
        """Setup the main UI layout using InspectorShell."""
        # Left panels - Connections and Profiles
        self.connection_panel = ConnectionManagerPanel(self.connection_manager)
        self.add_left_panel(self.connection_panel, "Active")

        self.profile_panel = ProfileManagerPanel(self.profile_service)
        self.add_left_panel(self.profile_panel, "Profiles")

        # Main content tabs using TabRegistry
        tab_defs = InspectorTabs.get_standard_tabs()

        for i, tab_def in enumerate(tab_defs):
            widget = InspectorTabs.create_tab_widget(tab_def, connection=None)
            self.add_main_tab(widget, tab_def.title)

            # Store references to views (except placeholder)
            if i == InspectorTabs.INFO_TAB:
                self.info_panel = widget
            elif i == InspectorTabs.DATA_TAB:
                self.metadata_view = widget
            elif i == InspectorTabs.SEARCH_TAB:
                self.search_view = widget
            # Visualization is lazy-loaded, so it's a placeholder for now

        # Set Info tab as default
        self.set_main_tab_active(InspectorTabs.INFO_TAB)

        # Connect to tab change to lazy load visualization
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _setup_menu_bar(self):
        """Setup application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_connection_action = QAction("&New Connection...", self)
        new_connection_action.setShortcut("Ctrl+N")
        new_connection_action.triggered.connect(self._new_connection_from_profile)
        file_menu.addAction(new_connection_action)

        file_menu.addSeparator()

        prefs_action = QAction("Preferences...", self)
        prefs_action.setShortcut("Ctrl+,")
        prefs_action.triggered.connect(self._show_preferences_dialog)
        file_menu.addAction(prefs_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Connection menu
        connection_menu = menubar.addMenu("&Connection")

        new_profile_action = QAction("New &Profile...", self)
        new_profile_action.triggered.connect(self._show_profile_editor)
        connection_menu.addAction(new_profile_action)

        connection_menu.addSeparator()

        refresh_action = QAction("&Refresh Collections", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_active_connection)
        connection_menu.addAction(refresh_action)

        connection_menu.addSeparator()

        backup_action = QAction("&Backup/Restore...", self)
        backup_action.triggered.connect(self._show_backup_restore_dialog)
        connection_menu.addAction(backup_action)

        migrate_action = QAction("&Migrate Data...", self)
        migrate_action.triggered.connect(self._show_migration_dialog)
        connection_menu.addAction(migrate_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.cache_action = QAction("Enable &Caching", self)
        self.cache_action.setCheckable(True)
        self.cache_action.setChecked(self.settings_service.get_cache_enabled())
        self.cache_action.triggered.connect(self._toggle_cache)
        view_menu.addAction(self.cache_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        check_update_action = QAction("Check for Update", self)
        check_update_action.triggered.connect(self._check_for_update_from_menu)
        help_menu.addAction(check_update_action)

    def _check_for_update_from_menu(self):
        from PySide6.QtWidgets import QMessageBox

        from vector_inspector.services.update_service import UpdateService
        from vector_inspector.utils.version import get_app_version

        latest = UpdateService.get_latest_release(force_refresh=True)
        if latest:
            current_version = get_app_version()
            latest_version = latest.get("tag_name")
            if latest_version and UpdateService.compare_versions(current_version, latest_version):
                # Show update modal
                self._latest_release = latest
                self._on_update_indicator_clicked(None)
                return
        QMessageBox.information(self, "Check for Update", "No update available.")

    def _setup_toolbar(self):
        """Setup application toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_connection_action = QAction("New Connection", self)
        new_connection_action.triggered.connect(self._new_connection_from_profile)
        toolbar.addAction(new_connection_action)

        toolbar.addSeparator()

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh_active_connection)
        toolbar.addAction(refresh_action)

    def _setup_statusbar(self):
        """Setup status bar with connection breadcrumb and update indicator."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Breadcrumb label
        self.breadcrumb_label = QLabel("No active connection")
        self.statusBar().addPermanentWidget(self.breadcrumb_label)

        # Update indicator label (hidden by default)
        self.update_indicator = QLabel()
        self.update_indicator.setText("")
        self.update_indicator.setStyleSheet(
            "color: #2980b9; font-weight: bold; text-decoration: underline;"
        )
        self.update_indicator.setVisible(False)
        self.update_indicator.setCursor(Qt.PointingHandCursor)
        self.statusBar().addPermanentWidget(self.update_indicator)

        self.statusBar().showMessage("Ready")

        # Connect click event
        self.update_indicator.mousePressEvent = self._on_update_indicator_clicked

        # Check for updates on launch
        import threading

        from PySide6.QtCore import QTimer

        from vector_inspector.services.update_service import UpdateService
        from vector_inspector.utils.version import get_app_version

        def check_updates():
            latest = UpdateService.get_latest_release()
            if latest:
                current_version = get_app_version()
                latest_version = latest.get("tag_name")
                if latest_version and UpdateService.compare_versions(
                    current_version, latest_version
                ):

                    def show_update():
                        self._latest_release = latest
                        self.update_indicator.setText(f"Update available: v{latest_version}")
                        self.update_indicator.setVisible(True)

                    QTimer.singleShot(0, show_update)

        threading.Thread(target=check_updates, daemon=True).start()

    def _show_preferences_dialog(self):
        try:
            from vector_inspector.ui.dialogs.settings_dialog import SettingsDialog

            dlg = SettingsDialog(self.settings_service, self)
            if dlg.exec() == QDialog.Accepted:
                self._apply_settings_to_views()
        except Exception as e:
            print(f"Failed to open preferences: {e}")

    def _apply_settings_to_views(self):
        """Apply relevant settings to existing views."""
        try:
            # Breadcrumb visibility
            enabled = self.settings_service.get_breadcrumb_enabled()
            if self.search_view is not None and hasattr(self.search_view, "breadcrumb_label"):
                self.search_view.breadcrumb_label.setVisible(enabled)
                # also set elide mode
                mode = self.settings_service.get_breadcrumb_elide_mode()
                try:
                    self.search_view.set_elide_mode(mode)
                except Exception:
                    pass

            # Default results
            default_n = self.settings_service.get_default_n_results()
            if self.search_view is not None and hasattr(self.search_view, "n_results_spin"):
                try:
                    self.search_view.n_results_spin.setValue(int(default_n))
                except Exception:
                    pass

        except Exception:
            pass

    def _on_setting_changed(self, key: str, value: object):
        """Handle granular setting change events."""
        try:
            if key == "breadcrumb.enabled":
                enabled = bool(value)
                if self.search_view is not None and hasattr(self.search_view, "breadcrumb_label"):
                    self.search_view.breadcrumb_label.setVisible(enabled)
            elif key == "breadcrumb.elide_mode":
                mode = str(value)
                if self.search_view is not None and hasattr(self.search_view, "set_elide_mode"):
                    self.search_view.set_elide_mode(mode)
            elif key == "search.default_n_results":
                try:
                    n = int(value)
                    if self.search_view is not None and hasattr(self.search_view, "n_results_spin"):
                        self.search_view.n_results_spin.setValue(n)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_update_indicator_clicked(self, event):
        # Show update details dialog
        if not hasattr(self, "_latest_release"):
            return
        DialogService.show_update_details(self._latest_release, self)

    def _connect_signals(self):
        """Connect signals between components."""
        # Connection manager signals
        self.connection_manager.active_connection_changed.connect(
            self._on_active_connection_changed
        )
        self.connection_manager.active_collection_changed.connect(
            self._on_active_collection_changed
        )
        self.connection_manager.collections_updated.connect(self._on_collections_updated)
        self.connection_manager.connection_opened.connect(self._on_connection_opened)

        # Connection controller signals
        self.connection_controller.connection_completed.connect(self._on_connection_completed)

        # Connection panel signals
        self.connection_panel.collection_selected.connect(self._on_collection_selected_from_panel)
        self.connection_panel.add_connection_btn.clicked.connect(self._new_connection_from_profile)

        # Profile panel signals
        self.profile_panel.connect_profile.connect(self._connect_to_profile)

    def _on_connection_completed(
        self, connection_id: str, success: bool, collections: list, error: str
    ):
        """Handle connection completed event from controller."""
        if success:
            # Switch to Active connections tab
            self.set_left_panel_active(0)
            self.statusBar().showMessage(
                f"Connected successfully ({len(collections)} collections)", 5000
            )

    def _on_tab_changed(self, index: int):
        """Handle tab change - lazy load visualization tab."""
        if index == InspectorTabs.VISUALIZATION_TAB and self.visualization_view is None:
            # Lazy load visualization view
            from vector_inspector.ui.views.visualization_view import VisualizationView

            # Get active connection
            active = self.connection_manager.get_active_connection()

            self.visualization_view = VisualizationView(active)
            # Replace placeholder with actual view
            self.remove_main_tab(InspectorTabs.VISUALIZATION_TAB)
            self.add_main_tab(
                self.visualization_view, "Visualization", InspectorTabs.VISUALIZATION_TAB
            )
            self.set_main_tab_active(InspectorTabs.VISUALIZATION_TAB)

            # Set collection if one is already selected
            if active and active.active_collection:
                self.visualization_view.set_collection(active.active_collection)

    def _on_active_connection_changed(self, connection_id):
        """Handle active connection change."""
        if connection_id:
            instance = self.connection_manager.get_connection(connection_id)
            if instance:
                # Update breadcrumb
                self.breadcrumb_label.setText(instance.get_breadcrumb())

                # Update all views with new connection
                self._update_views_with_connection(instance)

                # If there's an active collection, update views with it
                if instance.active_collection:
                    self._update_views_for_collection(instance.active_collection)
            else:
                self.breadcrumb_label.setText("No active connection")
                self._update_views_with_connection(None)
        else:
            self.breadcrumb_label.setText("No active connection")
            self._update_views_with_connection(None)

    def _on_active_collection_changed(self, connection_id: str, collection_name: str):
        """Handle active collection change."""
        instance = self.connection_manager.get_connection(connection_id)
        if instance:
            # Update breadcrumb
            self.breadcrumb_label.setText(instance.get_breadcrumb())

            # Update views if this is the active connection
            if connection_id == self.connection_manager.get_active_connection_id():
                # Show loading immediately when collection changes
                if collection_name:
                    self.connection_controller.loading_dialog.show_loading(
                        f"Loading collection '{collection_name}'..."
                    )
                    QApplication.processEvents()
                    try:
                        self._update_views_for_collection(collection_name)
                    finally:
                        self.connection_controller.loading_dialog.hide_loading()
                else:
                    # Clear collection from views
                    self.connection_controller.loading_dialog.show_loading("Clearing collection...")
                    QApplication.processEvents()
                    try:
                        self._update_views_for_collection(None)
                    finally:
                        self.connection_controller.loading_dialog.hide_loading()

    def _on_collections_updated(self, connection_id: str, collections: list):
        """Handle collections list updated."""
        # UI automatically updates via connection_manager_panel
        pass

    def _on_connection_opened(self, connection_id: str):
        """Handle connection successfully opened."""
        # If this is the active connection, refresh the info panel
        if connection_id == self.connection_manager.get_active_connection_id():
            instance = self.connection_manager.get_connection(connection_id)
            if instance and instance.is_connected:
                self.info_panel.refresh_database_info()

    def _on_collection_selected_from_panel(self, connection_id: str, collection_name: str):
        """Handle collection selection from connection panel."""
        # Show loading dialog while switching collections
        self.connection_controller.loading_dialog.show_loading(
            f"Loading collection '{collection_name}'..."
        )
        QApplication.processEvents()

        try:
            # The connection manager already handled setting active collection
            # Just update the views
            self._update_views_for_collection(collection_name)
        finally:
            self.connection_controller.loading_dialog.hide_loading()

    def _update_views_with_connection(self, connection: Optional[ConnectionInstance]):
        """Update all views with a new connection."""
        # Clear current collection when switching connections
        self.info_panel.current_collection = None
        self.metadata_view.current_collection = None
        self.search_view.current_collection = None
        if self.visualization_view is not None:
            self.visualization_view.current_collection = None

        # Update connection references
        self.info_panel.connection = connection
        self.metadata_view.connection = connection
        self.search_view.connection = connection

        if self.visualization_view is not None:
            self.visualization_view.connection = connection

        # Refresh info panel (will show no collection selected)
        if connection:
            self.info_panel.refresh_database_info()

    def _update_views_for_collection(self, collection_name: str):
        """Update all views with the selected collection."""
        if collection_name:
            # Get active connection ID to use as database identifier
            active = self.connection_manager.get_active_connection()
            database_name = active.id if active else ""

            self.info_panel.set_collection(collection_name, database_name)
            self.metadata_view.set_collection(collection_name, database_name)
            self.search_view.set_collection(collection_name, database_name)

            if self.visualization_view is not None:
                self.visualization_view.set_collection(collection_name)

    def _new_connection_from_profile(self):
        """Show dialog to create new connection (switches to Profiles tab)."""
        self.set_left_panel_active(1)  # Switch to Profiles tab
        DialogService.show_profile_editor_prompt(self)

    def _show_profile_editor(self):
        """Show profile editor to create new profile."""
        self.set_left_panel_active(1)  # Switch to Profiles tab
        self.profile_panel._create_profile()

    def _connect_to_profile(self, profile_id: str):
        """Connect to a profile using the connection controller."""
        success = self.connection_controller.connect_to_profile(profile_id)
        if success:
            # Switch to Active connections tab after initiating connection
            self.set_left_panel_active(0)

    def _refresh_active_connection(self):
        """Refresh collections for the active connection."""
        active = self.connection_manager.get_active_connection()
        if not active or not active.is_connected:
            QMessageBox.information(self, "No Connection", "No active connection to refresh.")
            return

        try:
            collections = active.list_collections()
            self.connection_manager.update_collections(active.id, collections)
            self.statusBar().showMessage(f"Refreshed collections ({len(collections)} found)", 3000)

            # Also refresh info panel
            self.info_panel.refresh_database_info()
        except Exception as e:
            QMessageBox.warning(self, "Refresh Failed", f"Failed to refresh collections: {e}")

    def _restore_session(self):
        """Restore previously active connections on startup."""
        # TODO: Implement session restore
        # For now, we'll just show a message if there are saved profiles
        profiles = self.profile_service.get_all_profiles()
        if profiles:
            self.statusBar().showMessage(
                f"{len(profiles)} saved profile(s) available. Switch to Profiles tab to connect.",
                10000,
            )

        # Apply settings to views after UI is built
        self._apply_settings_to_views()

    def _show_about(self):
        """Show about dialog."""
        DialogService.show_about(self)

    def _toggle_cache(self, checked: bool):
        """Toggle caching on/off."""
        self.settings_service.set_cache_enabled(checked)
        status = "enabled" if checked else "disabled"
        self.statusBar().showMessage(f"Caching {status}", 3000)

    def _show_migration_dialog(self):
        """Show cross-database migration dialog."""
        DialogService.show_migration_dialog(self.connection_manager, self)

    def _show_backup_restore_dialog(self):
        """Show backup/restore dialog for the active collection."""
        # Get active connection and collection
        connection = self.connection_manager.get_active_connection()
        collection_name = self.connection_manager.get_active_collection()

        # Show dialog
        result = DialogService.show_backup_restore_dialog(connection, collection_name or "", self)

        if result == QDialog.Accepted:
            # Refresh collections after restore
            self._refresh_active_connection()

    def show_search_results(self, collection_name: str, results: dict, context_info: str = ""):
        """Display search results in the Search tab.

        This is an extension point that allows external code (e.g., pro features)
        to programmatically display search results.

        Args:
            collection_name: Name of the collection
            results: Search results dictionary
            context_info: Optional context string (e.g., "Similar to: item_123")
        """
        # Switch to search tab
        self.set_main_tab_active(InspectorTabs.SEARCH_TAB)

        # Set the collection if needed
        if self.search_view.current_collection != collection_name:
            active = self.connection_manager.get_active_connection()
            database_name = active.id if active else ""
            self.search_view.set_collection(collection_name, database_name)

        # Display the results
        self.search_view.search_results = results
        self.search_view._display_results(results)

        # Update status with context if provided
        if context_info:
            num_results = len(results.get("ids", [[]])[0])
            self.search_view.results_status.setText(f"{context_info} - Found {num_results} results")

    def closeEvent(self, event):
        """Handle application close."""
        # Clean up connection controller
        self.connection_controller.cleanup()

        # Clean up temp HTML files from visualization view
        if self.visualization_view is not None:
            try:
                self.visualization_view.cleanup_temp_html()
            except Exception:
                pass
        # Close all connections
        self.connection_manager.close_all_connections()

        # Save window geometry if enabled
        try:
            if self.settings_service.get_window_restore_geometry():
                geom = self.saveGeometry()
                # geom may be a QByteArray; convert to raw bytes
                try:
                    if isinstance(geom, QByteArray):
                        b = bytes(geom)
                    else:
                        b = bytes(geom)
                    self.settings_service.set_window_geometry(b)
                except Exception:
                    try:
                        self.settings_service.set_window_geometry(bytes(geom))
                    except Exception:
                        pass
        except Exception:
            pass

        event.accept()
