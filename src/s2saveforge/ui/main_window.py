from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, QSignalBlocker, Qt, QThread, QTimer, QUrl, Signal
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
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from s2saveforge.core.models import Relationship, SaveGame
from s2saveforge.core.parser import ReadOnlySaveFormatError, UnsupportedSaveFormatError, extract_package_text_hints
from s2saveforge.core.service import SaveSession
from s2saveforge.core.validators import ValidationIssue, group_issues_by_entity, summarize_issues
from s2saveforge import __app_name__, __app_shortname__


class LoadWorker(QObject):
    progress = Signal(str, int, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, session: SaveSession, path: Path) -> None:
        super().__init__()
        self._session = session
        self._path = path

    def run(self) -> None:
        try:
            self._session.load(self._path, progress_callback=self.progress.emit)
        except Exception as exc:  # pragma: no cover - forwarded to UI thread
            self.failed.emit(str(exc))
            return
        self.finished.emit(str(self._path))


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
        self._current_lot_id = ""
        self._current_family_id = ""
        self._current_relationship_key = ""
        self._theme_name = "light"
        self._startup_prompt_pending = True
        self._load_thread: QThread | None = None
        self._load_worker: LoadWorker | None = None
        self._load_progress_dialog: QProgressDialog | None = None

        self._build_actions()
        self._build_layout()
        self._apply_window_style()

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")
        self._refresh_ui()

    def showEvent(self, event) -> None:  # pragma: no cover - UI lifecycle glue
        super().showEvent(event)
        if self._startup_prompt_pending:
            self._startup_prompt_pending = False
            QTimer.singleShot(0, self._prompt_for_startup_folder)

    def closeEvent(self, event) -> None:  # pragma: no cover - UI lifecycle glue
        if self._load_thread is not None:
            QMessageBox.information(self, "Loading in progress", "Please wait until the current load finishes.")
            event.ignore()
            return
        super().closeEvent(event)

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

        self.scope_title = QLabel("Neighborhoods", left_panel)
        self.scope_title.setObjectName("sectionTitle")
        left_layout.addWidget(self.scope_title)

        self.household_list = QListWidget(left_panel)
        self.household_list.currentItemChanged.connect(self._on_household_scope_changed)
        left_layout.addWidget(self.household_list, 1)

        self.lot_title = QLabel("Lots", left_panel)
        self.lot_title.setObjectName("sectionTitle")
        left_layout.addWidget(self.lot_title)

        self.lot_search = QLineEdit(left_panel)
        self.lot_search.setPlaceholderText("Filter by lot name or ID")
        self.lot_search.textChanged.connect(self._refresh_lot_list)
        left_layout.addWidget(self.lot_search)

        self.lot_list = QListWidget(left_panel)
        self.lot_list.currentItemChanged.connect(self._on_lot_selected)
        left_layout.addWidget(self.lot_list, 1)

        search_label = QLabel("Sims", left_panel)
        search_label.setObjectName("sectionTitle")
        left_layout.addWidget(search_label)

        self.sim_search = QLineEdit(left_panel)
        self.sim_search.setPlaceholderText("Filter by Sim name or ID")
        self.sim_search.textChanged.connect(self._refresh_sim_list)
        left_layout.addWidget(self.sim_search)

        self.sim_list = QListWidget(left_panel)
        self.sim_list.currentItemChanged.connect(self._on_sim_selected)
        left_layout.addWidget(self.sim_list, 2)

        self.family_title = QLabel("Families", left_panel)
        self.family_title.setObjectName("sectionTitle")
        left_layout.addWidget(self.family_title)

        self.family_search = QLineEdit(left_panel)
        self.family_search.setPlaceholderText("Filter families or households")
        self.family_search.textChanged.connect(self._refresh_family_list)
        left_layout.addWidget(self.family_search)

        self.family_list = QListWidget(left_panel)
        self.family_list.currentItemChanged.connect(self._on_family_selected)
        left_layout.addWidget(self.family_list, 1)

        right_panel = QTabWidget(splitter)
        right_panel.setDocumentMode(True)
        self.main_tabs = right_panel

        overview_page = QWidget(right_panel)
        self.overview_page = overview_page
        overview_layout = QVBoxLayout(overview_page)
        overview_layout.setContentsMargins(12, 12, 12, 12)
        overview_layout.setSpacing(10)

        self.overview_text = QTextBrowser(overview_page)
        self.overview_text.setOpenLinks(False)
        self.overview_text.anchorClicked.connect(self._on_visual_link_clicked)
        overview_layout.addWidget(self.overview_text)
        right_panel.addTab(overview_page, "Overview")

        family_page = QWidget(right_panel)
        self.family_page = family_page
        family_layout = QVBoxLayout(family_page)
        family_layout.setContentsMargins(12, 12, 12, 12)
        family_layout.setSpacing(10)
        self.family_detail_view = QTextBrowser(family_page)
        self.family_detail_view.setOpenLinks(False)
        self.family_detail_view.anchorClicked.connect(self._on_visual_link_clicked)
        family_layout.addWidget(self.family_detail_view, 1)
        right_panel.addTab(family_page, "Families")

        relationship_page = QWidget(right_panel)
        relationship_layout = QVBoxLayout(relationship_page)
        relationship_layout.setContentsMargins(12, 12, 12, 12)
        relationship_layout.setSpacing(10)

        relationship_filter_row = QHBoxLayout()
        relationship_filter_row.setSpacing(8)

        self.relationship_search = QLineEdit(relationship_page)
        self.relationship_search.setPlaceholderText("Filter relationships by Sim ID or name")
        self.relationship_search.textChanged.connect(self._refresh_relationship_view)
        relationship_filter_row.addWidget(self.relationship_search, 1)

        self.relationship_focus_select = QComboBox(relationship_page)
        self.relationship_focus_select.addItem("Current context", "context")
        self.relationship_focus_select.addItem("Selected Sim", "selected-sim")
        self.relationship_focus_select.addItem("Selected family", "selected-family")
        self.relationship_focus_select.currentIndexChanged.connect(self._refresh_relationship_view)
        relationship_filter_row.addWidget(self.relationship_focus_select)

        relationship_layout.addLayout(relationship_filter_row)

        self.relationship_summary_view = QTextBrowser(relationship_page)
        self.relationship_summary_view.setOpenLinks(False)
        self.relationship_summary_view.anchorClicked.connect(self._on_visual_link_clicked)
        relationship_layout.addWidget(self.relationship_summary_view, 1)

        self.relationship_list = QListWidget(relationship_page)
        self.relationship_list.currentItemChanged.connect(self._on_relationship_selected)
        relationship_layout.addWidget(self.relationship_list, 1)

        relationship_editor_box = QGroupBox("Selected Relationship", relationship_page)
        relationship_editor_form = QFormLayout(relationship_editor_box)

        self.relationship_sim_a_select = QComboBox(relationship_editor_box)
        self.relationship_sim_b_select = QComboBox(relationship_editor_box)

        self.relationship_daily_spin = QSpinBox(relationship_editor_box)
        self.relationship_daily_spin.setRange(-100, 100)

        self.relationship_lifetime_spin = QSpinBox(relationship_editor_box)
        self.relationship_lifetime_spin.setRange(-100, 100)

        self.relationship_flags_edit = QLineEdit(relationship_editor_box)
        self.relationship_flags_edit.setPlaceholderText("friend, crush, family")

        relationship_button_row = QHBoxLayout()
        self.apply_relationship_button = QPushButton("Apply Relationship", relationship_editor_box)
        self.apply_relationship_button.clicked.connect(self.apply_relationship_changes)
        relationship_button_row.addWidget(self.apply_relationship_button)

        self.add_relationship_button = QPushButton("Add Relationship", relationship_editor_box)
        self.add_relationship_button.clicked.connect(self.add_relationship)
        relationship_button_row.addWidget(self.add_relationship_button)

        self.remove_relationship_button = QPushButton("Remove Relationship", relationship_editor_box)
        self.remove_relationship_button.clicked.connect(self.remove_relationship)
        relationship_button_row.addWidget(self.remove_relationship_button)

        relationship_editor_form.addRow("Sim A", self.relationship_sim_a_select)
        relationship_editor_form.addRow("Sim B", self.relationship_sim_b_select)
        relationship_editor_form.addRow("Daily score", self.relationship_daily_spin)
        relationship_editor_form.addRow("Lifetime score", self.relationship_lifetime_spin)
        relationship_editor_form.addRow("Flags", self.relationship_flags_edit)
        relationship_editor_form.addRow("", relationship_button_row)

        relationship_layout.addWidget(relationship_editor_box)
        right_panel.addTab(relationship_page, "Relationships")

        sim_insights_page = QWidget(right_panel)
        sim_insights_layout = QVBoxLayout(sim_insights_page)
        sim_insights_layout.setContentsMargins(12, 12, 12, 12)
        sim_insights_layout.setSpacing(10)
        self.sim_insights_view = QTextEdit(sim_insights_page)
        self.sim_insights_view.setReadOnly(True)
        sim_insights_layout.addWidget(self.sim_insights_view, 1)
        right_panel.addTab(sim_insights_page, "Sim Insights")

        lots_page = QWidget(right_panel)
        self.lots_page = lots_page
        lots_layout = QVBoxLayout(lots_page)
        lots_layout.setContentsMargins(12, 12, 12, 12)
        lots_layout.setSpacing(10)

        lot_editor_box = QGroupBox("Selected Lot", lots_page)
        lot_editor_form = QFormLayout(lot_editor_box)

        self.lot_name_edit = QLineEdit(lot_editor_box)

        self.lot_zone_select = QComboBox(lot_editor_box)
        self.lot_zone_select.addItems(["unknown", "residential", "community", "apartment", "dorm", "vacation"])

        self.lot_occupancy_select = QComboBox(lot_editor_box)
        self.lot_occupancy_select.addItems(["unknown", "occupied", "vacant", "for_sale", "unlinked"])

        self.lot_household_select = QComboBox(lot_editor_box)

        self.apply_lot_button = QPushButton("Apply Lot Changes", lot_editor_box)
        self.apply_lot_button.clicked.connect(self.apply_lot_changes)

        lot_editor_form.addRow("Lot name", self.lot_name_edit)
        lot_editor_form.addRow("Zone", self.lot_zone_select)
        lot_editor_form.addRow("Occupancy", self.lot_occupancy_select)
        lot_editor_form.addRow("Linked household", self.lot_household_select)
        lot_editor_form.addRow("", self.apply_lot_button)
        lots_layout.addWidget(lot_editor_box)

        self.lot_detail_view = QTextBrowser(lots_page)
        self.lot_detail_view.setOpenLinks(False)
        self.lot_detail_view.anchorClicked.connect(self._on_visual_link_clicked)
        lots_layout.addWidget(self.lot_detail_view, 1)

        residents_label = QLabel("Detected Residents", lots_page)
        residents_label.setObjectName("sectionTitle")
        lots_layout.addWidget(residents_label)

        self.lot_resident_list = QListWidget(lots_page)
        self.lot_resident_list.currentItemChanged.connect(self._on_lot_resident_selected)
        lots_layout.addWidget(self.lot_resident_list, 1)

        object_filter_label = QLabel("Detected Objects", lots_page)
        object_filter_label.setObjectName("sectionTitle")
        lots_layout.addWidget(object_filter_label)

        self.lot_object_search = QLineEdit(lots_page)
        self.lot_object_search.setPlaceholderText("Filter detected object names")
        self.lot_object_search.textChanged.connect(self._refresh_lot_details)
        lots_layout.addWidget(self.lot_object_search)

        self.lot_object_list = QListWidget(lots_page)
        lots_layout.addWidget(self.lot_object_list, 2)

        right_panel.addTab(lots_page, "Lots")

        editor_page = QWidget(right_panel)
        self.editor_page = editor_page
        editor_layout = QVBoxLayout(editor_page)
        editor_layout.setContentsMargins(12, 12, 12, 12)
        editor_layout.setSpacing(12)

        household_box = QGroupBox("Selected Household", editor_page)
        household_form = QFormLayout(household_box)
        self.household_select = QComboBox(household_box)
        self.household_select.currentIndexChanged.connect(self._on_household_selected)

        self.household_name_edit = QLineEdit(household_box)

        self.funds_spin = QSpinBox(household_box)
        self.funds_spin.setRange(-9_999_999, 999_999_999)

        self.apply_household_button = QPushButton("Apply Household Changes", household_box)
        self.apply_household_button.clicked.connect(self.apply_household_changes)

        household_form.addRow("Household", self.household_select)
        household_form.addRow("Name", self.household_name_edit)
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

        self.sim_wants_edit = QTextEdit(sim_box)
        self.sim_wants_edit.setPlaceholderText("One wish, fear, or aspiration hint per line")
        self.sim_wants_edit.setMaximumHeight(100)
        sim_form.addRow("Wishes / fears", self.sim_wants_edit)

        self.sim_clothing_edit = QTextEdit(sim_box)
        self.sim_clothing_edit.setPlaceholderText("One clothing or appearance hint per line")
        self.sim_clothing_edit.setMaximumHeight(100)
        sim_form.addRow("Clothing / look", self.sim_clothing_edit)

        self.sim_notes_edit = QTextEdit(sim_box)
        self.sim_notes_edit.setPlaceholderText("Freeform notes for this Sim")
        self.sim_notes_edit.setMaximumHeight(100)
        sim_form.addRow("Notes", self.sim_notes_edit)

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
            QListWidget, QLineEdit, QComboBox, QSpinBox, QTextEdit, QTextBrowser, QTableWidget {
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

    def _ui_theme_value(self, key: str) -> str:
        return self.THEMES[self._theme_name][key]

    def _render_html_view(self, title: str, sections: list[str]) -> str:
        return (
            "<html><body style=\""
            f"font-family:'Segoe UI'; color:{self._ui_theme_value('primary_text')}; "
            f"background:{self._ui_theme_value('field_bg')}; margin:0; padding:12px;"
            "\">"
            f"<div style=\"font-size:20px; font-weight:700; margin-bottom:12px;\">{escape(title)}</div>"
            + "".join(sections)
            + "</body></html>"
        )

    def _render_info_card(self, title: str, body: str) -> str:
        return (
            "<div style=\""
            f"background:{self._ui_theme_value('surface_bg')}; "
            f"border:1px solid {self._ui_theme_value('surface_border')}; "
            "border-radius:12px; padding:12px; margin-bottom:10px;"
            "\">"
            f"<div style=\"font-size:14px; font-weight:700; margin-bottom:8px; color:{self._ui_theme_value('section_text')};\">"
            f"{escape(title)}"
            "</div>"
            f"{body}"
            "</div>"
        )

    def _render_stat_grid(self, stats: list[tuple[str, str]]) -> str:
        tiles: list[str] = []
        for label, value in stats:
            tiles.append(
                "<div style=\"display:inline-block; min-width:120px; margin:0 8px 8px 0; padding:10px 12px;"
                f" background:{self._ui_theme_value('tab_bg')}; border-radius:10px;\">"
                f"<div style=\"font-size:11px; color:{self._ui_theme_value('muted_text')}; text-transform:uppercase;\">{escape(label)}</div>"
                f"<div style=\"font-size:18px; font-weight:700;\">{escape(value)}</div>"
                "</div>"
            )
        return "".join(tiles)

    def _render_kv_rows(self, rows: list[tuple[str, str]]) -> str:
        lines: list[str] = []
        for label, value in rows:
            lines.append(
                f"<div style=\"margin-bottom:6px;\"><span style=\"color:{self._ui_theme_value('muted_text')}; font-weight:600;\">{escape(label)}:</span> {escape(value)}</div>"
            )
        return "".join(lines)

    def _render_tag_list(self, tags: list[str], empty_text: str) -> str:
        filtered = [tag for tag in tags if tag]
        if not filtered:
            return f"<div style=\"color:{self._ui_theme_value('muted_text')};\">{escape(empty_text)}</div>"
        pills = []
        for tag in filtered:
            pills.append(
                "<span style=\"display:inline-block; margin:0 6px 6px 0; padding:4px 10px; border-radius:999px;"
                f" background:{self._ui_theme_value('selection_bg')}; color:{self._ui_theme_value('selection_text')};\">{escape(tag)}</span>"
            )
        return "".join(pills)

    def _render_badge(self, label: str, background: str, foreground: str) -> str:
        return (
            "<span style=\"display:inline-block; margin:0 6px 6px 0; padding:4px 10px; border-radius:999px;"
            f" background:{background}; color:{foreground}; font-size:11px; font-weight:700;\">{escape(label)}</span>"
        )

    def _age_badge(self, age_stage: str) -> str:
        palette = {
            "baby": ("#f6d5cf", "#4f241b"),
            "toddler": ("#f0d8a8", "#51340b"),
            "child": ("#d4ead1", "#1e4b1f"),
            "teen": ("#d4e3f5", "#183b63"),
            "adult": ("#d9d6f5", "#30205a"),
            "elder": ("#ded7cf", "#43362d"),
        }
        background, foreground = palette.get(age_stage, (self._ui_theme_value("tab_bg"), self._ui_theme_value("primary_text")))
        return self._render_badge(age_stage.title() if age_stage else "Unknown", background, foreground)

    def _status_badge(self, label: str, tone: str) -> str:
        palette = {
            "career": ("#cfe8dc", "#184c34"),
            "funds": ("#f4e3b5", "#5a4105"),
            "relationship": ("#f6d0dd", "#6a2240"),
            "lot": ("#d8dff6", "#243a70"),
            "neutral": (self._ui_theme_value("tab_bg"), self._ui_theme_value("primary_text")),
        }
        background, foreground = palette.get(tone, palette["neutral"])
        return self._render_badge(label, background, foreground)

    def _avatar_initials(self, name: str) -> str:
        parts = [part[:1].upper() for part in name.split() if part[:1]]
        initials = "".join(parts[:2])
        return initials or "??"

    def _render_avatar(self, name: str) -> str:
        return (
            "<div style=\"display:inline-flex; width:52px; height:52px; border-radius:16px; align-items:center; justify-content:center;"
            f" background:{self._ui_theme_value('selection_bg')}; color:{self._ui_theme_value('selection_text')};"
            " font-size:18px; font-weight:800; margin-right:12px; vertical-align:top;\">"
            f"{escape(self._avatar_initials(name))}"
            "</div>"
        )

    def _render_click_card(
        self,
        title: str,
        subtitle: str,
        href: str,
        badges: list[str],
        details: list[tuple[str, str]],
    ) -> str:
        detail_html = "".join(
            f"<div style=\"margin-bottom:4px; color:{self._ui_theme_value('muted_text')};\"><strong>{escape(label)}:</strong> {escape(value)}</div>"
            for label, value in details
        )
        return (
            f"<a href=\"{escape(href)}\" style=\"text-decoration:none; color:inherit;\">"
            "<div style=\"display:inline-block; width:290px; min-height:152px; vertical-align:top;"
            f" background:{self._ui_theme_value('surface_bg')}; border:1px solid {self._ui_theme_value('surface_border')};"
            " border-radius:14px; padding:14px; margin:0 10px 10px 0;\">"
            + self._render_avatar(title)
            + "<div style=\"display:inline-block; width:200px; vertical-align:top;\">"
            + f"<div style=\"font-size:15px; font-weight:800; margin-bottom:4px;\">{escape(title)}</div>"
            + f"<div style=\"font-size:12px; color:{self._ui_theme_value('muted_text')}; margin-bottom:8px;\">{escape(subtitle)}</div>"
            + "".join(badges)
            + "<div style=\"margin-top:8px;\">"
            + detail_html
            + "</div></div></div></a>"
        )

    def _visible_family_rows(self, savegame: SaveGame) -> list[tuple[str, str]]:
        current_neighborhood_id = self._current_household_filter_id
        search_term = self.family_search.text().strip().lower()
        lots = [lot for lot in savegame.lots if lot.neighborhood_id == current_neighborhood_id]
        household = self._find_household_by_id(current_neighborhood_id)
        rows: list[tuple[str, str]] = []
        if household is not None:
            rows.append((household.id, f"{household.name} ({household.id})"))
        for lot in lots:
            if lot.household_id:
                rows.append((lot.household_id, f"{lot.household_id} linked to {lot.name}"))

        seen_ids: set[str] = set()
        visible_rows: list[tuple[str, str]] = []
        for family_id, label in rows:
            if family_id in seen_ids:
                continue
            seen_ids.add(family_id)
            if search_term and search_term not in label.lower():
                continue
            visible_rows.append((family_id, label))
        return visible_rows

    def _visible_sims(self, savegame: SaveGame) -> list:
        search_term = self.sim_search.text().strip().lower()
        family_member_ids = self._selected_family_member_ids()
        filtered_sims = []
        for sim in savegame.sims:
            if self._current_household_filter_id and sim.household_id != self._current_household_filter_id:
                continue
            if family_member_ids and sim.id not in family_member_ids:
                continue
            self._ensure_sim_name_hint(sim)
            haystack = f"{sim.name} {sim.id}".lower()
            if search_term and search_term not in haystack:
                continue
            filtered_sims.append(sim)
        return filtered_sims

    def _relationship_count_for_sim(self, savegame: SaveGame, sim_id: str) -> int:
        return sum(1 for rel in savegame.relationships if rel.sim_a == sim_id or rel.sim_b == sim_id)

    def _render_family_cards(self, savegame: SaveGame) -> str:
        cards: list[str] = []
        for family_id, _label in self._visible_family_rows(savegame)[:8]:
            household = self._find_household_by_id(family_id)
            if household is None:
                continue
            linked_lots = [lot for lot in savegame.lots if lot.household_id == household.id]
            cards.append(
                self._render_click_card(
                    household.name,
                    household.id,
                    f"family:{household.id}",
                    [
                        self._status_badge(f"Funds {household.funds}", "funds"),
                        self._status_badge(f"Lots {len(linked_lots)}", "lot"),
                    ],
                    [
                        ("Members", str(len(household.members))),
                        ("Household", household.id),
                        ("Lot state", ", ".join(lot.occupancy for lot in linked_lots[:2]) or "unlinked"),
                    ],
                )
            )
        return "".join(cards) or self._render_kv_rows([("Families", "No family cards available in the current scope")])

    def _render_sim_cards(self, savegame: SaveGame, sims: list, limit: int = 8) -> str:
        cards: list[str] = []
        for sim in sims[:limit]:
            relationship_count = self._relationship_count_for_sim(savegame, sim.id)
            cards.append(
                self._render_click_card(
                    sim.name,
                    sim.id,
                    f"sim:{sim.id}",
                    [
                        self._age_badge(sim.age_stage),
                        self._status_badge(sim.career or "No career", "career"),
                        self._status_badge(f"Relations {relationship_count}", "relationship"),
                    ],
                    [
                        ("Aspiration", sim.aspiration or "-"),
                        ("Career level", str(sim.career_level)),
                        ("Needs tracked", str(len(sim.needs))),
                    ],
                )
            )
        return "".join(cards) or self._render_kv_rows([("Sims", "No Sims available in the current scope")])

    def _render_lot_cards(self, lots: list) -> str:
        cards: list[str] = []
        for lot in lots[:8]:
            cards.append(
                self._render_click_card(
                    lot.name,
                    lot.id,
                    f"lot:{lot.id}",
                    [
                        self._status_badge(lot.zone_type or "unknown", "lot"),
                        self._status_badge(lot.occupancy or "unknown", "neutral"),
                    ],
                    [
                        ("Neighborhood", lot.neighborhood_id),
                        ("Linked household", lot.household_id or "-"),
                        ("Package", Path(lot.package_path).name if lot.package_path else "-"),
                    ],
                )
            )
        return "".join(cards) or self._render_kv_rows([("Lots", "No lots available in the current scope")])

    def _render_relationship_cards(self, relationships: list[Relationship]) -> str:
        cards: list[str] = []
        for rel in relationships[:12]:
            sim_a_label = self._sim_display_label(rel.sim_a)
            sim_b_label = self._sim_display_label(rel.sim_b)
            flags = ", ".join(rel.flags) if rel.flags else "no flags"
            body = (
                self._status_badge(f"Daily {rel.score_daily}", "relationship")
                + self._status_badge(f"Lifetime {rel.score_lifetime}", "relationship")
                + self._render_kv_rows(
                    [
                        ("Sim A", sim_a_label),
                        ("Sim B", sim_b_label),
                        ("Flags", flags),
                    ]
                )
                + "<div style=\"margin-top:8px;\">"
                + f"<a href=\"sim:{escape(rel.sim_a)}\" style=\"margin-right:10px; color:{self._ui_theme_value('primary_text')}; font-weight:700;\">Open {escape(sim_a_label)}</a>"
                + f"<a href=\"sim:{escape(rel.sim_b)}\" style=\"color:{self._ui_theme_value('primary_text')}; font-weight:700;\">Open {escape(sim_b_label)}</a>"
                + "</div>"
            )
            cards.append(self._render_info_card(f"{sim_a_label} ↔ {sim_b_label}", body))
        return "".join(cards) or self._render_kv_rows([("Relationships", "No visible relationships in the current scope")])

    def _render_resident_links(self, resident_names: list[str], resident_sim_ids: list[str]) -> str:
        links: list[str] = []
        for index, resident_name in enumerate(resident_names[:12]):
            sim_id = resident_sim_ids[index] if index < len(resident_sim_ids) else ""
            if sim_id:
                links.append(
                    f"<a href=\"sim:{escape(sim_id)}\" style=\"text-decoration:none;\">{self._render_badge(resident_name, self._ui_theme_value('selection_bg'), self._ui_theme_value('selection_text'))}</a>"
                )
            else:
                links.append(self._render_badge(resident_name, self._ui_theme_value('tab_bg'), self._ui_theme_value('primary_text')))
        return "".join(links) or self._render_kv_rows([("Residents", "No resident candidates detected yet")])

    def _on_visual_link_clicked(self, url: QUrl) -> None:
        self._handle_visual_navigation(url.toString())

    def _handle_visual_navigation(self, target: str) -> None:
        if ":" not in target:
            return
        kind, entity_id = target.split(":", 1)
        savegame = self.session.current
        if savegame is None or not entity_id:
            return

        if kind == "family":
            household = self._find_household_by_id(entity_id)
            if household is None:
                return
            self._current_household_filter_id = household.id
            self._current_family_id = household.id
            self._set_household_combo_by_id(household.id, emit_signal=False)
            self._select_household_list_item(household.id, emit_signal=False)
            self._refresh_scope_views()
            self._select_family_list_item(household.id, emit_signal=False)
            self.main_tabs.setCurrentWidget(self.family_page)
            return

        if kind == "sim":
            sim = next((entry for entry in savegame.sims if entry.id == entity_id), None)
            if sim is None:
                return
            self._current_household_filter_id = sim.household_id
            self._current_family_id = sim.household_id
            self._set_household_combo_by_id(sim.household_id, emit_signal=False)
            self._select_household_list_item(sim.household_id, emit_signal=False)
            self._refresh_scope_views()
            self._select_family_list_item(sim.household_id, emit_signal=False)
            self._select_sim_list_item(sim.id, emit_signal=False)
            self._on_sim_selected(self.sim_list.currentItem(), None)
            self.main_tabs.setCurrentWidget(self.editor_page)
            return

        if kind == "lot":
            lot = self._find_lot_by_id(entity_id)
            if lot is None:
                return
            self._current_household_filter_id = lot.neighborhood_id
            self._current_family_id = lot.household_id or lot.neighborhood_id
            self._set_household_combo_by_id(lot.neighborhood_id, emit_signal=False)
            self._select_household_list_item(lot.neighborhood_id, emit_signal=False)
            self._refresh_scope_views()
            self._select_family_list_item(self._current_family_id, emit_signal=False)
            self._select_lot_list_item(lot.id, emit_signal=False)
            self._on_lot_selected(self.lot_list.currentItem(), None)
            self.main_tabs.setCurrentWidget(self.lots_page)

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
            self._current_family_id = ""
            self._refresh_scope_views()
            return

        household_id = current.data(Qt.UserRole)
        if not isinstance(household_id, str):
            return

        self._current_household_filter_id = household_id
        self._current_family_id = household_id
        household = self._find_household_by_id(household_id)
        if household is not None:
            self.household_name_edit.setText(household.name)
            self.funds_spin.setValue(household.funds)
        self._set_household_combo_by_id(household_id, emit_signal=False)
        self._refresh_scope_views()

    def _on_household_selected(self, index: int) -> None:
        savegame = self.session.current
        if savegame is None or index < 0 or index >= len(savegame.households):
            return

        household = savegame.households[index]
        self.household_name_edit.setText(household.name)
        self.funds_spin.setValue(household.funds)
        self._current_household_filter_id = household.id
        self._current_family_id = household.id
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
        text_hints = sim.metadata.get("text_hints", {}) if isinstance(sim.metadata, dict) else {}
        edited_wants = sim.metadata.get("edited_wants", []) if isinstance(sim.metadata, dict) else []
        edited_clothing = sim.metadata.get("edited_clothing", []) if isinstance(sim.metadata, dict) else []
        edited_notes = sim.metadata.get("edited_notes", "") if isinstance(sim.metadata, dict) else ""
        want_lines = edited_wants or (text_hints.get("want_candidates", []) if isinstance(text_hints, dict) else [])
        clothing_lines = edited_clothing or (text_hints.get("clothing_candidates", []) if isinstance(text_hints, dict) else [])
        self.sim_wants_edit.setPlainText("\n".join(str(value).strip() for value in want_lines if str(value).strip()))
        self.sim_clothing_edit.setPlainText("\n".join(str(value).strip() for value in clothing_lines if str(value).strip()))
        self.sim_notes_edit.setPlainText(str(edited_notes).strip())
        self._fill_table(self.needs_table, sim.needs)
        self._fill_table(self.skills_table, sim.skills)
        self._current_household_filter_id = sim.household_id
        self._current_family_id = sim.household_id
        household = self._find_household_by_id(sim.household_id)
        if household is not None:
            self.household_name_edit.setText(household.name)
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
        if self._load_thread is not None:
            QMessageBox.information(self, "Loading in progress", "Please wait for the current load to finish.")
            return

        progress = QProgressDialog("Loading savegame...", None, 0, 0, self)
        progress.setWindowTitle("Loading Savegame")
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        progress.show()

        self._load_progress_dialog = progress
        self.statusBar().showMessage("Loading savegame...")
        self.centralWidget().setEnabled(False)

        self._load_thread = QThread(self)
        self._load_worker = LoadWorker(self.session, path)
        self._load_worker.moveToThread(self._load_thread)

        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.progress.connect(self._on_load_progress)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.failed.connect(self._on_load_failed)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.failed.connect(self._load_thread.quit)
        self._load_thread.finished.connect(self._cleanup_load_worker)

        self._load_thread.start()

    def _on_load_progress(self, message: str, current: int, total: int) -> None:
        if self._load_progress_dialog is None:
            return
        maximum = max(total, 1)
        self._load_progress_dialog.setMaximum(maximum)
        self._load_progress_dialog.setValue(min(current, maximum))
        self._load_progress_dialog.setLabelText(message)

    def _on_load_finished(self, path_text: str) -> None:
        if self._load_progress_dialog is not None:
            self._load_progress_dialog.setValue(self._load_progress_dialog.maximum())
            self._load_progress_dialog.close()
            self._load_progress_dialog = None

        path = Path(path_text)
        self._current_sim_id = ""
        self._current_household_filter_id = ""
        self._current_lot_id = ""
        self._refresh_ui()
        self.centralWidget().setEnabled(True)
        if path.is_dir():
            self.statusBar().showMessage(f"Loaded folder preview: {path}")
        else:
            self.statusBar().showMessage(f"Loaded: {path}")

    def _on_load_failed(self, error_text: str) -> None:
        if self._load_progress_dialog is not None:
            self._load_progress_dialog.close()
            self._load_progress_dialog = None
        self.centralWidget().setEnabled(True)

        if error_text.startswith("Unsupported file format") or "No Sims 2 neighborhood folders" in error_text:
            QMessageBox.warning(self, "Unsupported format", error_text)
        else:
            QMessageBox.critical(self, "Load failed", error_text)

    def _cleanup_load_worker(self) -> None:
        if self._load_worker is not None:
            self._load_worker.deleteLater()
            self._load_worker = None
        if self._load_thread is not None:
            self._load_thread.deleteLater()
            self._load_thread = None
        self.centralWidget().setEnabled(True)

    def _prompt_for_startup_folder(self) -> None:
        if self.session.current is not None:
            return
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Choose The Sims 2 save folder",
            str(Path.cwd()),
        )
        if folder_path:
            self._load_path(Path(folder_path))

    def _refresh_ui(self) -> None:
        savegame = self.session.current
        is_preview = self._is_preview_mode()

        self.household_list.blockSignals(True)
        self.household_select.blockSignals(True)
        self.lot_list.blockSignals(True)
        self.sim_list.blockSignals(True)
        self.family_list.blockSignals(True)

        self.household_list.clear()
        self.household_select.clear()
        self.lot_list.clear()
        self.sim_list.clear()
        self.family_list.clear()

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
            self._clear_lot_editor()
            self._set_editing_enabled(False)
            self._refresh_history_view()
            self._refresh_overview()
            self._refresh_lot_details()
            self._refresh_family_view()
            self._refresh_relationship_view()
            self._refresh_sim_insights()
            self._refresh_issue_center()
            self._refresh_package_source_options()
            self._refresh_package_inspector()
            self._refresh_resource_type_options()
            self._refresh_resource_browser()
            self._refresh_file_inventory_view()
            self.household_list.blockSignals(False)
            self.household_select.blockSignals(False)
            self.lot_list.blockSignals(False)
            self.sim_list.blockSignals(False)
            self.family_list.blockSignals(False)
            return

        self.scope_title.setText("Neighborhoods" if is_preview else "Households")
        self.lot_title.setText("Lots")
        self.family_title.setText("Families")
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
        self._refresh_lot_list(select_current=False)
        self._refresh_sim_list(select_current=False)
        self._set_editing_enabled(True)
        self._refresh_header()
        self._refresh_history_view()
        self._refresh_overview()
        self._refresh_lot_details()
        self._refresh_family_list()
        self._refresh_family_view()
        self._refresh_relationship_view()
        self._refresh_sim_insights()
        self._refresh_issue_scope_options()
        self._refresh_issue_center()
        self._refresh_package_source_options()
        self._refresh_package_inspector()
        self._refresh_resource_type_options()
        self._refresh_resource_browser()
        self._refresh_file_inventory_view()

        self.household_list.blockSignals(False)
        self.household_select.blockSignals(False)
        self.lot_list.blockSignals(False)
        self.sim_list.blockSignals(False)
        self.family_list.blockSignals(False)

    def _refresh_header(self) -> None:
        savegame = self.session.current
        if savegame is None:
            return

        source = str(self.session.source_path) if self.session.source_path else "-"
        if self._is_preview_mode():
            self.banner_label.setText(
                f"Folder preview loaded in {__app_shortname__}. You can inspect neighborhoods, lots, Sims, and stage edits in-session now; writeback to package files comes next."
            )
            self.mode_label.setText("Mode: Folder preview (staged edits, no writeback yet)")
        else:
            self.banner_label.setText(
                f"Editable save loaded in {__app_shortname__}. Use the left side to narrow scope, then change household or Sim data in the editor."
            )
            self.mode_label.setText("Mode: Editable MVP save")

        self.source_label.setText(f"Source: {source}")
        self.counts_label.setText(
            "Neighborhoods: "
            f"{len(savegame.neighborhoods)} | Lots: {len(savegame.lots)} | Households: {len(savegame.households)} | Sims: {len(savegame.sims)} | Relationships: {len(savegame.relationships)}"
        )
        summary = summarize_issues(self.session.validate())
        self.health_label.setText(
            f"Health: {summary['error']} errors | {summary['warning']} warnings | {summary['info']} info"
        )

    def _refresh_scope_views(self) -> None:
        self._refresh_lot_list()
        self._refresh_sim_list()
        self._refresh_family_list()
        self._refresh_detail_views()

    def _refresh_detail_views(self) -> None:
        self._refresh_overview()
        self._refresh_lot_details()
        self._refresh_family_view()
        self._refresh_relationship_view()
        self._refresh_sim_insights()
        self._refresh_package_source_options()
        self._refresh_package_inspector()
        self._refresh_resource_type_options()
        self._refresh_resource_browser()
        self._refresh_file_inventory_view()

    def _refresh_lot_list(self, *, select_current: bool = True) -> None:
        savegame = self.session.current
        blocker = QSignalBlocker(self.lot_list)
        self.lot_list.clear()

        if savegame is None:
            del blocker
            return

        filtered_lots = [
            lot
            for lot in savegame.lots
            if not self._current_household_filter_id or lot.neighborhood_id == self._current_household_filter_id
        ]
        search_term = self.lot_search.text().strip().lower()
        if search_term:
            filtered_lots = [
                lot for lot in filtered_lots if search_term in f"{lot.name} {lot.id}".lower()
            ]

        for lot in filtered_lots:
            label = f"{lot.name} ({lot.id})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, lot.id)
            self.lot_list.addItem(item)

        if not filtered_lots:
            self._current_lot_id = ""
            del blocker
            return

        target_id = self._current_lot_id if select_current else filtered_lots[0].id
        target_row = 0
        for row in range(self.lot_list.count()):
            item = self.lot_list.item(row)
            if item.data(Qt.UserRole) == target_id:
                target_row = row
                break

        self.lot_list.setCurrentRow(target_row)
        current_item = self.lot_list.currentItem()
        del blocker
        self._on_lot_selected(current_item, None)

    def _refresh_family_list(self) -> None:
        savegame = self.session.current
        blocker = QSignalBlocker(self.family_list)
        self.family_list.clear()
        if savegame is None:
            del blocker
            return

        visible_rows = self._visible_family_rows(savegame)

        if visible_rows and not self._current_family_id:
            self._current_family_id = visible_rows[0][0]

        for family_id, label in visible_rows:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, family_id)
            self.family_list.addItem(item)

        for row in range(self.family_list.count()):
            item = self.family_list.item(row)
            if item.data(Qt.UserRole) == self._current_family_id:
                self.family_list.setCurrentRow(row)
                break
        del blocker

    def _on_family_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._current_family_id = ""
            self._refresh_detail_views()
            self._current_relationship_key = ""
            return

        family_id = current.data(Qt.UserRole)
        if not isinstance(family_id, str):
            return

        self._current_family_id = family_id
        household = self._find_household_by_id(family_id)
        if household is not None:
            self.household_name_edit.setText(household.name)
            self.funds_spin.setValue(household.funds)
            self._set_household_combo_by_id(household.id, emit_signal=False)
        linked_lot = self._find_first_lot_for_family(family_id)
        if linked_lot is not None:
            self._current_lot_id = linked_lot.id
        self._refresh_scope_views()

    def _on_lot_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._current_lot_id = ""
            self._refresh_detail_views()
            return

        lot_id = current.data(Qt.UserRole)
        if not isinstance(lot_id, str):
            return

        self._current_lot_id = lot_id
        self._refresh_detail_views()

    def _current_lot(self):
        savegame = self.session.current
        if savegame is None or not self._current_lot_id:
            return None
        return next((lot for lot in savegame.lots if lot.id == self._current_lot_id), None)

    def _refresh_sim_list(self, *, select_current: bool = True) -> None:
        savegame = self.session.current
        blocker = QSignalBlocker(self.sim_list)
        self.sim_list.clear()

        if savegame is None:
            del blocker
            return

        filtered_sims = self._visible_sims(savegame)

        for sim in filtered_sims:
            summary_bits = []
            if sim.age_stage and sim.age_stage != "unknown":
                summary_bits.append(sim.age_stage)
            if sim.aspiration:
                summary_bits.append(sim.aspiration)
            label = f"{sim.name} ({sim.id})"
            if summary_bits:
                label += " | " + " | ".join(summary_bits[:2])
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
            self.overview_text.setHtml(
                self._render_html_view(
                    "Workspace Overview",
                    [
                        self._render_info_card(
                            "Start Here",
                            self._render_kv_rows(
                                [
                                    ("State", "No save loaded yet"),
                                    ("Next step", "Use Open Folder for a real Sims 2 save or Load Demo for the editable MVP file"),
                                ]
                            ),
                        )
                    ],
                )
            )
            return

        household = self._current_household()
        lot = self._current_lot()
        selected_sim = next((sim for sim in savegame.sims if sim.id == self._current_sim_id), None)
        mode_line = "Folder preview (staged edits, no writeback yet)" if self._is_preview_mode() else "Editable MVP save"
        issues = self.session.validate()
        issue_total = len(issues)

        sections = [
            self._render_info_card(
                "Save Summary",
                self._render_stat_grid(
                    [
                        ("Neighborhoods", str(len(savegame.neighborhoods))),
                        ("Lots", str(len(savegame.lots))),
                        ("Households", str(len(savegame.households))),
                        ("Sims", str(len(savegame.sims))),
                        ("Relationships", str(len(savegame.relationships))),
                        ("Issues", str(issue_total)),
                    ]
                )
                + self._render_kv_rows(
                    [
                        ("Mode", mode_line),
                        ("Source", str(self.session.source_path or "-")),
                    ]
                ),
            )
        ]
        visible_sims = self._visible_sims(savegame)
        visible_lots = [
            lot for lot in savegame.lots if not self._current_household_filter_id or lot.neighborhood_id == self._current_household_filter_id
        ]

        if savegame.metadata:
            if savegame.metadata.get("source_kind") == "folder_preview":
                preview_rows = [
                    ("Neighborhood root", str(savegame.metadata.get("neighborhoods_root", "-"))),
                    ("Neighborhood count", str(savegame.metadata.get("neighborhood_count", 0))),
                    ("Lot count", str(savegame.metadata.get("lot_count", 0))),
                    (
                        "NeighborhoodManager.package",
                        "present" if savegame.metadata.get("neighborhood_manager_exists") else "missing",
                    ),
                    ("Story entries found", str(savegame.metadata.get("total_story_entries", 0))),
                ]
                package_role_profile = savegame.metadata.get("package_role_profile", [])
                if isinstance(package_role_profile, list) and package_role_profile:
                    preview_rows.extend(
                        [
                            (str(entry.get("role", "Unknown")), f"x {entry.get('count', 0)}")
                            for entry in package_role_profile[:6]
                        ]
                    )
                simpe_reference = savegame.metadata.get("simpe_reference", {})
                if isinstance(simpe_reference, dict) and simpe_reference.get("loaded"):
                    preview_rows.extend(
                        [
                            ("SimPE source", str(simpe_reference.get("source_path", "-"))),
                            (
                                "Known hood kinds",
                                ", ".join(simpe_reference.get("known_hood_kinds", []) or ["-"]),
                            ),
                        ]
                    )
                sections.append(self._render_info_card("Folder Preview", self._render_kv_rows(preview_rows)))

        sections.append(self._render_info_card("Families", self._render_family_cards(savegame)))
        sections.append(self._render_info_card("Visible Sims", self._render_sim_cards(savegame, visible_sims, limit=6)))
        sections.append(self._render_info_card("Visible Lots", self._render_lot_cards(visible_lots)))

        if household is not None:
            scope_label = "Neighborhood" if self._is_preview_mode() else "Household"
            household_rows = [
                (f"Current {scope_label}", household.name),
                ("ID", household.id),
                ("Members", str(len(household.members))),
                ("Funds", str(household.funds)),
            ]
            if household.metadata:
                household_rows.extend(
                    [
                        ("Directory", str(household.metadata.get("directory_path", "-"))),
                        (
                            "Main package",
                            "present" if household.metadata.get("main_package_exists", True) else "missing",
                        ),
                        (
                            "Main package role",
                            str(household.metadata.get("main_package_info", {}).get("package_role", "-")),
                        ),
                        (
                            "Characters dir",
                            "present" if household.metadata.get("characters_dir_exists", True) else "missing",
                        ),
                        ("Lots dir", "present" if household.metadata.get("lots_dir_exists", True) else "missing"),
                        ("Character packages", str(household.metadata.get("character_count", len(household.members)))),
                        ("Lot packages", str(household.metadata.get("lot_count", 0))),
                    ]
                )
            sections.append(
                self._render_info_card(
                    f"Selected {scope_label}",
                    self._render_kv_rows(household_rows),
                )
            )

        if lot is not None:
            text_hints = lot.metadata.get("text_hints", {}) if isinstance(lot.metadata, dict) else {}
            object_names = text_hints.get("object_name_candidates", []) if isinstance(text_hints, dict) else []
            resident_names = text_hints.get("resident_name_candidates", []) if isinstance(text_hints, dict) else []
            sections.append(
                self._render_info_card(
                    "Current Lot",
                    self._render_kv_rows(
                        [
                            ("Lot", lot.name),
                            ("Lot ID", lot.id),
                            ("Neighborhood", lot.neighborhood_id),
                            ("Zone", lot.zone_type),
                            ("Occupancy", lot.occupancy),
                            ("Linked household", lot.household_id or "-"),
                            ("Resident name candidates", str(len(resident_names))),
                            ("Object name candidates", str(len(object_names))),
                        ]
                    ),
                )
            )

        if selected_sim is not None:
            sim_rows = [
                ("Current Sim", selected_sim.name),
                ("Sim ID", selected_sim.id),
                ("Age", selected_sim.age_stage),
                ("Aspiration", selected_sim.aspiration or "-"),
                ("Career", selected_sim.career or "-"),
                ("Needs tracked", str(len(selected_sim.needs))),
                ("Skills tracked", str(len(selected_sim.skills))),
            ]
            if selected_sim.metadata:
                text_hints = selected_sim.metadata.get("text_hints", {})
                sim_rows.extend(
                    [
                        ("Package path", str(selected_sim.metadata.get("package_path", "-"))),
                        ("Package size", f"{selected_sim.metadata.get('package_size', 0)} bytes"),
                    ]
                )
                if isinstance(text_hints, dict) and text_hints.get("name_candidates"):
                    sim_rows.append(
                        ("Detected package names", ", ".join(text_hints.get("name_candidates", [])[:5]))
                    )
            sections.append(self._render_info_card("Current Sim", self._render_kv_rows(sim_rows)))
        elif self.sim_list.count() > 0:
            sections.append(
                self._render_info_card(
                    "Current Sim",
                    self._render_kv_rows([("Selection", "Select a Sim on the left to inspect and edit details here")]),
                )
            )
        else:
            sections.append(
                self._render_info_card(
                    "Current Sim",
                    self._render_kv_rows([("Selection", "No Sims match the current household scope and search filter")]),
                )
            )

        self.overview_text.setHtml(self._render_html_view("Workspace Overview", sections))

    def _refresh_history_view(self) -> None:
        labels = self.session.history_labels
        if not labels:
            self.history_view.setPlainText("No changes yet.")
            return

        lines = [f"{idx + 1}. {label}" for idx, label in enumerate(labels)]
        if self._is_preview_mode():
            lines.insert(0, "Read-only filesystem preview loaded from a Sims 2 folder.")
        self.history_view.setPlainText("\n".join(lines))

    def _refresh_family_view(self) -> None:
        savegame = self.session.current
        household = self._find_household_by_id(self._current_family_id or self._current_household_filter_id)
        if savegame is None or household is None:
            self.family_detail_view.setHtml(
                self._render_html_view(
                    "Family Overview",
                    [self._render_info_card("Current Family", self._render_kv_rows([("Selection", "No family selected")]))],
                )
            )
            return

        family_sims = [sim for sim in savegame.sims if sim.id in household.members]
        if not family_sims and household.id:
            family_sims = [sim for sim in savegame.sims if sim.household_id == household.id]
        linked_lots = [lot for lot in savegame.lots if lot.household_id == household.id]
        for sim in family_sims:
            self._ensure_sim_name_hint(sim)

        sections = [
            self._render_info_card(
                "Current Family",
                self._render_stat_grid(
                    [
                        ("Members", str(len(family_sims))),
                        ("Linked lots", str(len(linked_lots))),
                        ("Funds", str(household.funds)),
                    ]
                )
                + self._render_kv_rows(
                    [
                        ("Family", household.name),
                        ("Family ID", household.id),
                    ]
                ),
            ),
            self._render_info_card("Family Members", self._render_sim_cards(savegame, family_sims, limit=30)),
            self._render_info_card("Linked Lots", self._render_lot_cards(linked_lots)),
        ]
        self.family_detail_view.setHtml(self._render_html_view("Family Overview", sections))

    def _refresh_relationship_view(self) -> None:
        savegame = self.session.current
        neighborhood_id = self._current_household_filter_id
        if savegame is None or not neighborhood_id:
            self.relationship_summary_view.setHtml(
                self._render_html_view(
                    "Relationship Overview",
                    [self._render_info_card("Current Scope", self._render_kv_rows([("Selection", "No neighborhood selected")]))],
                )
            )
            self.relationship_list.clear()
            self._clear_relationship_editor()
            return
        relationships = self._relationships_in_scope()
        self._populate_relationship_sim_options()

        sections = [
            self._render_info_card(
                "Relationship Summary",
                self._render_stat_grid(
                    [
                        ("Visible", str(len(relationships))),
                        ("Focus", self.relationship_focus_select.currentText()),
                    ]
                )
                + self._render_kv_rows([("Search", self.relationship_search.text().strip() or "-")]),
            )
        ]

        if not relationships:
            empty_rows = [
                ("Decoder state", "No decoded relationship resources were found in the current scope yet"),
                ("Editing", "You can already stage relationship entries manually here while the DBPF relationship decoder is still missing"),
            ]
            inferred_lot = self._current_lot()
            inferred_residents = []
            if inferred_lot is not None:
                inferred_residents = list(inferred_lot.metadata.get("resident_sim_ids", []))
            if inferred_residents:
                empty_rows.append(("Inferred co-resident links", ", ".join(inferred_residents[:20])))
            sections.append(self._render_info_card("Relationship State", self._render_kv_rows(empty_rows)))
            self.relationship_summary_view.setHtml(self._render_html_view("Relationship Overview", sections))
            self.relationship_list.clear()
            self._clear_relationship_editor()
            return

        sections.append(self._render_info_card("Visible Relationships", self._render_relationship_cards(relationships)))
        self.relationship_summary_view.setHtml(self._render_html_view("Relationship Overview", sections))

        self.relationship_list.blockSignals(True)
        self.relationship_list.clear()
        for rel in relationships:
            sim_a_label = self._sim_display_label(rel.sim_a)
            sim_b_label = self._sim_display_label(rel.sim_b)
            item = QListWidgetItem(
                f"{sim_a_label} -> {sim_b_label} | daily {rel.score_daily} | life {rel.score_lifetime}"
            )
            key = self._relationship_key(rel.sim_a, rel.sim_b)
            item.setData(Qt.UserRole, key)
            self.relationship_list.addItem(item)

        target_key = self._current_relationship_key or self.relationship_list.item(0).data(Qt.UserRole)
        selected_row = 0
        for row in range(self.relationship_list.count()):
            item = self.relationship_list.item(row)
            if item.data(Qt.UserRole) == target_key:
                selected_row = row
                break
        self.relationship_list.setCurrentRow(selected_row)
        current_item = self.relationship_list.currentItem()
        self.relationship_list.blockSignals(False)
        self._on_relationship_selected(current_item, None)

    def _relationship_key(self, sim_a: str, sim_b: str) -> str:
        return f"{sim_a}->{sim_b}"

    def _sim_display_label(self, sim_id: str) -> str:
        sim = self._find_sim_by_id(sim_id)
        if sim is None:
            return sim_id
        self._ensure_sim_name_hint(sim)
        return f"{sim.name} ({sim.id})"

    def _find_sim_by_id(self, sim_id: str):
        savegame = self.session.current
        if savegame is None:
            return None
        return next((sim for sim in savegame.sims if sim.id == sim_id), None)

    def _relationships_in_scope(self):
        savegame = self.session.current
        if savegame is None or not self._current_household_filter_id:
            return []

        neighborhood_sim_ids = {sim.id for sim in savegame.sims if sim.household_id == self._current_household_filter_id}
        relationships = [
            rel for rel in savegame.relationships if rel.sim_a in neighborhood_sim_ids or rel.sim_b in neighborhood_sim_ids
        ]

        focus_mode = self.relationship_focus_select.currentData()
        if focus_mode == "selected-sim" and self._current_sim_id:
            relationships = [
                rel for rel in relationships if rel.sim_a == self._current_sim_id or rel.sim_b == self._current_sim_id
            ]
        elif focus_mode == "selected-family" and self._current_family_id:
            family_ids = set(self._selected_family_member_ids())
            if family_ids:
                relationships = [
                    rel for rel in relationships if rel.sim_a in family_ids or rel.sim_b in family_ids
                ]

        search_term = self.relationship_search.text().strip().lower()
        if search_term:
            filtered: list = []
            for rel in relationships:
                haystack = (
                    f"{rel.sim_a} {rel.sim_b} {self._sim_display_label(rel.sim_a)} {self._sim_display_label(rel.sim_b)} "
                    f"{' '.join(rel.flags)}"
                ).lower()
                if search_term in haystack:
                    filtered.append(rel)
            relationships = filtered
        return relationships

    def _populate_relationship_sim_options(self) -> None:
        savegame = self.session.current
        self.relationship_sim_a_select.blockSignals(True)
        self.relationship_sim_b_select.blockSignals(True)
        current_a = self.relationship_sim_a_select.currentData()
        current_b = self.relationship_sim_b_select.currentData()
        self.relationship_sim_a_select.clear()
        self.relationship_sim_b_select.clear()
        if savegame is not None and self._current_household_filter_id:
            sims = [sim for sim in savegame.sims if sim.household_id == self._current_household_filter_id]
            for sim in sims:
                self._ensure_sim_name_hint(sim)
                label = f"{sim.name} ({sim.id})"
                self.relationship_sim_a_select.addItem(label, sim.id)
                self.relationship_sim_b_select.addItem(label, sim.id)
        for combo, current_value in ((self.relationship_sim_a_select, current_a), (self.relationship_sim_b_select, current_b)):
            for index in range(combo.count()):
                if combo.itemData(index) == current_value:
                    combo.setCurrentIndex(index)
                    break
        self.relationship_sim_a_select.blockSignals(False)
        self.relationship_sim_b_select.blockSignals(False)

    def _clear_relationship_editor(self) -> None:
        self._current_relationship_key = ""
        self.relationship_sim_a_select.setCurrentIndex(-1)
        self.relationship_sim_b_select.setCurrentIndex(-1)
        self.relationship_daily_spin.setValue(0)
        self.relationship_lifetime_spin.setValue(0)
        self.relationship_flags_edit.clear()

    def _find_relationship_by_key(self, key: str):
        savegame = self.session.current
        if savegame is None:
            return None
        for rel in savegame.relationships:
            if self._relationship_key(rel.sim_a, rel.sim_b) == key:
                return rel
        return None

    def _on_relationship_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._clear_relationship_editor()
            return
        key = current.data(Qt.UserRole)
        if not isinstance(key, str):
            self._clear_relationship_editor()
            return
        rel = self._find_relationship_by_key(key)
        if rel is None:
            self._clear_relationship_editor()
            return
        self._current_relationship_key = key
        for combo, sim_id in ((self.relationship_sim_a_select, rel.sim_a), (self.relationship_sim_b_select, rel.sim_b)):
            for index in range(combo.count()):
                if combo.itemData(index) == sim_id:
                    combo.setCurrentIndex(index)
                    break
        self.relationship_daily_spin.setValue(rel.score_daily)
        self.relationship_lifetime_spin.setValue(rel.score_lifetime)
        self.relationship_flags_edit.setText(", ".join(rel.flags))

    def apply_relationship_changes(self) -> None:
        if not self._current_relationship_key:
            return
        sim_a = self.relationship_sim_a_select.currentData()
        sim_b = self.relationship_sim_b_select.currentData()
        if not isinstance(sim_a, str) or not isinstance(sim_b, str) or not sim_a or not sim_b:
            return
        new_daily = int(self.relationship_daily_spin.value())
        new_lifetime = int(self.relationship_lifetime_spin.value())
        new_flags = [flag.strip() for flag in self.relationship_flags_edit.text().split(",") if flag.strip()]
        key = self._current_relationship_key

        def mutate(data: SaveGame) -> None:
            rel = next((entry for entry in data.relationships if self._relationship_key(entry.sim_a, entry.sim_b) == key), None)
            if rel is None:
                return
            rel.sim_a = sim_a
            rel.sim_b = sim_b
            rel.score_daily = new_daily
            rel.score_lifetime = new_lifetime
            rel.flags = new_flags

        self.session.apply(f"Updated relationship {key}", mutate)
        self._current_relationship_key = self._relationship_key(sim_a, sim_b)
        self._refresh_detail_views()
        self.statusBar().showMessage("Relationship updated in-session")

    def add_relationship(self) -> None:
        sim_a = self.relationship_sim_a_select.currentData()
        sim_b = self.relationship_sim_b_select.currentData()
        if not isinstance(sim_a, str) or not isinstance(sim_b, str) or not sim_a or not sim_b:
            return
        daily = int(self.relationship_daily_spin.value())
        lifetime = int(self.relationship_lifetime_spin.value())
        flags = [flag.strip() for flag in self.relationship_flags_edit.text().split(",") if flag.strip()]
        new_key = self._relationship_key(sim_a, sim_b)

        def mutate(data: SaveGame) -> None:
            exists = next((entry for entry in data.relationships if self._relationship_key(entry.sim_a, entry.sim_b) == new_key), None)
            if exists is not None:
                exists.score_daily = daily
                exists.score_lifetime = lifetime
                exists.flags = flags
                return
            data.relationships.append(
                Relationship(sim_a=sim_a, sim_b=sim_b, score_daily=daily, score_lifetime=lifetime, flags=flags)
            )

        self.session.apply(f"Added relationship {new_key}", mutate)
        self._current_relationship_key = new_key
        self._refresh_detail_views()
        self.statusBar().showMessage("Relationship added in-session")

    def remove_relationship(self) -> None:
        if not self._current_relationship_key:
            return
        key = self._current_relationship_key

        def mutate(data: SaveGame) -> None:
            data.relationships = [
                rel for rel in data.relationships if self._relationship_key(rel.sim_a, rel.sim_b) != key
            ]

        self.session.apply(f"Removed relationship {key}", mutate)
        self._current_relationship_key = ""
        self._refresh_detail_views()
        self.statusBar().showMessage("Relationship removed in-session")

    def _refresh_sim_insights(self) -> None:
        savegame = self.session.current
        if savegame is None or not self._current_sim_id:
            self.sim_insights_view.setPlainText(
                "Sim Insights\n\nSelect a Sim to inspect detected wishes, clothing hints, and package-derived labels."
            )
            return

        sim = next((entry for entry in savegame.sims if entry.id == self._current_sim_id), None)
        if sim is None:
            self.sim_insights_view.setPlainText("No Sim selected.")
            return
        self._ensure_sim_name_hint(sim)
        text_hints = sim.metadata.get("text_hints", {}) if isinstance(sim.metadata, dict) else {}
        edited_wants = sim.metadata.get("edited_wants", []) if isinstance(sim.metadata, dict) else []
        edited_clothing = sim.metadata.get("edited_clothing", []) if isinstance(sim.metadata, dict) else []
        edited_notes = sim.metadata.get("edited_notes", "") if isinstance(sim.metadata, dict) else ""
        lines = [
            "Sim Insights",
            "",
            f"Sim: {sim.name}",
            f"Sim ID: {sim.id}",
            "",
            "Detected wishes / fears",
        ]
        want_candidates = edited_wants or (text_hints.get("want_candidates", []) if isinstance(text_hints, dict) else [])
        if want_candidates:
            lines.extend(str(value) for value in want_candidates[:20])
        else:
            lines.append("No reliable wish or fear labels detected yet.")

        lines.extend(["", "Detected clothing / appearance hints"])
        clothing_candidates = edited_clothing or (text_hints.get("clothing_candidates", []) if isinstance(text_hints, dict) else [])
        if clothing_candidates:
            lines.extend(str(value) for value in clothing_candidates[:20])
        else:
            lines.append("No reliable clothing hints detected yet.")

        lines.extend(["", "Editor notes"])
        if str(edited_notes).strip():
            lines.extend(str(edited_notes).strip().splitlines())
        else:
            lines.append("No editor notes yet.")

        lines.extend(["", "Other package labels"])
        preview_strings = text_hints.get("preview_strings", []) if isinstance(text_hints, dict) else []
        if preview_strings:
            lines.extend(str(value) for value in preview_strings[:20])
        else:
            lines.append("No additional package labels available.")
        self.sim_insights_view.setPlainText("\n".join(lines))

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
            for lot in savegame.lots:
                self.issue_scope_select.addItem(f"{lot.id} issues", lot.id)
            for neighborhood in savegame.neighborhoods:
                self.issue_scope_select.addItem(f"{neighborhood.id} issues", neighborhood.id)

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
        lot = self._current_lot()
        if household is not None:
            main_path = household.metadata.get("main_package_path")
            if main_path:
                self.package_source_select.addItem(f"{household.id} main package", main_path)
            for suburb_path in household.metadata.get("suburb_package_paths", []):
                self.package_source_select.addItem(Path(suburb_path).name, suburb_path)
            for thumbnail_path in household.metadata.get("thumbnail_package_paths", []):
                self.package_source_select.addItem(Path(thumbnail_path).name, thumbnail_path)

        if lot is not None and lot.package_path:
            preferred_value = lot.package_path
            self.package_source_select.addItem(f"{lot.id} lot package", lot.package_path)

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

        for lot in savegame.lots:
            if lot.package_path == path_text:
                package_info = lot.metadata.get("package_info")
                if isinstance(package_info, dict):
                    return package_info

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
                f"Text hint sample count: {len(package_info.get('text_hints', {}).get('preview_strings', [])) if isinstance(package_info.get('text_hints'), dict) else 0}",
            ]
        )

        text_hints = package_info.get("text_hints", {})
        if isinstance(text_hints, dict):
            if text_hints.get("name_candidates"):
                lines.extend(["", "Detected names"])
                for value in text_hints.get("name_candidates", [])[:8]:
                    lines.append(str(value))
            if text_hints.get("resident_name_candidates"):
                lines.extend(["", "Resident candidates"])
                for value in text_hints.get("resident_name_candidates", [])[:12]:
                    lines.append(str(value))
            if text_hints.get("object_name_candidates"):
                lines.extend(["", "Object name candidates"])
                for value in text_hints.get("object_name_candidates", [])[:20]:
                    lines.append(str(value))
            if text_hints.get("preview_strings"):
                lines.extend(["", "Sample strings"])
                for value in text_hints.get("preview_strings", [])[:12]:
                    lines.append(str(value))

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

    def _refresh_lot_details(self) -> None:
        savegame = self.session.current
        lot = self._current_lot()
        if savegame is None or lot is None:
            self._clear_lot_editor()
            self.lot_detail_view.setHtml(
                self._render_html_view(
                    "Lot Overview",
                    [
                        self._render_info_card(
                            "Current Lot",
                            self._render_kv_rows(
                                [("Selection", "Choose a neighborhood and then a lot to inspect residents, package hints, and object names")]
                            ),
                        )
                    ],
                )
            )
            self.lot_resident_list.clear()
            self.lot_object_list.clear()
            return

        text_hints = lot.metadata.get("text_hints", {}) if isinstance(lot.metadata, dict) else {}
        resident_names = list(text_hints.get("resident_name_candidates", [])) if isinstance(text_hints, dict) else []
        resident_sim_ids = []
        for resident_name in resident_names:
            matched_sim = self._find_sim_by_display_name(resident_name, neighborhood_id=lot.neighborhood_id)
            resident_sim_ids.append(matched_sim.id if matched_sim is not None else "")
        lot.metadata["resident_sim_ids"] = resident_sim_ids
        self.lot_name_edit.setText(lot.name)
        self.lot_zone_select.setCurrentText(lot.zone_type or "unknown")
        self.lot_occupancy_select.setCurrentText(lot.occupancy or "unknown")
        self._refresh_lot_household_options(lot)

        sections = [
            self._render_info_card(
                "Current Lot",
                self._render_stat_grid(
                    [
                        ("Residents", str(len(resident_names))),
                        ("Matched Sims", str(len([item for item in resident_sim_ids if item]))),
                        ("Objects", str(len(text_hints.get('object_name_candidates', [])) if isinstance(text_hints, dict) else 0)),
                    ]
                )
                + self._render_kv_rows(
                    [
                        ("Name", lot.name),
                        ("Lot ID", lot.id),
                        ("Neighborhood", lot.neighborhood_id),
                        ("Package", lot.package_path or "-"),
                        ("Zone type", lot.zone_type),
                        ("Occupancy", lot.occupancy),
                        ("Linked household", lot.household_id or "-"),
                    ]
                ),
            ),
            self._render_info_card("Resident Candidates", self._render_resident_links(resident_names, resident_sim_ids)),
        ]

        if not lot.household_id:
            sections.append(
                self._render_info_card(
                    "Funds Editing",
                    self._render_kv_rows(
                        [
                            (
                                "Status",
                                "Lot-to-household linkage is not decoded yet. Household funds can already be staged in-session, but not reliably assigned per lot until family resources are parsed.",
                            )
                        ]
                    ),
                )
            )

        self.lot_detail_view.setHtml(self._render_html_view("Lot Overview", sections))

        self.lot_resident_list.blockSignals(True)
        self.lot_resident_list.clear()
        for resident_name in resident_names:
            item = QListWidgetItem(resident_name)
            matched_sim = self._find_sim_by_display_name(resident_name, neighborhood_id=lot.neighborhood_id)
            if matched_sim is not None:
                item.setData(Qt.UserRole, matched_sim.id)
            self.lot_resident_list.addItem(item)
        self.lot_resident_list.blockSignals(False)

        self.lot_object_list.clear()
        object_names = text_hints.get("object_name_candidates", []) if isinstance(text_hints, dict) else []
        object_filter = self.lot_object_search.text().strip().lower()
        visible_object_names = [
            object_name
            for object_name in object_names
            if not object_filter or object_filter in str(object_name).lower()
        ]
        for object_name in visible_object_names[:120]:
            self.lot_object_list.addItem(QListWidgetItem(str(object_name)))

    def _on_lot_resident_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        sim_id = current.data(Qt.UserRole)
        if not isinstance(sim_id, str):
            return
        for row in range(self.sim_list.count()):
            item = self.sim_list.item(row)
            if item.data(Qt.UserRole) == sim_id:
                self.sim_list.setCurrentRow(row)
                return

    def _clear_sim_editor(self) -> None:
        self.household_name_edit.clear()
        self.sim_name.clear()
        self.sim_age.setCurrentText("unknown")
        self.sim_aspiration.clear()
        self.sim_career.clear()
        self.sim_career_level.setValue(1)
        self.sim_wants_edit.clear()
        self.sim_clothing_edit.clear()
        self.sim_notes_edit.clear()
        self.needs_table.setRowCount(0)
        self.skills_table.setRowCount(0)

    def _clear_lot_editor(self) -> None:
        name_blocker = QSignalBlocker(self.lot_name_edit)
        zone_blocker = QSignalBlocker(self.lot_zone_select)
        occupancy_blocker = QSignalBlocker(self.lot_occupancy_select)
        household_blocker = QSignalBlocker(self.lot_household_select)
        object_filter_blocker = QSignalBlocker(self.lot_object_search)
        self.lot_name_edit.clear()
        self.lot_zone_select.setCurrentText("unknown")
        self.lot_occupancy_select.setCurrentText("unknown")
        self.lot_household_select.clear()
        self.lot_object_search.clear()
        del name_blocker
        del zone_blocker
        del occupancy_blocker
        del household_blocker
        del object_filter_blocker

    def _set_editing_enabled(self, enabled: bool) -> None:
        self.funds_spin.setEnabled(enabled)
        self.apply_household_button.setEnabled(enabled)
        self.household_name_edit.setEnabled(enabled)
        self.lot_name_edit.setEnabled(enabled)
        self.lot_zone_select.setEnabled(enabled)
        self.lot_occupancy_select.setEnabled(enabled)
        self.lot_household_select.setEnabled(enabled)
        self.apply_lot_button.setEnabled(enabled)
        self.sim_name.setEnabled(enabled)
        self.sim_age.setEnabled(enabled)
        self.sim_aspiration.setEnabled(enabled)
        self.sim_career.setEnabled(enabled)
        self.sim_career_level.setEnabled(enabled)
        self.sim_wants_edit.setEnabled(enabled)
        self.sim_clothing_edit.setEnabled(enabled)
        self.sim_notes_edit.setEnabled(enabled)
        self.needs_table.setEnabled(enabled)
        self.skills_table.setEnabled(enabled)
        self.apply_sim_button.setEnabled(enabled)
        self.relationship_sim_a_select.setEnabled(enabled)
        self.relationship_sim_b_select.setEnabled(enabled)
        self.relationship_daily_spin.setEnabled(enabled)
        self.relationship_lifetime_spin.setEnabled(enabled)
        self.relationship_flags_edit.setEnabled(enabled)
        self.apply_relationship_button.setEnabled(enabled)
        self.add_relationship_button.setEnabled(enabled)
        self.remove_relationship_button.setEnabled(enabled)

    def _find_household_by_id(self, household_id: str):
        savegame = self.session.current
        if savegame is None:
            return None
        return next((household for household in savegame.households if household.id == household_id), None)

    def _find_lot_by_id(self, lot_id: str):
        savegame = self.session.current
        if savegame is None:
            return None
        return next((lot for lot in savegame.lots if lot.id == lot_id), None)

    def _find_first_lot_for_family(self, family_id: str):
        savegame = self.session.current
        if savegame is None:
            return None
        return next((lot for lot in savegame.lots if lot.household_id == family_id), None)

    def _selected_family_member_ids(self) -> list[str]:
        if not self._current_family_id:
            return []
        household = self._find_household_by_id(self._current_family_id)
        if household is None:
            return []
        return list(household.members)

    def _ensure_sim_name_hint(self, sim) -> None:
        if sim.metadata.get("text_hints"):
            return
        package_path = sim.metadata.get("package_path")
        if not isinstance(package_path, str) or not package_path:
            return
        text_hints = extract_package_text_hints(package_path, "Character/Sim")
        sim.metadata["text_hints"] = text_hints
        if sim.name == sim.id and isinstance(text_hints, dict):
            name_candidates = text_hints.get("name_candidates", [])
            if isinstance(name_candidates, list) and name_candidates:
                sim.name = str(name_candidates[0])

    def _find_sim_by_display_name(self, display_name: str, *, neighborhood_id: str = ""):
        savegame = self.session.current
        if savegame is None:
            return None
        target = display_name.casefold().strip()
        for sim in savegame.sims:
            if neighborhood_id and sim.household_id != neighborhood_id:
                continue
            self._ensure_sim_name_hint(sim)
            if sim.name.casefold().strip() == target:
                return sim
        return None

    def _match_resident_names_to_sims(self, neighborhood_id: str, resident_names: list[str]) -> list[str]:
        matched_ids: list[str] = []
        for resident_name in resident_names:
            sim = self._find_sim_by_display_name(resident_name, neighborhood_id=neighborhood_id)
            if sim is not None:
                matched_ids.append(sim.id)
        return matched_ids

    def _refresh_lot_household_options(self, lot) -> None:
        savegame = self.session.current
        current_value = lot.household_id if lot is not None else ""
        self.lot_household_select.blockSignals(True)
        self.lot_household_select.clear()
        self.lot_household_select.addItem("Unassigned", "")
        if savegame is not None and lot is not None:
            candidates = [
                household for household in savegame.households if household.id == lot.neighborhood_id
            ]
            for household in candidates:
                self.lot_household_select.addItem(
                    f"{household.name} ({household.id})",
                    household.id,
                )
        for index in range(self.lot_household_select.count()):
            if self.lot_household_select.itemData(index) == current_value:
                self.lot_household_select.setCurrentIndex(index)
                break
        else:
            self.lot_household_select.setCurrentIndex(0)
        self.lot_household_select.blockSignals(False)

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

    def _select_family_list_item(self, family_id: str, *, emit_signal: bool = True) -> None:
        blocker = QSignalBlocker(self.family_list) if not emit_signal else None
        for row in range(self.family_list.count()):
            item = self.family_list.item(row)
            if item.data(Qt.UserRole) == family_id:
                self.family_list.setCurrentRow(row)
                del blocker
                return
        del blocker

    def _select_sim_list_item(self, sim_id: str, *, emit_signal: bool = True) -> None:
        blocker = QSignalBlocker(self.sim_list) if not emit_signal else None
        for row in range(self.sim_list.count()):
            item = self.sim_list.item(row)
            if item.data(Qt.UserRole) == sim_id:
                self.sim_list.setCurrentRow(row)
                del blocker
                return
        del blocker

    def _select_lot_list_item(self, lot_id: str, *, emit_signal: bool = True) -> None:
        blocker = QSignalBlocker(self.lot_list) if not emit_signal else None
        for row in range(self.lot_list.count()):
            item = self.lot_list.item(row)
            if item.data(Qt.UserRole) == lot_id:
                self.lot_list.setCurrentRow(row)
                del blocker
                return
        del blocker

    def apply_household_changes(self) -> None:
        savegame = self.session.current
        household = self._current_household()
        if savegame is None or household is None:
            return

        household_id = household.id
        new_name = self.household_name_edit.text().strip() or household_id
        new_funds = int(self.funds_spin.value())

        def mutate(data: SaveGame) -> None:
            target = next((entry for entry in data.households if entry.id == household_id), None)
            if target is not None:
                target.name = new_name
                target.funds = new_funds

        self.session.apply(f"Updated household {household_id}", mutate)
        self._refresh_ui()
        if self._is_preview_mode():
            self.statusBar().showMessage("Household changes updated in-session; package writeback is not available yet")
        else:
            self.statusBar().showMessage("Household changes applied")

    def apply_lot_changes(self) -> None:
        lot = self._current_lot()
        if lot is None:
            return

        lot_id = lot.id
        new_name = self.lot_name_edit.text().strip() or lot_id
        new_zone = self.lot_zone_select.currentText().strip() or "unknown"
        new_occupancy = self.lot_occupancy_select.currentText().strip() or "unknown"
        linked_household_id = self.lot_household_select.currentData()
        new_household_id = linked_household_id if isinstance(linked_household_id, str) else ""

        def mutate(data: SaveGame) -> None:
            target = next((entry for entry in data.lots if entry.id == lot_id), None)
            if target is None:
                return
            target.name = new_name
            target.zone_type = new_zone
            target.occupancy = new_occupancy
            target.household_id = new_household_id

        self.session.apply(f"Updated lot {lot_id}", mutate)
        self._refresh_ui()
        if self._is_preview_mode():
            self.statusBar().showMessage("Lot changes staged in-session; package writeback is not available yet")
        else:
            self.statusBar().showMessage("Lot changes applied")

    def apply_sim_changes(self) -> None:
        if not self._current_sim_id:
            return

        new_name = self.sim_name.text().strip() or "Unnamed Sim"
        new_age = self.sim_age.currentText().strip()
        new_aspiration = self.sim_aspiration.text().strip()
        new_career = self.sim_career.text().strip()
        new_career_level = int(self.sim_career_level.value())
        new_wants = [line.strip() for line in self.sim_wants_edit.toPlainText().splitlines() if line.strip()]
        new_clothing = [line.strip() for line in self.sim_clothing_edit.toPlainText().splitlines() if line.strip()]
        new_notes = self.sim_notes_edit.toPlainText().strip()
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
            sim.metadata["edited_wants"] = new_wants
            sim.metadata["edited_clothing"] = new_clothing
            sim.metadata["edited_notes"] = new_notes
            sim.needs = new_needs
            sim.skills = new_skills

        self.session.apply(f"Updated sim {current_sim_id}", mutate)
        self._refresh_ui()
        if self._is_preview_mode():
            self.statusBar().showMessage("Sim changes staged in-session; package writeback is not available yet")
        else:
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
