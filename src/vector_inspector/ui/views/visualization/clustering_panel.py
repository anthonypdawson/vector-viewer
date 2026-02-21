"""Clustering controls panel for vector visualization."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# Feature flags accessed via app_state (passed from parent)


class ClusteringPanel(QGroupBox):
    def __init__(self, parent=None, app_state=None):
        super().__init__("Clustering", parent)
        self.app_state = app_state
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # First row: Algorithm and basic parameters (always visible)
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Algorithm:"))
        self.cluster_algorithm_combo = QComboBox()
        self.cluster_algorithm_combo.addItems(["HDBSCAN", "KMeans", "DBSCAN", "OPTICS"])
        first_row.addWidget(self.cluster_algorithm_combo)

        # HDBSCAN basic parameters
        self.cluster_hdb_min_size_label = QLabel("min_cluster_size:")
        first_row.addWidget(self.cluster_hdb_min_size_label)
        self.cluster_hdb_min_size_spin = QSpinBox()
        self.cluster_hdb_min_size_spin.setMinimum(2)
        self.cluster_hdb_min_size_spin.setMaximum(100)
        self.cluster_hdb_min_size_spin.setValue(5)
        first_row.addWidget(self.cluster_hdb_min_size_spin)

        self.cluster_hdb_min_samples_label = QLabel("min_samples:")
        first_row.addWidget(self.cluster_hdb_min_samples_label)
        self.cluster_hdb_min_samples_spin = QSpinBox()
        self.cluster_hdb_min_samples_spin.setMinimum(1)
        self.cluster_hdb_min_samples_spin.setMaximum(100)
        self.cluster_hdb_min_samples_spin.setValue(5)
        first_row.addWidget(self.cluster_hdb_min_samples_spin)

        # KMeans basic parameters
        self.cluster_kmeans_n_label = QLabel("n_clusters:")
        first_row.addWidget(self.cluster_kmeans_n_label)
        self.cluster_kmeans_n_spin = QSpinBox()
        self.cluster_kmeans_n_spin.setMinimum(2)
        self.cluster_kmeans_n_spin.setMaximum(50)
        self.cluster_kmeans_n_spin.setValue(5)
        first_row.addWidget(self.cluster_kmeans_n_spin)
        self.cluster_kmeans_n_label.hide()
        self.cluster_kmeans_n_spin.hide()

        # DBSCAN basic parameters
        self.cluster_dbscan_eps_label = QLabel("eps:")
        first_row.addWidget(self.cluster_dbscan_eps_label)
        self.cluster_dbscan_eps_spin = QDoubleSpinBox()
        self.cluster_dbscan_eps_spin.setMinimum(0.1)
        self.cluster_dbscan_eps_spin.setMaximum(100.0)
        self.cluster_dbscan_eps_spin.setValue(0.5)
        self.cluster_dbscan_eps_spin.setSingleStep(0.1)
        first_row.addWidget(self.cluster_dbscan_eps_spin)
        self.cluster_dbscan_eps_label.hide()
        self.cluster_dbscan_eps_spin.hide()

        self.cluster_dbscan_min_samples_label = QLabel("min_samples:")
        first_row.addWidget(self.cluster_dbscan_min_samples_label)
        self.cluster_dbscan_min_samples_spin = QSpinBox()
        self.cluster_dbscan_min_samples_spin.setMinimum(1)
        self.cluster_dbscan_min_samples_spin.setMaximum(100)
        self.cluster_dbscan_min_samples_spin.setValue(5)
        first_row.addWidget(self.cluster_dbscan_min_samples_spin)
        self.cluster_dbscan_min_samples_label.hide()
        self.cluster_dbscan_min_samples_spin.hide()

        # OPTICS basic parameters
        self.cluster_optics_min_samples_label = QLabel("min_samples:")
        first_row.addWidget(self.cluster_optics_min_samples_label)
        self.cluster_optics_min_samples_spin = QSpinBox()
        self.cluster_optics_min_samples_spin.setMinimum(1)
        self.cluster_optics_min_samples_spin.setMaximum(100)
        self.cluster_optics_min_samples_spin.setValue(5)
        first_row.addWidget(self.cluster_optics_min_samples_spin)
        self.cluster_optics_min_samples_label.hide()
        self.cluster_optics_min_samples_spin.hide()

        self.cluster_optics_max_eps_label = QLabel("max_eps:")
        first_row.addWidget(self.cluster_optics_max_eps_label)
        self.cluster_optics_max_eps_spin = QDoubleSpinBox()
        self.cluster_optics_max_eps_spin.setMinimum(0.1)
        self.cluster_optics_max_eps_spin.setMaximum(100.0)
        self.cluster_optics_max_eps_spin.setValue(10.0)
        self.cluster_optics_max_eps_spin.setSingleStep(0.1)
        first_row.addWidget(self.cluster_optics_max_eps_spin)
        self.cluster_optics_max_eps_label.hide()
        self.cluster_optics_max_eps_spin.hide()

        first_row.addStretch()

        # Clustering result message label (initially hidden)
        self.cluster_result_label = QLabel("")
        self.cluster_result_label.setStyleSheet("color: green; font-weight: bold;")
        self.cluster_result_label.setVisible(False)
        first_row.addWidget(self.cluster_result_label)

        first_row.addStretch()

        # Checkbox to save cluster labels to metadata
        self.save_to_metadata_checkbox = QCheckBox("Save labels to metadata")
        self.save_to_metadata_checkbox.setChecked(False)
        self.save_to_metadata_checkbox.setToolTip(
            "When checked, cluster assignments will be saved to item metadata as 'cluster' field"
        )
        first_row.addWidget(self.save_to_metadata_checkbox)

        # Run clustering button
        self.cluster_button = QPushButton("Run Clustering")
        first_row.addWidget(self.cluster_button)

        layout.addLayout(first_row)

        # Advanced settings toggle button
        self.advanced_toggle = QPushButton("▶ Advanced Settings")
        self.advanced_toggle.setFlat(True)
        self.advanced_toggle.setStyleSheet("text-align: left; padding: 5px;")
        layout.addWidget(self.advanced_toggle)

        # Advanced settings widget (initially hidden)
        self.advanced_widget = QWidget()
        advanced_layout = QVBoxLayout()
        advanced_layout.setContentsMargins(20, 0, 0, 0)  # Indent advanced section

        # Advanced parameters row
        adv_row = QHBoxLayout()

        # HDBSCAN advanced parameters
        self.cluster_hdb_adv_epsilon_label = QLabel("cluster_selection_epsilon:")
        adv_row.addWidget(self.cluster_hdb_adv_epsilon_label)
        self.cluster_hdb_adv_epsilon_spin = QDoubleSpinBox()
        self.cluster_hdb_adv_epsilon_spin.setMinimum(0.0)
        self.cluster_hdb_adv_epsilon_spin.setMaximum(1.0)
        self.cluster_hdb_adv_epsilon_spin.setValue(0.0)
        self.cluster_hdb_adv_epsilon_spin.setSingleStep(0.01)
        adv_row.addWidget(self.cluster_hdb_adv_epsilon_spin)

        self.cluster_hdb_adv_single_label = QLabel("allow_single_cluster:")
        adv_row.addWidget(self.cluster_hdb_adv_single_label)
        self.cluster_hdb_adv_single_check = QCheckBox()
        adv_row.addWidget(self.cluster_hdb_adv_single_check)

        self.cluster_hdb_adv_metric_label = QLabel("metric:")
        adv_row.addWidget(self.cluster_hdb_adv_metric_label)
        self.cluster_hdb_adv_metric_combo = QComboBox()
        self.cluster_hdb_adv_metric_combo.addItems(["euclidean", "manhattan", "cosine"])
        adv_row.addWidget(self.cluster_hdb_adv_metric_combo)

        self.cluster_hdb_adv_alpha_label = QLabel("alpha:")
        adv_row.addWidget(self.cluster_hdb_adv_alpha_label)
        self.cluster_hdb_adv_alpha_spin = QDoubleSpinBox()
        self.cluster_hdb_adv_alpha_spin.setMinimum(0.0)
        self.cluster_hdb_adv_alpha_spin.setMaximum(2.0)
        self.cluster_hdb_adv_alpha_spin.setValue(1.0)
        self.cluster_hdb_adv_alpha_spin.setSingleStep(0.1)
        adv_row.addWidget(self.cluster_hdb_adv_alpha_spin)

        self.cluster_hdb_adv_method_label = QLabel("cluster_selection_method:")
        adv_row.addWidget(self.cluster_hdb_adv_method_label)
        self.cluster_hdb_adv_method_combo = QComboBox()
        self.cluster_hdb_adv_method_combo.addItems(["eom", "leaf"])
        adv_row.addWidget(self.cluster_hdb_adv_method_combo)

        # Hide HDBSCAN advanced by default
        self.cluster_hdb_adv_epsilon_label.hide()
        self.cluster_hdb_adv_epsilon_spin.hide()
        self.cluster_hdb_adv_single_label.hide()
        self.cluster_hdb_adv_single_check.hide()
        self.cluster_hdb_adv_metric_label.hide()
        self.cluster_hdb_adv_metric_combo.hide()
        self.cluster_hdb_adv_alpha_label.hide()
        self.cluster_hdb_adv_alpha_spin.hide()
        self.cluster_hdb_adv_method_label.hide()
        self.cluster_hdb_adv_method_combo.hide()

        # KMeans advanced parameters
        self.cluster_kmeans_adv_init_label = QLabel("init:")
        adv_row.addWidget(self.cluster_kmeans_adv_init_label)
        self.cluster_kmeans_adv_init_combo = QComboBox()
        self.cluster_kmeans_adv_init_combo.addItems(["k-means++", "random"])
        adv_row.addWidget(self.cluster_kmeans_adv_init_combo)

        self.cluster_kmeans_adv_maxiter_label = QLabel("max_iter:")
        adv_row.addWidget(self.cluster_kmeans_adv_maxiter_label)
        self.cluster_kmeans_adv_maxiter_spin = QSpinBox()
        self.cluster_kmeans_adv_maxiter_spin.setMinimum(100)
        self.cluster_kmeans_adv_maxiter_spin.setMaximum(1000)
        self.cluster_kmeans_adv_maxiter_spin.setValue(300)
        self.cluster_kmeans_adv_maxiter_spin.setSingleStep(50)
        adv_row.addWidget(self.cluster_kmeans_adv_maxiter_spin)

        self.cluster_kmeans_adv_tol_label = QLabel("tol:")
        adv_row.addWidget(self.cluster_kmeans_adv_tol_label)
        self.cluster_kmeans_adv_tol_spin = QDoubleSpinBox()
        self.cluster_kmeans_adv_tol_spin.setMinimum(0.0001)
        self.cluster_kmeans_adv_tol_spin.setMaximum(1.0)
        self.cluster_kmeans_adv_tol_spin.setValue(0.0001)
        self.cluster_kmeans_adv_tol_spin.setDecimals(4)
        self.cluster_kmeans_adv_tol_spin.setSingleStep(0.0001)
        adv_row.addWidget(self.cluster_kmeans_adv_tol_spin)

        self.cluster_kmeans_adv_algo_label = QLabel("algorithm:")
        adv_row.addWidget(self.cluster_kmeans_adv_algo_label)
        self.cluster_kmeans_adv_algo_combo = QComboBox()
        self.cluster_kmeans_adv_algo_combo.addItems(["lloyd", "elkan"])
        adv_row.addWidget(self.cluster_kmeans_adv_algo_combo)

        # Hide KMeans advanced by default
        self.cluster_kmeans_adv_init_label.hide()
        self.cluster_kmeans_adv_init_combo.hide()
        self.cluster_kmeans_adv_maxiter_label.hide()
        self.cluster_kmeans_adv_maxiter_spin.hide()
        self.cluster_kmeans_adv_tol_label.hide()
        self.cluster_kmeans_adv_tol_spin.hide()
        self.cluster_kmeans_adv_algo_label.hide()
        self.cluster_kmeans_adv_algo_combo.hide()

        # DBSCAN advanced parameters
        self.cluster_dbscan_adv_metric_label = QLabel("metric:")
        adv_row.addWidget(self.cluster_dbscan_adv_metric_label)
        self.cluster_dbscan_adv_metric_combo = QComboBox()
        self.cluster_dbscan_adv_metric_combo.addItems(["euclidean", "manhattan", "cosine", "l1", "l2"])
        adv_row.addWidget(self.cluster_dbscan_adv_metric_combo)

        self.cluster_dbscan_adv_algo_label = QLabel("algorithm:")
        adv_row.addWidget(self.cluster_dbscan_adv_algo_label)
        self.cluster_dbscan_adv_algo_combo = QComboBox()
        self.cluster_dbscan_adv_algo_combo.addItems(["auto", "ball_tree", "kd_tree", "brute"])
        adv_row.addWidget(self.cluster_dbscan_adv_algo_combo)

        self.cluster_dbscan_adv_leaf_label = QLabel("leaf_size:")
        adv_row.addWidget(self.cluster_dbscan_adv_leaf_label)
        self.cluster_dbscan_adv_leaf_spin = QSpinBox()
        self.cluster_dbscan_adv_leaf_spin.setMinimum(10)
        self.cluster_dbscan_adv_leaf_spin.setMaximum(100)
        self.cluster_dbscan_adv_leaf_spin.setValue(30)
        adv_row.addWidget(self.cluster_dbscan_adv_leaf_spin)

        # Hide DBSCAN advanced by default
        self.cluster_dbscan_adv_metric_label.hide()
        self.cluster_dbscan_adv_metric_combo.hide()
        self.cluster_dbscan_adv_algo_label.hide()
        self.cluster_dbscan_adv_algo_combo.hide()
        self.cluster_dbscan_adv_leaf_label.hide()
        self.cluster_dbscan_adv_leaf_spin.hide()

        # OPTICS advanced parameters
        self.cluster_optics_adv_metric_label = QLabel("metric:")
        adv_row.addWidget(self.cluster_optics_adv_metric_label)
        self.cluster_optics_adv_metric_combo = QComboBox()
        self.cluster_optics_adv_metric_combo.addItems(["euclidean", "manhattan", "cosine", "l1", "l2"])
        adv_row.addWidget(self.cluster_optics_adv_metric_combo)

        self.cluster_optics_adv_xi_label = QLabel("xi:")
        adv_row.addWidget(self.cluster_optics_adv_xi_label)
        self.cluster_optics_adv_xi_spin = QDoubleSpinBox()
        self.cluster_optics_adv_xi_spin.setMinimum(0.0)
        self.cluster_optics_adv_xi_spin.setMaximum(1.0)
        self.cluster_optics_adv_xi_spin.setValue(0.05)
        self.cluster_optics_adv_xi_spin.setSingleStep(0.01)
        adv_row.addWidget(self.cluster_optics_adv_xi_spin)

        self.cluster_optics_adv_method_label = QLabel("cluster_method:")
        adv_row.addWidget(self.cluster_optics_adv_method_label)
        self.cluster_optics_adv_method_combo = QComboBox()
        self.cluster_optics_adv_method_combo.addItems(["xi", "dbscan"])
        adv_row.addWidget(self.cluster_optics_adv_method_combo)

        self.cluster_optics_adv_algo_label = QLabel("algorithm:")
        adv_row.addWidget(self.cluster_optics_adv_algo_label)
        self.cluster_optics_adv_algo_combo = QComboBox()
        self.cluster_optics_adv_algo_combo.addItems(["auto", "ball_tree", "kd_tree", "brute"])
        adv_row.addWidget(self.cluster_optics_adv_algo_combo)

        self.cluster_optics_adv_leaf_label = QLabel("leaf_size:")
        adv_row.addWidget(self.cluster_optics_adv_leaf_label)
        self.cluster_optics_adv_leaf_spin = QSpinBox()
        self.cluster_optics_adv_leaf_spin.setMinimum(10)
        self.cluster_optics_adv_leaf_spin.setMaximum(100)
        self.cluster_optics_adv_leaf_spin.setValue(30)
        adv_row.addWidget(self.cluster_optics_adv_leaf_spin)

        # Hide OPTICS advanced by default
        self.cluster_optics_adv_metric_label.hide()
        self.cluster_optics_adv_metric_combo.hide()
        self.cluster_optics_adv_xi_label.hide()
        self.cluster_optics_adv_xi_spin.hide()
        self.cluster_optics_adv_method_label.hide()
        self.cluster_optics_adv_method_combo.hide()
        self.cluster_optics_adv_algo_label.hide()
        self.cluster_optics_adv_algo_combo.hide()
        self.cluster_optics_adv_leaf_label.hide()
        self.cluster_optics_adv_leaf_spin.hide()

        adv_row.addStretch()
        advanced_layout.addLayout(adv_row)

        self.advanced_widget.setLayout(advanced_layout)
        self.advanced_widget.hide()  # Initially hidden
        layout.addWidget(self.advanced_widget)

        self.setLayout(layout)

        # Build control mapping for easier management
        self._build_control_mapping()

        # Apply feature flag gating to advanced controls
        self._apply_feature_gating()

        # Connect toggle button
        self.advanced_toggle.clicked.connect(self._toggle_advanced)

        # Connect algorithm change to show/hide appropriate controls
        self.cluster_algorithm_combo.currentTextChanged.connect(self._on_algorithm_changed)
        # Initialize visibility
        self._on_algorithm_changed(self.cluster_algorithm_combo.currentText())

    def _build_control_mapping(self):
        """Build a mapping of controls organized by algorithm and type."""
        self._controls = {
            "HDBSCAN": {
                "basic": [
                    (self.cluster_hdb_min_size_label, self.cluster_hdb_min_size_spin),
                    (self.cluster_hdb_min_samples_label, self.cluster_hdb_min_samples_spin),
                ],
                "advanced": [
                    (self.cluster_hdb_adv_epsilon_label, self.cluster_hdb_adv_epsilon_spin),
                    (self.cluster_hdb_adv_single_label, self.cluster_hdb_adv_single_check),
                    (self.cluster_hdb_adv_metric_label, self.cluster_hdb_adv_metric_combo),
                    (self.cluster_hdb_adv_alpha_label, self.cluster_hdb_adv_alpha_spin),
                    (self.cluster_hdb_adv_method_label, self.cluster_hdb_adv_method_combo),
                ],
            },
            "KMeans": {
                "basic": [
                    (self.cluster_kmeans_n_label, self.cluster_kmeans_n_spin),
                ],
                "advanced": [
                    (self.cluster_kmeans_adv_init_label, self.cluster_kmeans_adv_init_combo),
                    (self.cluster_kmeans_adv_maxiter_label, self.cluster_kmeans_adv_maxiter_spin),
                    (self.cluster_kmeans_adv_tol_label, self.cluster_kmeans_adv_tol_spin),
                    (self.cluster_kmeans_adv_algo_label, self.cluster_kmeans_adv_algo_combo),
                ],
            },
            "DBSCAN": {
                "basic": [
                    (self.cluster_dbscan_eps_label, self.cluster_dbscan_eps_spin),
                    (self.cluster_dbscan_min_samples_label, self.cluster_dbscan_min_samples_spin),
                ],
                "advanced": [
                    (self.cluster_dbscan_adv_metric_label, self.cluster_dbscan_adv_metric_combo),
                    (self.cluster_dbscan_adv_algo_label, self.cluster_dbscan_adv_algo_combo),
                    (self.cluster_dbscan_adv_leaf_label, self.cluster_dbscan_adv_leaf_spin),
                ],
            },
            "OPTICS": {
                "basic": [
                    (self.cluster_optics_min_samples_label, self.cluster_optics_min_samples_spin),
                    (self.cluster_optics_max_eps_label, self.cluster_optics_max_eps_spin),
                ],
                "advanced": [
                    (self.cluster_optics_adv_metric_label, self.cluster_optics_adv_metric_combo),
                    (self.cluster_optics_adv_xi_label, self.cluster_optics_adv_xi_spin),
                    (self.cluster_optics_adv_method_label, self.cluster_optics_adv_method_combo),
                    (self.cluster_optics_adv_algo_label, self.cluster_optics_adv_algo_combo),
                    (self.cluster_optics_adv_leaf_label, self.cluster_optics_adv_leaf_spin),
                ],
            },
        }

    def _apply_feature_gating(self):
        """Apply feature flag gating to advanced controls."""
        if not self.app_state or not self.app_state.advanced_features_enabled:
            tooltip = (
                self.app_state.get_feature_tooltip("Advanced clustering parameters")
                if self.app_state
                else "Advanced clustering parameters available in Vector Studio"
            )
            # Disable all advanced controls and set tooltip
            for algorithm_controls in self._controls.values():
                for label, widget in algorithm_controls.get("advanced", []):
                    widget.setEnabled(False)
                    widget.setToolTip(tooltip)
                    if label:
                        label.setEnabled(False)
                        label.setToolTip(tooltip)

    def _toggle_advanced(self):
        """Toggle visibility of advanced settings."""
        if self.advanced_widget.isVisible():
            self.advanced_widget.hide()
            self.advanced_toggle.setText("▶ Advanced Settings (Premium)")
        else:
            self.advanced_widget.show()
            self.advanced_toggle.setText("▼ Advanced Settings (Premium)")
            # Update visibility based on current algorithm
            self._on_algorithm_changed(self.cluster_algorithm_combo.currentText())

    def _on_algorithm_changed(self, algorithm: str):
        """Show/hide parameters based on selected algorithm."""
        # Hide all controls for all algorithms
        for algo, controls in self._controls.items():
            is_selected = algo == algorithm
            # Show/hide basic controls
            for label, widget in controls["basic"]:
                label.setVisible(is_selected)
                widget.setVisible(is_selected)

            # Only update advanced controls if section is expanded
            if self.advanced_widget.isVisible():
                for label, widget in controls["advanced"]:
                    label.setVisible(is_selected)
                    widget.setVisible(is_selected)

        # Clear any previous clustering result when algorithm changes
        if hasattr(self, "cluster_result_label"):
            self.cluster_result_label.setVisible(False)
            self.cluster_result_label.setText("")

    def get_clustering_params(self) -> dict:
        """Get clustering parameters based on selected algorithm.

        Returns:
            Dictionary of parameters for the selected algorithm.
        """
        algorithm = self.cluster_algorithm_combo.currentText()
        params = {}
        advanced_enabled = self.app_state.advanced_features_enabled if self.app_state else False

        if algorithm == "HDBSCAN":
            params["min_cluster_size"] = self.cluster_hdb_min_size_spin.value()
            params["min_samples"] = self.cluster_hdb_min_samples_spin.value()
            # Advanced parameters (only if feature enabled)
            if advanced_enabled:
                params["cluster_selection_epsilon"] = self.cluster_hdb_adv_epsilon_spin.value()
                params["allow_single_cluster"] = self.cluster_hdb_adv_single_check.isChecked()
                params["metric"] = self.cluster_hdb_adv_metric_combo.currentText()
                params["alpha"] = self.cluster_hdb_adv_alpha_spin.value()
                params["cluster_selection_method"] = self.cluster_hdb_adv_method_combo.currentText()
        elif algorithm == "KMeans":
            params["n_clusters"] = self.cluster_kmeans_n_spin.value()
            # Advanced parameters (only if feature enabled)
            if advanced_enabled:
                params["init"] = self.cluster_kmeans_adv_init_combo.currentText()
                params["max_iter"] = self.cluster_kmeans_adv_maxiter_spin.value()
                params["tol"] = self.cluster_kmeans_adv_tol_spin.value()
                params["algorithm"] = self.cluster_kmeans_adv_algo_combo.currentText()
        elif algorithm == "DBSCAN":
            params["eps"] = self.cluster_dbscan_eps_spin.value()
            params["min_samples"] = self.cluster_dbscan_min_samples_spin.value()
            # Advanced parameters (only if feature enabled)
            if advanced_enabled:
                params["metric"] = self.cluster_dbscan_adv_metric_combo.currentText()
                params["algorithm"] = self.cluster_dbscan_adv_algo_combo.currentText()
                params["leaf_size"] = self.cluster_dbscan_adv_leaf_spin.value()
        elif algorithm == "OPTICS":
            params["min_samples"] = self.cluster_optics_min_samples_spin.value()
            params["max_eps"] = self.cluster_optics_max_eps_spin.value()
            # Advanced parameters (only if feature enabled)
            if advanced_enabled:
                params["metric"] = self.cluster_optics_adv_metric_combo.currentText()
                params["xi"] = self.cluster_optics_adv_xi_spin.value()
                params["cluster_method"] = self.cluster_optics_adv_method_combo.currentText()
                params["algorithm"] = self.cluster_optics_adv_algo_combo.currentText()
                params["leaf_size"] = self.cluster_optics_adv_leaf_spin.value()

        return params
