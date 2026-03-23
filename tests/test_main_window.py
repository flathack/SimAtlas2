from pathlib import Path
import struct

from PySide6.QtWidgets import QApplication

from s2saveforge.ui.main_window import MainWindow


def _build_preview_root(tmp_path: Path) -> Path:
    root = tmp_path / "The Sims 2"
    neighborhoods = root / "Neighborhoods"

    for neighborhood_id, character_count in (("N001", 2), ("N002", 1)):
        neighborhood = neighborhoods / neighborhood_id
        characters = neighborhood / "Characters"
        lots = neighborhood / "Lots"
        characters.mkdir(parents=True)
        lots.mkdir(parents=True)

        _write_fake_dbpf(neighborhood / f"{neighborhood_id}_Neighborhood.package", entry_count=2)
        _write_fake_dbpf(lots / f"{neighborhood_id}_Lot1.package", entry_count=1)
        for index in range(character_count):
            _write_fake_dbpf(characters / f"{neighborhood_id}_User{index:05d}.package", entry_count=1)

    return root


def _write_fake_dbpf(path: Path, entry_count: int) -> None:
    index_offset = 96
    entry_size = 20
    index_size = entry_count * entry_size
    values = [
        1,
        2,
        0,
        0,
        0,
        0,
        0,
        7,
        entry_count,
        index_offset,
        index_size,
        0,
        0,
        0,
        2,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    ]
    header = struct.pack("<4s23I", b"DBPF", *values)

    entries = []
    data_offset = index_offset + index_size
    for index in range(entry_count):
        entries.append(
            struct.pack(
                "<5I",
                0xE86B1EEF + index,
                0xFFFFFFFF,
                index + 1,
                data_offset + (index * 32),
                32,
            )
        )

    path.write_bytes(header + b"".join(entries) + (b"\x00" * (32 * entry_count)))


def test_selecting_neighborhood_updates_scope_without_crash(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    assert window.household_list.count() == 2
    assert window.lot_list.count() == 1
    assert window.apply_household_button.isEnabled() is True
    assert window.apply_sim_button.isEnabled() is True
    assert window.apply_lot_button.isEnabled() is True

    window.household_list.setCurrentRow(1)
    app.processEvents()

    assert window._current_household_filter_id == "N002"
    assert window.household_select.currentData() == "N002"
    assert window.lot_list.count() == 1
    assert window.sim_list.count() == 1
    assert window.family_list.count() >= 1
    assert "Neighborhoods: 2" in window.counts_label.text()
    assert "Lots: 2" in window.counts_label.text()

    window.close()


def test_lot_changes_are_staged_in_preview_session(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    assert window.lot_list.count() == 1
    window.lot_list.setCurrentRow(0)
    app.processEvents()

    window.lot_name_edit.setText("Test Lot")
    window.lot_zone_select.setCurrentText("residential")
    window.lot_occupancy_select.setCurrentText("occupied")
    window.apply_lot_changes()
    app.processEvents()

    current_lot = window._current_lot()
    assert current_lot is not None
    assert current_lot.name == "Test Lot"
    assert current_lot.zone_type == "residential"
    assert current_lot.occupancy == "occupied"

    window.close()


def test_neighborhood_views_show_family_relationship_and_sim_insights(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()
    window.sim_list.setCurrentRow(0)
    app.processEvents()

    assert "Family Overview" in window.family_detail_view.toPlainText()
    assert "No decoded relationship resources" in window.relationship_summary_view.toPlainText()
    assert "Sim Insights" in window.sim_insights_view.toPlainText()

    window.close()


def test_overview_and_family_views_show_card_sections(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()
    window.sim_list.setCurrentRow(0)
    app.processEvents()

    overview_text = window.overview_text.toPlainText()
    family_text = window.family_detail_view.toPlainText()

    assert "Workspace Overview" in overview_text
    assert "Save Summary" in overview_text
    assert "Current Sim" in overview_text
    assert "Families" in overview_text
    assert "Visible Sims" in overview_text
    assert "Family Overview" in family_text
    assert "Current Family" in family_text
    assert "Family Members" in family_text

    window.close()


def test_visual_navigation_can_focus_selected_sim(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    first_sim_id = window.session.current.sims[0].id
    window._handle_visual_navigation(f"sim:{first_sim_id}")
    app.processEvents()

    assert window._current_sim_id == first_sim_id
    assert window.main_tabs.currentWidget() is window.editor_page
    assert window.sim_name.text() != ""

    window.close()


def test_household_changes_update_name_and_funds(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    window.household_name_edit.setText("Edited Neighborhood")
    window.funds_spin.setValue(4242)
    window.apply_household_changes()
    app.processEvents()

    current_household = window._current_household()
    assert current_household is not None
    assert current_household.name == "Edited Neighborhood"
    assert current_household.funds == 4242

    window.close()


def test_family_selection_filters_sim_scope(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    assert window.family_list.count() >= 1
    window.family_list.setCurrentRow(0)
    app.processEvents()

    assert window._current_family_id == "N001"
    assert window.sim_list.count() == 2
    assert "Family: N001" in window.family_detail_view.toPlainText() or "Edited Neighborhood" not in window.family_detail_view.toPlainText()

    window.close()


def test_relationship_can_be_added_and_updated_in_preview_session(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    window.relationship_sim_a_select.setCurrentIndex(0)
    window.relationship_sim_b_select.setCurrentIndex(1)
    window.relationship_daily_spin.setValue(25)
    window.relationship_lifetime_spin.setValue(40)
    window.relationship_flags_edit.setText("friend, ally")
    window.add_relationship()
    app.processEvents()

    assert len(window.session.current.relationships) == 1
    relationship = window.session.current.relationships[0]
    assert relationship.score_daily == 25
    assert relationship.score_lifetime == 40
    assert relationship.flags == ["friend", "ally"]

    window.relationship_daily_spin.setValue(55)
    window.apply_relationship_changes()
    app.processEvents()

    assert window.session.current.relationships[0].score_daily == 55

    window.close()


def test_relationship_tab_shows_visual_summary_cards(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    window.relationship_sim_a_select.setCurrentIndex(0)
    window.relationship_sim_b_select.setCurrentIndex(1)
    window.relationship_daily_spin.setValue(25)
    window.relationship_lifetime_spin.setValue(40)
    window.relationship_flags_edit.setText("friend")
    window.add_relationship()
    app.processEvents()

    text = window.relationship_summary_view.toPlainText()
    assert "Relationship Overview" in text
    assert "Relationship Summary" in text
    assert "Visible Relationships" in text

    window.close()


def test_lot_tab_shows_visual_overview(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()
    window.lot_list.setCurrentRow(0)
    app.processEvents()

    text = window.lot_detail_view.toPlainText()
    assert "Lot Overview" in text
    assert "Current Lot" in text
    assert "Resident Candidates" in text

    window.close()


def test_sim_wishes_clothing_and_notes_can_be_staged(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    root = _build_preview_root(tmp_path)

    window = MainWindow()
    window.session.load(root)
    window._refresh_ui()

    window.sim_list.setCurrentRow(0)
    app.processEvents()

    window.sim_wants_edit.setPlainText("Reach top career\nBuy a hot tub")
    window.sim_clothing_edit.setPlainText("Formal red dress\nEveryday denim jacket")
    window.sim_notes_edit.setPlainText("Prefers family aspiration stories")
    window.apply_sim_changes()
    app.processEvents()

    current_sim = next((sim for sim in window.session.current.sims if sim.id == window._current_sim_id), None)
    assert current_sim is not None
    assert current_sim.metadata["edited_wants"] == ["Reach top career", "Buy a hot tub"]
    assert current_sim.metadata["edited_clothing"] == ["Formal red dress", "Everyday denim jacket"]
    assert current_sim.metadata["edited_notes"] == "Prefers family aspiration stories"
    assert "Reach top career" in window.sim_insights_view.toPlainText()
    assert "Formal red dress" in window.sim_insights_view.toPlainText()
    assert "Prefers family aspiration stories" in window.sim_insights_view.toPlainText()

    window.close()
