import json
from pathlib import Path
import struct

import pytest

from s2saveforge.core.service import SaveSession
from s2saveforge.core.parser import ReadOnlySaveFormatError


SAMPLE = {
    "version": "0.1",
    "households": [
        {"id": "hh-1", "name": "Test", "funds": 1000, "members": ["sim-1"]}
    ],
    "sims": [
        {
            "id": "sim-1",
            "name": "Tester",
            "age_stage": "adult",
            "aspiration": "knowledge",
            "household_id": "hh-1",
            "career": "Science",
            "career_level": 3,
            "needs": {"hunger": 80},
            "skills": {"logic": 4}
        }
    ],
    "relationships": []
}


def _write_sample(path: Path) -> None:
    path.write_text(json.dumps(SAMPLE, indent=2), encoding="utf-8")


def test_session_backup_undo_redo_save(tmp_path: Path) -> None:
    source = tmp_path / "test_save.s2json"
    _write_sample(source)

    session = SaveSession()
    session.load(source)

    def mutate(data):
        data.households[0].funds = 9999

    session.apply("Change funds", mutate)
    assert session.current is not None
    assert session.current.households[0].funds == 9999

    session.undo()
    assert session.current is not None
    assert session.current.households[0].funds == 1000

    session.redo()
    assert session.current is not None
    assert session.current.households[0].funds == 9999

    backup = session.create_backup(tmp_path / "backups")
    assert backup.exists()

    target = session.save()
    assert target.exists()

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["households"][0]["funds"] == 9999


def test_session_loads_sims2_folder_preview_and_blocks_save(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 2"
    neighborhood = root / "Neighborhoods" / "N001"
    characters = neighborhood / "Characters"
    lots = neighborhood / "Lots"
    characters.mkdir(parents=True)
    lots.mkdir(parents=True)

    _write_fake_dbpf(neighborhood / "N001_Neighborhood.package", entry_count=2)
    _write_fake_dbpf(characters / "N001_User00000.package", entry_count=1)
    _write_fake_dbpf(characters / "N001_User00001.package", entry_count=1)
    _write_fake_dbpf(lots / "N001_Lot1.package", entry_count=1)

    session = SaveSession()
    savegame = session.load(root)

    assert savegame.version.startswith("fs-preview:")
    assert len(savegame.households) == 1
    assert savegame.households[0].id == "N001"
    assert savegame.households[0].members == ["N001_User00000", "N001_User00001"]
    assert savegame.households[0].metadata["main_package_exists"] is True
    assert savegame.households[0].metadata["lot_count"] == 1
    assert savegame.households[0].metadata["character_count"] == 2
    assert savegame.households[0].metadata["main_package_info"]["exists"] is True
    assert savegame.households[0].metadata["main_package_info"]["is_dbpf"] is True
    assert savegame.households[0].metadata["main_package_info"]["parsed_index_entry_count"] == 2
    assert savegame.households[0].metadata["main_package_info"]["index_entries_preview"][0]["type_name"] != ""
    assert savegame.households[0].metadata["main_package_info"]["index_entries_preview"][0]["domain_hint"] != ""
    assert isinstance(savegame.households[0].metadata["main_package_info"]["domain_profile"], list)
    assert len(savegame.sims) == 2
    assert savegame.sims[0].metadata["package_path"].endswith(".package")
    assert savegame.sims[0].metadata["package_info"]["exists"] is True
    assert savegame.sims[0].metadata["package_info"]["parsed_index_entry_count"] == 1
    assert savegame.metadata["source_kind"] == "folder_preview"
    assert savegame.metadata["neighborhood_manager_exists"] is False
    assert savegame.metadata["neighborhood_manager_info"]["exists"] is False

    with pytest.raises(ReadOnlySaveFormatError):
        session.create_backup()

    with pytest.raises(ReadOnlySaveFormatError):
        session.save()


def _write_fake_dbpf(path: Path, entry_count: int) -> None:
    index_offset = 96
    entry_size = 20
    index_size = entry_count * entry_size
    values = [
        1,  # major
        2,  # minor
        0,
        0,
        0,
        0,
        0,
        7,  # index version major
        entry_count,
        index_offset,
        index_size,
        0,
        0,
        0,
        2,  # index version minor
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
    for idx in range(entry_count):
        entries.append(
            struct.pack(
                "<5I",
                0xE86B1EEF + idx,
                0xFFFFFFFF,
                idx + 1,
                data_offset + (idx * 32),
                32,
            )
        )

    path.write_bytes(header + b"".join(entries) + (b"\x00" * (32 * entry_count)))
