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

    window.household_list.setCurrentRow(1)
    app.processEvents()

    assert window._current_household_filter_id == "N002"
    assert window.household_select.currentData() == "N002"
    assert window.sim_list.count() == 1

    window.close()
