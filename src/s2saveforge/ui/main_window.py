from __future__ import annotations

from pathlib import Path
from string import Template

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from s2saveforge.core.models import SaveGame
from s2saveforge.core.parser import ReadOnlySaveFormatError, UnsupportedSaveFormatError
from s2saveforge.core.service import SaveSession
from s2saveforge.core.validators import ValidationIssue, group_issues_by_entity, summarize_issues
from s2saveforge import __app_name__, __app_shortname__


class MainWindow(QMainWindow):
    THEMES = {
        "light": {
            "window_bg": "#f3efe7",
            "toolbar_bg": "#ddd2bf",
            "toolbar_text": "#221a14",
            "toolbutton_bg": "#fffdf8",
            "toolbutton_border": "#b8a790",
            "toolbutton_hover": "#efe4d2",
            "surface_bg": "#fffdf9",
            "surface_border": "#cdbca4",
            "field_bg": "#fffefb",
            "field_border": "#c5b59e",
            "field_text": "#1d1814",
            "muted_text": "#5f5143",
            "primary_text": "#201913",
            "section_text": "#403227",
            "button_bg": "#6e4f2f",
            "button_hover": "#5f4328",
            "button_text": "#fffdf9",
            "button_disabled": "#b9ab97",
            "tab_bg": "#e7dbc8",
            "tab_active_bg": "#fffefb",
            "selection_bg": "#d7b98f",
            "selection_text": "#1b1612",
            "status_bg": "#ddd2bf",
            "status_text": "#201913",
        },
        "dark": {
            "window_bg": "#14181d",
            "toolbar_bg": "#1d242c",
            "toolbar_text": "#eef2f5",
            "toolbutton_bg": "#212a33",
            "toolbutton_border": "#415161",
            "toolbutton_hover": "#2b3743",
            "surface_bg": "#1a2129",
            "surface_border": "#34424f",
            "field_bg": "#11171d",
            "field_border": "#4a5b69",
            "field_text": "#f3f6f8",
            "muted_text": "#b7c2cb",
            "primary_text": "#f7fafc",
            "section_text": "#dbe5eb",
            "button_bg": "#d9a15d",
            "button_hover": "#ebaf66",
            "button_text": "#16110c",
            "button_disabled": "#667583",
            "tab_bg": "#202933",
            "tab_active_bg": "#11171d",
            "selection_bg": "#3f6f9a",
            "selection_text": "#ffffff",
            "status_bg": "#1d242c",
            "status_text": "#eef2f5",
        },
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(__app_name__)

        self.session = SaveSession()
        self._current_sim_id = ""
        self._current_household_filter_id = ""
        self._theme_name = "light"

        self._build_actions()
        self._build_layout()
        self._apply_window_style()

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")
        self._refresh_ui()

    def _build_actions(self) -> None:
        action_open = QAction("Open File", self)
        action_open.triggered.connect(self.open_file)

        action_open_folder = QAction("Open Folder", self)
        action_open_folder.triggered.connect(self.open_folder)

        action_load_demo = QAction("Load Demo", self)
        action_load_demo.triggered.connect(self.load_demo)

        action_backup = QAction("Create Backup", self)
        action_backup.triggered.connect(self.create_backup)

        action_save = QAction("Save", self)
        action_save.triggered.connect(self.save_file)

        action_undo = QAction("Undo", self)
        action_undo.triggered.connect(self.undo)

        action_redo = QAction("Redo", self)
        action_redo.triggered.connect(self.redo)

        action_validate = QAction("Validate", self)
        action_validate.triggered.connect(self.run_validation)

        self.action_light_theme = QAction("Light Theme", self)
        self.action_light_theme.setCheckable(True)
        self.action_light_theme.triggered.connect(lambda: self._set_theme("light"))

        self.action_dark_theme = QAction("Dark Theme", self)
        self.action_dark_theme.setCheckable(True)
        self.action_dark_theme.triggered.connect(lambda: self._set_theme("dark"))

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        theme_group.addAction(self.action_light_theme)
        theme_group.addAction(self.action_dark_theme)
        self.action_light_theme.setChecked(True)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction(action_open)
        toolbar.addAction(action_open_folder)
        toolbar.addAction(action_load_demo)
        toolbar.addSeparator()
        toolbar.addAction(action_backup)
        toolbar.addAction(action_save)
        toolbar.addSeparator()
        toolbar.addAction(action_undo)
        toolbar.addAction(action_redo)
        toolbar.addSeparator()
        toolbar.addAction(action_validate)
        toolbar.addSeparator()
        toolbar.addAction(self.action_light_theme)
        toolbar.addAction(self.action_dark_theme)

    def _build_layout(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header = QFrame(root)
        header.setObjectName("summaryCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        header_layout.setSpacing(8)

        title = QLabel(__app_name__, header)
        title.setObjectName("heroTitle")
        header_layout.addWidget(title)

        self.banner_label = QLabel(
            f"Open a Sims 2 folder or demo save to start working in {__app_shortname__}.",
            header,
        )
        self.banner_label.setWordWrap(True)
        header_layout.addWidget(self.banner_label)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(18)

        self.mode_label = QLabel("Mode: No save loaded", header)
        self.source_label = QLabel("Source: -", header)
        self.counts_label = QLabel("Households: 0 | Sims: 0 | Relationships: 0", header)
        self.health_label = QLabel("Health: -", header)

        for widget in (self.mode_label, self.source_label, self.counts_label, self.health_label):
            widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            stats_row.addWidget(widget, 1)

        header_layout.addLayout(stats_row)
        root_layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal, root)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, 1)

        left_panel = QWidget(splitter)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.scope_title = QLabel("Households", left_panel)
        self.scope_title.setObjectName("sectionTitle")
        left_layout.addWidget(self.scope_title)

        self.household_list = QListWidget(left_panel)
        self.household_list.currentItemChanged.connect(self._on_household_scope_changed)
        left_layout.addWidget(self.household_list, 1)

        search_label = QLabel("Sim Search", left_panel)
        search_label.setObjectName("sectionTitle")
        left_layout.addWidget(search_label)

        self.sim_search = QLineEdit(left_panel)
        self.sim_search.setPlaceholderText("Filter by Sim name or ID")
        self.sim_search.textChanged.connect(self._refresh_sim_list)
        left_layout.addWidget(self.sim_search)

        self.sim_list = QListWidget(left_panel)
        self.sim_list.currentItemChanged.connect(self._on_sim_selected)
        left_layout.addWidget(self.sim_list, 2)

        right_panel = QTabWidget(splitter)
        right_panel.setDocumentMode(True)
        self.main_tabs = right_panel

        overview_page = QWidget(right_panel)
        overview_layout = QVBoxLayout(overview_page)
        overview_layout.setContentsMargins(12, 12, 12, 12)
        overview_layout.setSpacing(10)

        self.overview_text = QTextEdit(overview_page)
        self.overview_text.setReadOnly(True)
        overview_layout.addWidget(self.overview_text)
        right_panel.addTab(overview_page, "Overview")

        editor_page = QWidget(right_panel)
        editor_layout = QVBoxLayout(editor_page)
        editor_layout.setContentsMargins(12, 12, 12, 12)
        editor_layout.setSpacing(12)

        household_box = QGroupBox("Selected Household", editor_page)
        household_form = QFormLayout(household_box)
        self.household_select = QComboBox(household_box)
        self.household_select.currentIndexChanged.connect(self._on_household_selected)

        self.funds_spin = QSpinBox(household_box)
        self.funds_spin.setRange(-9_999_999, 999_999_999)

        self.apply_household_button = QPushButton("Apply Household Funds", household_box)
        self.apply_household_button.clicked.connect(self.apply_household_changes)

        household_form.addRow("Household", self.household_select)
        household_form.addRow("Funds", self.funds_spin)
        household_form.addRow("", self.apply_household_button)
        editor_layout.addWidget(household_box)

        sim_box = QGroupBox("Selected Sim", editor_page)
        sim_form = QFormLayout(sim_box)

        self.sim_name = QLineEdit(sim_box)
        self.sim_age = QComboBox(sim_box)
        self.sim_age.addItems(["unknown", "baby", "toddler", "child", "teen", "adult", "elder"])
        self.sim_aspiration = QLineEdit(sim_box)
        self.sim_career = QLineEdit(sim_box)
        self.sim_career_level = QSpinBox(sim_box)
        self.sim_career_level.setRange(1, 20)

        sim_form.addRow("Name", self.sim_name)
        sim_form.addRow("Age", self.sim_age)
        sim_form.addRow("Aspiration", self.sim_aspiration)
        sim_form.addRow("Career", self.sim_career)
        sim_form.addRow("Career level", self.sim_career_level)

        tables_row = QHBoxLayout()
        tables_row.setSpacing(12)

        self.needs_table = QTableWidget(sim_box)
        self.needs_table.setColumnCount(2)
        self.needs_table.setHorizontalHeaderLabels(["Need", "Value"])
        self.needs_table.horizontalHeader().setStretchLastSection(True)

        self.skills_table = QTableWidget(sim_box)
        self.skills_table.setColumnCount(2)
        self.skills_table.setHorizontalHeaderLabels(["Skill", "Value"])
        self.skills_table.horizontalHeader().setStretchLastSection(True)

        tables_row.addWidget(self.needs_table)
        tables_row.addWidget(self.skills_table)

        tables_widget = QWidget(sim_box)
        tables_widget.setLayout(tables_row)

        sim_form.addRow("Needs and skills", tables_widget)

        self.apply_sim_button = QPushButton("Apply Sim Changes", sim_box)
        self.apply_sim_button.clicked.connect(self.apply_sim_changes)
        sim_form.addRow("", self.apply_sim_button)
        editor_layout.addWidget(sim_box, 1)

        right_panel.addTab(editor_page, "Editor")

        self.validation_view = QTextEdit(right_panel)
        self.validation_view.setReadOnly(True)
        right_panel.addTab(self.validation_view, "Validation")

        self.history_view = QTextEdit(right_panel)
        self.history_view.setReadOnly(True)
        right_panel.addTab(self.history_view, "Changes")

        issues_page = QWidget(right_panel)
        issues_layout = QVBoxLayout(issues_page)
        issues_layout.setContentsMargins(12, 12, 12, 12)
        issues_layout.setSpacing(10)

        issues_filter_row = QHBoxLayout()
        issues_filter_row.setSpacing(8)

        issues_scope_label = QLabel("Issue Scope", issues_page)
        issues_scope_label.setObjectName("sectionTitle")
        issues_filter_row.addWidget(issues_scope_label)

        self.issue_scope_select = QComboBox(issues_page)
        self.issue_scope_select.currentIndexChanged.connect(self._refresh_issue_center)
        issues_filter_row.addWidget(self.issue_scope_select, 1)

        issues_layout.addLayout(issues_filter_row)

        self.issue_summary_view = QTextEdit(issues_page)
        self.issue_summary_view.setReadOnly(True)
        issues_layout.addWidget(self.issue_summary_view, 1)

        self.issue_detail_list = QListWidget(issues_page)
        self.issue_detail_list.currentItemChanged.connect(self._on_issue_selected)
        issues_layout.addWidget(self.issue_detail_list, 1)

        self.issue_detail_view = QTextEdit(issues_page)
        self.issue_detail_view.setReadOnly(True)
        issues_layout.addWidget(self.issue_detail_view, 1)

        right_panel.addTab(issues_page, "Issue Center")

        package_page = QWidget(right_panel)
        package_layout = QVBoxLayout(package_page)
        package_layout.setContentsMargins(12, 12, 12, 12)
        package_layout.setSpacing(10)

        package_filter_row = QHBoxLayout()
        package_filter_row.setSpacing(8)

        package_scope_label = QLabel("Package Source", package_page)
        package_scope_label.setObjectName("sectionTitle")
        package_filter_row.addWidget(package_scope_label)

        self.package_source_select = QComboBox(package_page)
        self.package_source_select.currentIndexChanged.connect(self._refresh_package_inspector)
        package_filter_row.addWidget(self.package_source_select, 1)
        package_layout.addLayout(package_filter_row)

        self.package_view = QTextEdit(package_page)
        self.package_view.setReadOnly(True)
        package_layout.addWidget(self.package_view, 1)

        right_panel.addTab(package_page, "Package Inspector")

        resources_page = QWidget(right_panel)
        resources_layout = QVBoxLayout(resources_page)
        resources_layout.setContentsMargins(12, 12, 12, 12)
        resources_layout.setSpacing(10)

        resource_filter_row = QHBoxLayout()
        resource_filter_row.setSpacing(8)

        resource_type_label = QLabel("Resource Type Filter", resources_page)
        resource_type_label.setObjectName("sectionTitle")
        resource_filter_row.addWidget(resource_type_label)

        self.resource_type_select = QComboBox(resources_page)
        self.resource_type_select.currentIndexChanged.connect(self._refresh_resource_browser)
        resource_filter_row.addWidget(self.resource_type_select, 1)
        resources_layout.addLayout(resource_filter_row)

        self.resource_summary_view = QTextEdit(resources_page)
        self.resource_summary_view.setReadOnly(True)
        resources_layout.addWidget(self.resource_summary_view, 1)

        self.resource_list = QListWidget(resources_page)
        self.resource_list.currentItemChanged.connect(self._on_resource_selected)
        resources_layout.addWidget(self.resource_list, 1)

        self.resource_detail_view = QTextEdit(resources_page)
        self.resource_detail_view.setReadOnly(True)
        resources_layout.addWidget(self.resource_detail_view, 1)

        right_panel.addTab(resources_page, "Resources")

        file_inventory_page = QWidget(right_panel)
        file_inventory_layout = QVBoxLayout(file_inventory_page)
        file_inventory_layout.setContentsMargins(12, 12, 12, 12)
        file_inventory_layout.setSpacing(10)

        self.file_inventory_view = QTextEdit(file_inventory_page)
        self.file_inventory_view.setReadOnly(True)
        file_inventory_layout.addWidget(self.file_inventory_view, 1)

        right_panel.addTab(file_inventory_page, "Files")

        splitter.setSizes([320, 960])

    def _apply_window_style(self) -> None:
        theme = self.THEMES[self._theme_name]
        stylesheet = Template(
            """
            QMainWindow {
                background: $window_bg;
                color: $primary_text;
            }
            QToolBar {
                background: $toolbar_bg;
                border: none;
                spacing: 6px;
                padding: 6px;
                color: $toolbar_text;
            }
            QToolButton {
                background: $toolbutton_bg;
                color: $toolbar_text;
                border: 1px solid $toolbutton_border;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QToolButton:hover {
                background: $toolbutton_hover;
            }
            QToolButton:checked {
                background: $selection_bg;
                color: $selection_text;
            }
            #summaryCard {
                background: $surface_bg;
                border: 1px solid $surface_border;
                border-radius: 12px;
            }
            #heroTitle {
                font-size: 22px;
                font-weight: 700;
                color: $primary_text;
            }
            #sectionTitle {
                font-size: 13px;
                font-weight: 700;
                color: $section_text;
            }
            QLabel, QGroupBox, QCheckBox, QRadioButton {
                color: $primary_text;
            }
            QListWidget, QLineEdit, QComboBox, QSpinBox, QTextEdit, QTableWidget {
                background: $field_bg;
                color: $field_text;
                border: 1px solid $field_border;
                border-radius: 8px;
                selection-background-color: $selection_bg;
                selection-color: $selection_text;
            }
            QGroupBox {
                border: 1px solid $surface_border;
                border-radius: 10px;
                margin-top: 14px;
                background: $surface_bg;
                font-weight: 700;
                color: $primary_text;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QPushButton {
                background: $button_bg;
                color: $button_text;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: $button_hover;
            }
            QPushButton:disabled {
                background: $button_disabled;
                color: $button_text;
            }
            QTabWidget::pane {
                border: 1px solid $surface_border;
                background: $surface_bg;
                border-radius: 10px;
            }
            QTabBar::tab {
                background: $tab_bg;
                color: $primary_text;
                padding: 8px 12px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: $tab_active_bg;
                color: $primary_text;
            }
            QStatusBar {
                background: $status_bg;
                color: $status_text;
            }
            QHeaderView::section {
                background: $tab_bg;
                color: $primary_text;
                border: 1px solid $field_border;
                padding: 4px 6px;
            }
            QAbstractItemView {
                alternate-background-color: $surface_bg;
            }
            """
        ).substitute(theme)
        self.setStyleSheet(stylesheet)

    def _set_theme(self, theme_name: str) -> None:
        if theme_name not in self.THEMES or theme_name == self._theme_name:
            return
        self._theme_name = theme_name
        self._apply_window_style()
        self.statusBar().showMessage(f"Theme changed to {theme_name}")

    def _is_preview_mode(self) -> bool:
        savegame = self.session.current
        return bool(savegame and savegame.version.startswith("fs-preview:"))

    def _current_household(self):
        savegame = self.session.current
        index = self.household_select.currentIndex()
        if savegame is None or index < 0 or index >= len(savegame.households):
            return None
        return savegame.households[index]

    def _on_household_scope_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self._current_household_filter_id = ""
            self._refresh_scope_views()
            return

        household_id = current.data(Qt.UserRole)
        if not isinstance(household_id, str):
            return

        self._current_household_filter_id = household_id
        household = self._find_household_by_id(household_id)
        if household is not None:
            self.funds_spin.setValue(household.funds)
        self._set_household_combo_by_id(household_id, emit_signal=False)
        self._refresh_scope_views()

    def _on_household_selected(self, index: int) -> None:
        savegame = self.session.current
        if savegame is None or index < 0 or index >= len(savegame.households):
            return

        household = savegame.households[index]
        self.funds_spin.setValue(household.funds)
        self._current_household_filter_id = household.id
        self._select_household_list_item(household.id, emit_signal=False)
        self._refresh_scope_views()

    def _on_sim_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._current_sim_id = ""
            self._clear_sim_editor()
            self._refresh_overview()
            return

        sim_id = current.data(Qt.UserRole)
        if not isinstance(sim_id, str):
            return

        savegame = self.session.current
        if savegame is None:
            return

        sim = next((entry for entry in savegame.sims if entry.id == sim_id), None)
        if sim is None:
            return

        self._current_sim_id = sim_id
        self.sim_name.setText(sim.name)
        self.sim_age.setCurrentText(sim.age_stage)
        self.sim_aspiration.setText(sim.aspiration)
        self.sim_career.setText(sim.career)
        self.sim_career_level.setValue(sim.career_level)
        self._fill_table(self.needs_table, sim.needs)
        self._fill_table(self.skills_table, sim.skills)
        self._current_household_filter_id = sim.household_id
        household = self._find_household_by_id(sim.household_id)
        if household is not None:
            self.funds_spin.setValue(household.funds)
        self._set_household_combo_by_id(sim.household_id, emit_signal=False)
        self._select_household_list_item(sim.household_id, emit_signal=False)
        self._refresh_detail_views()

    def _fill_table(self, table: QTableWidget, data: dict[str, int]) -> None:
        table.setRowCount(len(data))
        for row, (name, value) in enumerate(sorted(data.items())):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            value_item = QTableWidgetItem(str(value))
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, value_item)

    def _table_to_dict(self, table: QTableWidget) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in range(table.rowCount()):
            key_item = table.item(row, 0)
            value_item = table.item(row, 1)
            if key_item is None or value_item is None:
                continue
            key = key_item.text().strip()
            if not key:
                continue
            try:
                value = int(value_item.text().strip())
            except ValueError:
                value = 0
            result[key] = value
        return result

    def open_file(self) -> None:
        file_path, _selected = QFileDialog.getOpenFileName(
            self,
            "Open save file",
            str(Path.cwd()),
            "Save files (*.s2json *.json)",
        )
        if file_path:
            self._load_path(Path(file_path))

    def open_folder(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Open Sims 2 save folder",
            str(Path.cwd()),
        )
        if folder_path:
            self._load_path(Path(folder_path))

    def load_demo(self) -> None:
        demo_path = Path(__file__).resolve().parents[3] / "sample_data" / "demo_save.s2json"
        self._load_path(demo_path)

    def _load_path(self, path: Path) -> None:
        try:
            self.session.load(path)
        except UnsupportedSaveFormatError as exc:
            QMessageBox.warning(self, "Unsupported format", str(exc))
            return
        except Exception as exc:  # pragma: no cover
            QMessageBox.critical(self, "Load failed", str(exc))
            return

        self._current_sim_id = ""
        self._current_household_filter_id = ""
        self._refresh_ui()
        if path.is_dir():
            self.statusBar().showMessage(f"Loaded folder preview: {path}")
        else:
            self.statusBar().showMessage(f"Loaded: {path}")

    def _refresh_ui(self) -> None:
        savegame = self.session.current
        is_preview = self._is_preview_mode()

        self.household_list.blockSignals(True)
        self.household_select.blockSignals(True)
        self.sim_list.blockSignals(True)

        self.household_list.clear()
        self.household_select.clear()
        self.sim_list.clear()

        if savegame is None:
            self.scope_title.setText("Households")
            self.banner_label.setText(
                f"Open a Sims 2 folder or demo save to start working in {__app_shortname__}."
            )
            self.mode_label.setText("Mode: No save loaded")
            self.source_label.setText("Source: -")
            self.counts_label.setText("Households: 0 | Sims: 0 | Relationships: 0")
            self.health_label.setText("Health: -")
            self._clear_sim_editor()
            self._set_editing_enabled(False)
            self._refresh_history_view()
            self._refresh_overview()
            self._refresh_issue_center()
            self._refresh_package_source_options()
            self._refresh_package_inspector()
            self._refresh_resource_type_options()
            self._refresh_resource_browser()
            self._refresh_file_inventory_view()
            self.household_list.blockSignals(False)
            self.household_select.blockSignals(False)
            self.sim_list.blockSignals(False)
            return

        self.scope_title.setText("Neighborhoods" if is_preview else "Households")
        for household in savegame.households:
            summary = f"{household.name} | members: {len(household.members)}"
            item = QListWidgetItem(summary)
            item.setData(Qt.UserRole, household.id)
            self.household_list.addItem(item)
            self.household_select.addItem(f"{household.name} ({household.id})", household.id)

        if not self._current_household_filter_id and savegame.households:
            self._current_household_filter_id = savegame.households[0].id

        self._select_household_list_item(self._current_household_filter_id)
        self._set_household_combo_by_id(self._current_household_filter_id)
        self._refresh_sim_list(select_current=False)
        self._set_editing_enabled(not is_preview)
        self._refresh_header()
        self._refresh_history_view()
        self._refresh_overview()
        self._refresh_issue_scope_options()
        self._refresh_issue_center()
        self._refresh_package_source_options()
        self._refresh_package_inspector()
        self._refresh_resource_type_options()
        self._refresh_resource_browser()
        self._refresh_file_inventory_view()

        self.household_list.blockSignals(False)
        self.household_select.blockSignals(False)
        self.sim_list.blockSignals(False)

    def _refresh_header(self) -> None:
        savegame = self.session.current
        if savegame is None:
            return

        source = str(self.session.source_path) if self.session.source_path else "-"
        if self._is_preview_mode():
            self.banner_label.setText(
                f"Read-only folder preview loaded in {__app_shortname__}. You can inspect neighborhoods and Sims now; package-level editing comes next."
            )
            self.mode_label.setText("Mode: Folder preview (read-only)")
        else:
            self.banner_label.setText(
                f"Editable save loaded in {__app_shortname__}. Use the left side to narrow scope, then change household or Sim data in the editor."
            )
            self.mode_label.setText("Mode: Editable MVP save")

        self.source_label.setText(f"Source: {source}")
        self.counts_label.setText(
            "Households: "
            f"{len(savegame.households)} | Sims: {len(savegame.sims)} | Relationships: {len(savegame.relationships)}"
        )
        summary = summarize_issues(self.session.validate())
        self.health_label.setText(
            f"Health: {summary['error']} errors | {summary['warning']} warnings | {summary['info']} info"
        )

    def _refresh_scope_views(self) -> None:
        self._refresh_sim_list()
        self._refresh_detail_views()

    def _refresh_detail_views(self) -> None:
        self._refresh_overview()
        self._refresh_package_source_options()
        self._refresh_package_inspector()
        self._refresh_resource_type_options()
        self._refresh_resource_browser()
        self._refresh_file_inventory_view()

    def _refresh_sim_list(self, *, select_current: bool = True) -> None:
        savegame = self.session.current
        blocker = QSignalBlocker(self.sim_list)
        self.sim_list.clear()

        if savegame is None:
            del blocker
            return

        search_term = self.sim_search.text().strip().lower()
        filtered_sims = []
        for sim in savegame.sims:
            if self._current_household_filter_id and sim.household_id != self._current_household_filter_id:
                continue
            haystack = f"{sim.name} {sim.id}".lower()
            if search_term and search_term not in haystack:
                continue
            filtered_sims.append(sim)

        for sim in filtered_sims:
            label = f"{sim.name} ({sim.id})"
            if sim.age_stage and sim.age_stage != "unknown":
                label += f" - {sim.age_stage}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, sim.id)
            self.sim_list.addItem(item)

        if not filtered_sims:
            self._current_sim_id = ""
            self._clear_sim_editor()
            del blocker
            self._refresh_overview()
            return

        target_id = self._current_sim_id if select_current else filtered_sims[0].id
        target_row = 0
        for row in range(self.sim_list.count()):
            item = self.sim_list.item(row)
            if item.data(Qt.UserRole) == target_id:
                target_row = row
                break

        self.sim_list.setCurrentRow(target_row)
        current_item = self.sim_list.currentItem()
        del blocker
        self._on_sim_selected(current_item, None)

    def _refresh_overview(self) -> None:
        savegame = self.session.current
        if savegame is None:
            self.overview_text.setPlainText(
                "No save loaded yet.\n\nUse Open Folder for a real Sims 2 save or Load Demo for the editable MVP file."
            )
            return

        household = self._current_household()
        selected_sim = next((sim for sim in savegame.sims if sim.id == self._current_sim_id), None)
        mode_line = "Folder preview (read-only)" if self._is_preview_mode() else "Editable MVP save"
        issues = self.session.validate()
        issue_total = len(issues)

        lines = [
            "Workspace Overview",
            "",
            f"Mode: {mode_line}",
            f"Source: {self.session.source_path or '-'}",
            f"Households: {len(savegame.households)}",
            f"Sims: {len(savegame.sims)}",
            f"Relationships: {len(savegame.relationships)}",
            f"Validation issues: {issue_total}",
            "",
        ]

        if savegame.metadata:
            if savegame.metadata.get("source_kind") == "folder_preview":
                lines.extend(
                    [
                        "Folder Preview",
                        f"Neighborhood root: {savegame.metadata.get('neighborhoods_root', '-')}",
                        f"Neighborhood count: {savegame.metadata.get('neighborhood_count', 0)}",
                        "NeighborhoodManager.package: "
                        + ("present" if savegame.metadata.get("neighborhood_manager_exists") else "missing"),
                        f"Story entries found: {savegame.metadata.get('total_story_entries', 0)}",
                        "",
                    ]
                )
                package_role_profile = savegame.metadata.get("package_role_profile", [])
                if isinstance(package_role_profile, list) and package_role_profile:
                    lines.extend(["Package role profile"])
                    for entry in package_role_profile[:6]:
                        lines.append(f"{entry.get('role', 'Unknown')} x {entry.get('count', 0)}")
                    lines.append("")
                simpe_reference = savegame.metadata.get("simpe_reference", {})
                if isinstance(simpe_reference, dict) and simpe_reference.get("loaded"):
                    lines.extend(
                        [
                            "SimPE reference",
                            f"Source: {simpe_reference.get('source_path', '-')}",
                            "Known hood kinds: "
                            + ", ".join(simpe_reference.get("known_hood_kinds", []) or ["-"]),
                            "",
                        ]
                    )

        if household is not None:
            scope_label = "Neighborhood" if self._is_preview_mode() else "Household"
            lines.extend(
                [
                    f"Selected {scope_label}: {household.name}",
                    f"ID: {household.id}",
                    f"Members: {len(household.members)}",
                    f"Funds: {household.funds}",
                    "",
                ]
            )
            if household.metadata:
                lines.extend(
                    [
                        "Selected scope details",
                        f"Directory: {household.metadata.get('directory_path', '-')}",
                        "Main package: "
                        + ("present" if household.metadata.get("main_package_exists", True) else "missing"),
                        "Main package role: "
                        + str(household.metadata.get("main_package_info", {}).get("package_role", "-")),
                        "Characters dir: "
                        + ("present" if household.metadata.get("characters_dir_exists", True) else "missing"),
                        "Lots dir: "
                        + ("present" if household.metadata.get("lots_dir_exists", True) else "missing"),
                        f"Character packages: {household.metadata.get('character_count', len(household.members))}",
                        f"Lot packages: {household.metadata.get('lot_count', 0)}",
                        f"Suburbs: {household.metadata.get('suburb_count', 0)}",
                        f"Thumbnail packages: {household.metadata.get('thumbnail_package_count', 0)}",
                        f"Story entries: {household.metadata.get('story_entry_count', 0)}",
                        "",
                    ]
                )

        if selected_sim is not None:
            lines.extend(
                [
                    f"Selected Sim: {selected_sim.name}",
                    f"Sim ID: {selected_sim.id}",
                    f"Age: {selected_sim.age_stage}",
                    f"Aspiration: {selected_sim.aspiration or '-'}",
                    f"Career: {selected_sim.career or '-'}",
                    f"Needs tracked: {len(selected_sim.needs)}",
                    f"Skills tracked: {len(selected_sim.skills)}",
                ]
            )
            if selected_sim.metadata:
                lines.extend(
                    [
                        f"Package path: {selected_sim.metadata.get('package_path', '-')}",
                        f"Package size: {selected_sim.metadata.get('package_size', 0)} bytes",
                    ]
                )
        elif self.sim_list.count() > 0:
            lines.append("Select a Sim on the left to inspect and edit details here.")
        else:
            lines.append("No Sims match the current household scope and search filter.")

        self.overview_text.setPlainText("\n".join(lines))

    def _refresh_history_view(self) -> None:
        labels = self.session.history_labels
        if not labels:
            self.history_view.setPlainText("No changes yet.")
            return

        lines = [f"{idx + 1}. {label}" for idx, label in enumerate(labels)]
        if self._is_preview_mode():
            lines.insert(0, "Read-only filesystem preview loaded from a Sims 2 folder.")
        self.history_view.setPlainText("\n".join(lines))

    def _refresh_issue_scope_options(self) -> None:
        savegame = self.session.current
        current_value = self.issue_scope_select.currentData()
        self.issue_scope_select.blockSignals(True)
        self.issue_scope_select.clear()
        self.issue_scope_select.addItem("All issues", "__all__")
        self.issue_scope_select.addItem("Global issues", "_global")

        if savegame is not None:
            for household in savegame.households:
                self.issue_scope_select.addItem(f"{household.id} issues", household.id)

        for index in range(self.issue_scope_select.count()):
            if self.issue_scope_select.itemData(index) == current_value:
                self.issue_scope_select.setCurrentIndex(index)
                break
        else:
            self.issue_scope_select.setCurrentIndex(0)
        self.issue_scope_select.blockSignals(False)

    def _issues_for_current_scope(self) -> list[ValidationIssue]:
        issues = self.session.validate()
        scope = self.issue_scope_select.currentData()
        if scope in (None, "__all__"):
            return issues
        if scope == "_global":
            return [issue for issue in issues if not issue.entity_id]
        return [issue for issue in issues if issue.entity_id == scope or issue.entity_id.startswith(f"{scope}->")]

    def _refresh_issue_center(self) -> None:
        issues = self._issues_for_current_scope()
        summary = summarize_issues(issues)
        grouped = group_issues_by_entity(issues)

        if not issues:
            self.issue_summary_view.setPlainText(
                "No issues in the selected scope.\n\nThis is where grouped validation and repair candidates will appear."
            )
            self.issue_detail_list.clear()
            self.issue_detail_view.setPlainText("No issue selected.")
            return

        summary_lines = [
            "Issue Summary",
            "",
            f"Total: {summary['total']}",
            f"Errors: {summary['error']}",
            f"Warnings: {summary['warning']}",
            f"Info: {summary['info']}",
            "",
            f"Affected entities: {len(grouped)}",
        ]
        self.issue_summary_view.setPlainText("\n".join(summary_lines))

        self.issue_detail_list.blockSignals(True)
        self.issue_detail_list.clear()
        for issue in issues:
            entity = issue.entity_id or "global"
            item = QListWidgetItem(f"[{issue.severity.upper()}] {entity} - {issue.code}")
            item.setData(Qt.UserRole, issue.code)
            item.setData(Qt.UserRole + 1, issue.message)
            item.setData(Qt.UserRole + 2, entity)
            item.setData(Qt.UserRole + 3, issue.severity)
            self.issue_detail_list.addItem(item)
        self.issue_detail_list.blockSignals(False)

        if self.issue_detail_list.count() > 0:
            self.issue_detail_list.setCurrentRow(0)
        else:
            self.issue_detail_view.setPlainText("No issue selected.")

    def _on_issue_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.issue_detail_view.setPlainText("No issue selected.")
            return

        issue_code = current.data(Qt.UserRole)
        message = current.data(Qt.UserRole + 1)
        entity = current.data(Qt.UserRole + 2)
        severity = current.data(Qt.UserRole + 3)

        lines = [
            "Selected Issue",
            "",
            f"Severity: {severity}",
            f"Entity: {entity}",
            f"Code: {issue_code}",
            "",
            "Message",
            str(message),
            "",
            "Next step",
            "This issue is currently read-only. A future repair workflow will attach suggested fixes here.",
        ]
        self.issue_detail_view.setPlainText("\n".join(lines))

    def _refresh_package_source_options(self) -> None:
        savegame = self.session.current
        current_value = self.package_source_select.currentData()
        preferred_value = current_value
        self.package_source_select.blockSignals(True)
        self.package_source_select.clear()

        if savegame is None:
            self.package_source_select.blockSignals(False)
            return

        manager_path = savegame.metadata.get("neighborhood_manager_path")
        if manager_path:
            self.package_source_select.addItem("NeighborhoodManager.package", manager_path)

        household = self._current_household()
        if household is not None:
            main_path = household.metadata.get("main_package_path")
            if main_path:
                self.package_source_select.addItem(f"{household.id} main package", main_path)
            for suburb_path in household.metadata.get("suburb_package_paths", []):
                self.package_source_select.addItem(Path(suburb_path).name, suburb_path)
            for thumbnail_path in household.metadata.get("thumbnail_package_paths", []):
                self.package_source_select.addItem(Path(thumbnail_path).name, thumbnail_path)

        selected_sim = next((sim for sim in savegame.sims if sim.id == self._current_sim_id), None)
        if selected_sim is not None and selected_sim.metadata.get("package_path"):
            preferred_value = selected_sim.metadata["package_path"]
            self.package_source_select.addItem(
                f"{selected_sim.id} character package",
                selected_sim.metadata["package_path"],
            )
        elif household is not None and household.metadata.get("main_package_path"):
            preferred_value = household.metadata["main_package_path"]

        for index in range(self.package_source_select.count()):
            if self.package_source_select.itemData(index) == preferred_value:
                self.package_source_select.setCurrentIndex(index)
                break
        else:
            if self.package_source_select.count() > 0:
                self.package_source_select.setCurrentIndex(0)

        self.package_source_select.blockSignals(False)

    def _lookup_package_info(self, path_text: str) -> dict | None:
        savegame = self.session.current
        if savegame is None:
            return None

        if savegame.metadata.get("neighborhood_manager_path") == path_text:
            return savegame.metadata.get("neighborhood_manager_info")

        for household in savegame.households:
            if household.metadata.get("main_package_path") == path_text:
                return household.metadata.get("main_package_info")
            for package_info in household.metadata.get("suburb_package_infos", []):
                if isinstance(package_info, dict) and package_info.get("path") == path_text:
                    return package_info
            for package_info in household.metadata.get("thumbnail_package_infos", []):
                if isinstance(package_info, dict) and package_info.get("path") == path_text:
                    return package_info

        for sim in savegame.sims:
            if sim.metadata.get("package_path") == path_text:
                return sim.metadata.get("package_info")

        return None

    def _refresh_package_inspector(self) -> None:
        if self.package_source_select.count() == 0:
            self.package_view.setPlainText(
                "No package selected.\n\nLoad a save and choose a package source to inspect its DBPF header."
            )
            return

        selected_path = self.package_source_select.currentData()
        if not isinstance(selected_path, str):
            self.package_view.setPlainText("No package selected.")
            return

        package_info = self._lookup_package_info(selected_path)
        if not package_info:
            self.package_view.setPlainText("No package metadata available for the selected source.")
            return

        lines = [
            "Package Inspector",
            "",
            f"Path: {package_info.get('path', selected_path)}",
            f"Exists: {package_info.get('exists', False)}",
        ]

        if not package_info.get("exists", False):
            self.package_view.setPlainText("\n".join(lines))
            return

        lines.extend(
            [
                f"Package role: {package_info.get('package_role', 'Unknown')}",
                f"Size: {package_info.get('size', 0)} bytes",
                f"Magic: {package_info.get('magic', '-')}",
                f"DBPF: {package_info.get('is_dbpf', False)}",
                f"DBPF version: {package_info.get('dbpf_version_major', '-')}."
                f"{package_info.get('dbpf_version_minor', '-')}",
                f"Index version: {package_info.get('index_version_major', '-')}."
                f"{package_info.get('index_version_minor', '-')}",
                f"Index entries: {package_info.get('index_entry_count', 0)}",
                f"Parsed index entries: {package_info.get('parsed_index_entry_count', 0)}",
                f"Index entry size: {package_info.get('index_entry_size', 0)}",
                f"Index offset: {package_info.get('index_offset', 0)}",
                f"Index size: {package_info.get('index_size', 0)}",
                f"Hole entries: {package_info.get('hole_entry_count', 0)}",
                f"Hole offset: {package_info.get('hole_offset', 0)}",
                f"Hole size: {package_info.get('hole_size', 0)}",
            ]
        )

        top_resource_types = package_info.get("top_resource_types", [])
        if isinstance(top_resource_types, list) and top_resource_types:
            lines.extend(["", "Top resource types"])
            for entry in top_resource_types:
                lines.append(
                    f"{entry.get('type_hex', '-')} "
                    f"[{entry.get('type_short_name', 'UNK')}] "
                    f"({entry.get('type_name', 'Unknown Resource')}, "
                    f"{entry.get('domain_hint', 'Unknown')}) x "
                    f"{entry.get('count', 0)}"
                )

        domain_profile = package_info.get("domain_profile", [])
        if isinstance(domain_profile, list) and domain_profile:
            lines.extend(["", "Likely domain profile"])
            for entry in domain_profile:
                lines.append(f"{entry.get('domain', 'Unknown')} x {entry.get('count', 0)}")

        preview_entries = package_info.get("index_entries_preview", [])
        if isinstance(preview_entries, list) and preview_entries:
            lines.extend(["", "Index entry preview"])
            for idx, entry in enumerate(preview_entries[:5], start=1):
                lines.append(
                    f"{idx}. {entry.get('type_hex', '-')} "
                    f"[{entry.get('type_short_name', 'UNK')}] "
                    f"({entry.get('type_name', 'Unknown Resource')}) / "
                    f"{entry.get('group_hex', '-')} / "
                    f"{entry.get('instance_hex', '-')} | offset {entry.get('file_offset', 0)} | "
                    f"size {entry.get('file_size', 0)} | domain {entry.get('domain_hint', 'Unknown')}"
                )

        lines.extend(
            [
                "",
                "Next step",
                "A future parser pass will map known DBPF resource types to real Sims, relationships, lots, and repair targets.",
            ]
        )
        self.package_view.setPlainText("\n".join(lines))

    def _resource_entries_for_current_package(self) -> list[dict]:
        selected_path = self.package_source_select.currentData()
        if not isinstance(selected_path, str):
            return []
        package_info = self._lookup_package_info(selected_path)
        if not package_info:
            return []
        entries = package_info.get("index_entries_preview", [])
        if not isinstance(entries, list):
            return []
        return entries

    def _refresh_resource_type_options(self) -> None:
        entries = self._resource_entries_for_current_package()
        current_value = self.resource_type_select.currentData()
        self.resource_type_select.blockSignals(True)
        self.resource_type_select.clear()
        self.resource_type_select.addItem("All resource types", "__all__")

        seen: set[str] = set()
        for entry in entries:
            type_hex = str(entry.get("type_hex", "0x00000000"))
            if type_hex in seen:
                continue
            seen.add(type_hex)
            type_name = str(entry.get("type_name", "Unknown Resource"))
            self.resource_type_select.addItem(f"{type_name} ({type_hex})", type_hex)

        for index in range(self.resource_type_select.count()):
            if self.resource_type_select.itemData(index) == current_value:
                self.resource_type_select.setCurrentIndex(index)
                break
        else:
            self.resource_type_select.setCurrentIndex(0)
        self.resource_type_select.blockSignals(False)

    def _filtered_resource_entries(self) -> list[dict]:
        entries = self._resource_entries_for_current_package()
        selected_type = self.resource_type_select.currentData()
        if selected_type in (None, "__all__"):
            return entries
        return [entry for entry in entries if entry.get("type_hex") == selected_type]

    def _refresh_resource_browser(self) -> None:
        entries = self._filtered_resource_entries()
        selected_path = self.package_source_select.currentData()
        package_info = self._lookup_package_info(str(selected_path)) if isinstance(selected_path, str) else None
        if not entries:
            self.resource_summary_view.setPlainText(
                "No parsed resource entries available for the current package and filter.\n\n"
                "Right now the browser shows the parsed preview entries from the DBPF index."
            )
            self.resource_list.clear()
            self.resource_detail_view.setPlainText("No resource selected.")
            return

        summary_lines = [
            "Resource Browser",
            "",
            f"Visible entries: {len(entries)}",
            f"Current filter: {self.resource_type_select.currentText() or 'All resource types'}",
            f"Package role: {package_info.get('package_role', 'Unknown') if package_info else 'Unknown'}",
            "",
            "This is a preview of parsed DBPF index entries from the selected package.",
        ]
        self.resource_summary_view.setPlainText("\n".join(summary_lines))

        self.resource_list.blockSignals(True)
        self.resource_list.clear()
        for entry in entries:
            item = QListWidgetItem(
                f"{entry.get('type_short_name', 'UNK')} - "
                f"{entry.get('type_name', 'Unknown Resource')} [{entry.get('domain_hint', 'Unknown')}] | "
                f"{entry.get('instance_hex', '-')} | size {entry.get('file_size', 0)}"
            )
            item.setData(Qt.UserRole, entry)
            self.resource_list.addItem(item)
        self.resource_list.blockSignals(False)

        if self.resource_list.count() > 0:
            self.resource_list.setCurrentRow(0)
        else:
            self.resource_detail_view.setPlainText("No resource selected.")

    def _on_resource_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.resource_detail_view.setPlainText("No resource selected.")
            return

        entry = current.data(Qt.UserRole)
        if not isinstance(entry, dict):
            self.resource_detail_view.setPlainText("No resource selected.")
            return

        lines = [
            "Selected Resource",
            "",
            f"Short name: {entry.get('type_short_name', 'UNK')}",
            f"Type: {entry.get('type_name', 'Unknown Resource')}",
            f"Domain hint: {entry.get('domain_hint', 'Unknown')}",
            f"Type hex: {entry.get('type_hex', '-')}",
            f"Group: {entry.get('group_hex', '-')}",
            f"Instance: {entry.get('instance_hex', '-')}",
            f"Resource: {entry.get('resource_hex', '-')}",
            f"Offset: {entry.get('file_offset', 0)}",
            f"Size: {entry.get('file_size', 0)}",
            "",
            "Next step",
            "A future pass will decode payloads for known resource types and link them to Sims, relationships, lots, and repair actions.",
        ]
        self.resource_detail_view.setPlainText("\n".join(lines))

    def _refresh_file_inventory_view(self) -> None:
        savegame = self.session.current
        if savegame is None:
            self.file_inventory_view.setPlainText(
                "No save loaded yet.\n\nLoad a Sims 2 folder to inspect the neighborhood file inventory."
            )
            return

        household = self._current_household()
        if household is None:
            self.file_inventory_view.setPlainText("No neighborhood selected.")
            return

        inventory = household.metadata.get("file_inventory", {})
        if not isinstance(inventory, dict) or not inventory:
            self.file_inventory_view.setPlainText(
                "No file inventory is available for the selected neighborhood."
            )
            return

        lines = [
            "Neighborhood File Inventory",
            "",
            f"Neighborhood: {household.id}",
            f"Directory: {household.metadata.get('directory_path', '-')}",
            f"Total files: {inventory.get('total_file_count', 0)}",
            f"Total size: {inventory.get('total_size', 0)} bytes",
        ]

        role_profile = inventory.get("role_profile", [])
        if isinstance(role_profile, list) and role_profile:
            lines.extend(["", "File roles"])
            for entry in role_profile[:10]:
                lines.append(
                    f"{entry.get('role', 'Unknown')} x {entry.get('count', 0)} | "
                    f"{entry.get('total_size', 0)} bytes"
                )

        extension_profile = inventory.get("extension_profile", [])
        if isinstance(extension_profile, list) and extension_profile:
            lines.extend(["", "Extensions"])
            for entry in extension_profile[:10]:
                lines.append(
                    f"{entry.get('extension', '<none>')} x {entry.get('count', 0)} | "
                    f"{entry.get('total_size', 0)} bytes"
                )

        noteworthy_files = inventory.get("noteworthy_files", [])
        if isinstance(noteworthy_files, list) and noteworthy_files:
            lines.extend(["", "Noteworthy files"])
            for entry in noteworthy_files[:12]:
                lines.append(
                    f"{entry.get('role', 'Unknown')}: {entry.get('relative_path', '-')} | "
                    f"{entry.get('size', 0)} bytes"
                )

        global_roles = savegame.metadata.get("neighborhood_file_role_profile", [])
        if isinstance(global_roles, list) and global_roles:
            lines.extend(["", "Whole save overview"])
            for entry in global_roles[:8]:
                lines.append(f"{entry.get('role', 'Unknown')} x {entry.get('count', 0)}")

        self.file_inventory_view.setPlainText("\n".join(lines))

    def _clear_sim_editor(self) -> None:
        self.sim_name.clear()
        self.sim_age.setCurrentText("unknown")
        self.sim_aspiration.clear()
        self.sim_career.clear()
        self.sim_career_level.setValue(1)
        self.needs_table.setRowCount(0)
        self.skills_table.setRowCount(0)

    def _set_editing_enabled(self, enabled: bool) -> None:
        self.funds_spin.setEnabled(enabled)
        self.apply_household_button.setEnabled(enabled)
        self.sim_name.setEnabled(enabled)
        self.sim_age.setEnabled(enabled)
        self.sim_aspiration.setEnabled(enabled)
        self.sim_career.setEnabled(enabled)
        self.sim_career_level.setEnabled(enabled)
        self.needs_table.setEnabled(enabled)
        self.skills_table.setEnabled(enabled)
        self.apply_sim_button.setEnabled(enabled)

    def _find_household_by_id(self, household_id: str):
        savegame = self.session.current
        if savegame is None:
            return None
        return next((household for household in savegame.households if household.id == household_id), None)

    def _set_household_combo_by_id(self, household_id: str, *, emit_signal: bool = True) -> None:
        blocker = QSignalBlocker(self.household_select) if not emit_signal else None
        for index in range(self.household_select.count()):
            if self.household_select.itemData(index) == household_id:
                self.household_select.setCurrentIndex(index)
                del blocker
                return
        del blocker

    def _select_household_list_item(self, household_id: str, *, emit_signal: bool = True) -> None:
        blocker = QSignalBlocker(self.household_list) if not emit_signal else None
        for row in range(self.household_list.count()):
            item = self.household_list.item(row)
            if item.data(Qt.UserRole) == household_id:
                self.household_list.setCurrentRow(row)
                del blocker
                return
        del blocker

    def apply_household_changes(self) -> None:
        savegame = self.session.current
        household = self._current_household()
        if savegame is None or household is None:
            return

        household_id = household.id
        new_funds = int(self.funds_spin.value())

        def mutate(data: SaveGame) -> None:
            target = next((entry for entry in data.households if entry.id == household_id), None)
            if target is not None:
                target.funds = new_funds

        self.session.apply(f"Updated funds for household {household_id}", mutate)
        self._refresh_ui()
        self.statusBar().showMessage("Household funds updated")

    def apply_sim_changes(self) -> None:
        if not self._current_sim_id:
            return

        new_name = self.sim_name.text().strip() or "Unnamed Sim"
        new_age = self.sim_age.currentText().strip()
        new_aspiration = self.sim_aspiration.text().strip()
        new_career = self.sim_career.text().strip()
        new_career_level = int(self.sim_career_level.value())
        new_needs = self._table_to_dict(self.needs_table)
        new_skills = self._table_to_dict(self.skills_table)
        current_sim_id = self._current_sim_id

        def mutate(data: SaveGame) -> None:
            sim = next((entry for entry in data.sims if entry.id == current_sim_id), None)
            if sim is None:
                return
            sim.name = new_name
            sim.age_stage = new_age
            sim.aspiration = new_aspiration
            sim.career = new_career
            sim.career_level = new_career_level
            sim.needs = new_needs
            sim.skills = new_skills

        self.session.apply(f"Updated sim {current_sim_id}", mutate)
        self._refresh_ui()
        self.statusBar().showMessage("Sim changes applied")

    def create_backup(self) -> None:
        try:
            backup_path = self.session.create_backup()
        except ReadOnlySaveFormatError as exc:
            QMessageBox.information(self, "Read-only preview", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))
            return
        self.statusBar().showMessage(f"Backup created: {backup_path}")

    def save_file(self) -> None:
        if self.session.current is None:
            return

        try:
            self.session.create_backup()
            target = self.session.save()
        except ReadOnlySaveFormatError as exc:
            QMessageBox.information(self, "Read-only preview", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return

        self.statusBar().showMessage(f"Saved: {target}")

    def undo(self) -> None:
        self.session.undo()
        self._refresh_ui()
        self.statusBar().showMessage("Undo")

    def redo(self) -> None:
        self.session.redo()
        self._refresh_ui()
        self.statusBar().showMessage("Redo")

    def run_validation(self) -> None:
        issues = self.session.validate()
        if not issues:
            self.validation_view.setPlainText("No validation issues.")
            self.main_tabs.setCurrentWidget(self.validation_view)
            self.statusBar().showMessage("Validation complete: no issues")
            return

        lines = []
        for issue in issues:
            entity = f" ({issue.entity_id})" if issue.entity_id else ""
            lines.append(f"[{issue.severity.upper()}] {issue.code}{entity}: {issue.message}")

        self.validation_view.setPlainText("\n".join(lines))
        self.main_tabs.setCurrentWidget(self.validation_view)
        self.statusBar().showMessage(f"Validation complete: {len(issues)} issue(s)")
        self._refresh_header()
        self._refresh_issue_center()


def run_app() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1400, 860)
    window.show()
    return app.exec()
