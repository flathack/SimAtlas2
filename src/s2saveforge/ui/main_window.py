from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from s2saveforge.core.models import Household, SaveGame, Sim
from s2saveforge.core.parser import UnsupportedSaveFormatError
from s2saveforge.core.service import SaveSession


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("S2 Save Forge")

        self.session = SaveSession()
        self._current_sim_id: str = ""

        self._build_actions()
        self._build_layout()

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        action_open = QAction("Open", self)
        action_open.triggered.connect(self.open_file)

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

        toolbar = self.addToolBar("Main")
        toolbar.addAction(action_open)
        toolbar.addAction(action_load_demo)
        toolbar.addAction(action_backup)
        toolbar.addAction(action_save)
        toolbar.addSeparator()
        toolbar.addAction(action_undo)
        toolbar.addAction(action_redo)
        toolbar.addSeparator()
        toolbar.addAction(action_validate)

    def _build_layout(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        splitter = QSplitter(Qt.Horizontal, root)
        root_layout.addWidget(splitter)

        self.sim_list = QListWidget(splitter)
        self.sim_list.currentItemChanged.connect(self._on_sim_selected)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)

        household_box = QGroupBox("Household", right)
        household_form = QFormLayout(household_box)
        self.household_select = QComboBox(household_box)
        self.household_select.currentIndexChanged.connect(self._on_household_selected)

        self.funds_spin = QSpinBox(household_box)
        self.funds_spin.setRange(-9999999, 999999999)

        self.apply_household_button = QPushButton("Apply Household Funds", household_box)
        self.apply_household_button.clicked.connect(self.apply_household_changes)

        household_form.addRow("Select", self.household_select)
        household_form.addRow("Funds", self.funds_spin)
        household_form.addRow("", self.apply_household_button)
        right_layout.addWidget(household_box)

        sim_box = QGroupBox("Sim", right)
        sim_form = QFormLayout(sim_box)

        self.sim_name = QLineEdit(sim_box)
        self.sim_age = QComboBox(sim_box)
        self.sim_age.addItems(["baby", "toddler", "child", "teen", "adult", "elder"])

        self.sim_aspiration = QLineEdit(sim_box)
        self.sim_career = QLineEdit(sim_box)
        self.sim_career_level = QSpinBox(sim_box)
        self.sim_career_level.setRange(1, 20)

        sim_form.addRow("Name", self.sim_name)
        sim_form.addRow("Age", self.sim_age)
        sim_form.addRow("Aspiration", self.sim_aspiration)
        sim_form.addRow("Career", self.sim_career)
        sim_form.addRow("Career level", self.sim_career_level)

        table_row = QHBoxLayout()

        self.needs_table = QTableWidget(sim_box)
        self.needs_table.setColumnCount(2)
        self.needs_table.setHorizontalHeaderLabels(["Need", "Value"])
        self.needs_table.horizontalHeader().setStretchLastSection(True)

        self.skills_table = QTableWidget(sim_box)
        self.skills_table.setColumnCount(2)
        self.skills_table.setHorizontalHeaderLabels(["Skill", "Value"])
        self.skills_table.horizontalHeader().setStretchLastSection(True)

        table_row.addWidget(self.needs_table)
        table_row.addWidget(self.skills_table)

        sim_form.addRow(QLabel("Needs and Skills"), QWidget())
        sim_form.addRow(table_row)

        self.apply_sim_button = QPushButton("Apply Sim Changes", sim_box)
        self.apply_sim_button.clicked.connect(self.apply_sim_changes)
        sim_form.addRow("", self.apply_sim_button)

        right_layout.addWidget(sim_box)

        self.tabs = QTabWidget(right)

        self.validation_view = QTextEdit(self.tabs)
        self.validation_view.setReadOnly(True)

        self.history_view = QTextEdit(self.tabs)
        self.history_view.setReadOnly(True)

        self.tabs.addTab(self.validation_view, "Validation")
        self.tabs.addTab(self.history_view, "Changes")

        right_layout.addWidget(self.tabs)

    def _on_household_selected(self, index: int) -> None:
        savegame = self.session.current
        if savegame is None or index < 0 or index >= len(savegame.households):
            return
        household = savegame.households[index]
        self.funds_spin.setValue(household.funds)

    def _on_sim_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._current_sim_id = ""
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
        if not file_path:
            return
        self._load_path(Path(file_path))

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

        self._refresh_ui()
        self.statusBar().showMessage(f"Loaded: {path}")

    def _refresh_ui(self) -> None:
        savegame = self.session.current
        if savegame is None:
            return

        self.household_select.clear()
        for household in savegame.households:
            self.household_select.addItem(f"{household.name} ({household.id})")

        self.sim_list.clear()
        for sim in savegame.sims:
            item = QListWidgetItem(f"{sim.name} ({sim.id})")
            item.setData(Qt.UserRole, sim.id)
            self.sim_list.addItem(item)

        if self.household_select.count() > 0:
            self.household_select.setCurrentIndex(0)

        if self.sim_list.count() > 0:
            self.sim_list.setCurrentRow(0)

        self._refresh_history_view()

    def apply_household_changes(self) -> None:
        savegame = self.session.current
        index = self.household_select.currentIndex()
        if savegame is None or index < 0 or index >= len(savegame.households):
            return

        household_id = savegame.households[index].id
        new_funds = int(self.funds_spin.value())

        def mutate(data: SaveGame) -> None:
            household = next((entry for entry in data.households if entry.id == household_id), None)
            if household is None:
                return
            household.funds = new_funds

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
            self.tabs.setCurrentWidget(self.validation_view)
            self.statusBar().showMessage("Validation complete: no issues")
            return

        lines = []
        for issue in issues:
            entity = f" ({issue.entity_id})" if issue.entity_id else ""
            lines.append(f"[{issue.severity.upper()}] {issue.code}{entity}: {issue.message}")

        self.validation_view.setPlainText("\n".join(lines))
        self.tabs.setCurrentWidget(self.validation_view)
        self.statusBar().showMessage(f"Validation complete: {len(issues)} issue(s)")

    def _refresh_history_view(self) -> None:
        labels = self.session.history_labels
        if not labels:
            self.history_view.setPlainText("No changes yet.")
            return

        lines = [f"{idx + 1}. {label}" for idx, label in enumerate(labels)]
        self.history_view.setPlainText("\n".join(lines))


def run_app() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    return app.exec()
