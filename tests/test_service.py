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
    storytelling = neighborhood / "Storytelling"
    thumbnails = neighborhood / "Thumbnails"
    characters.mkdir(parents=True)
    lots.mkdir(parents=True)
    storytelling.mkdir(parents=True)
    thumbnails.mkdir(parents=True)

    _write_fake_dbpf(neighborhood / "N001_Neighborhood.package", entry_count=2)
    (neighborhood / "N001_Neighborhood.png").write_bytes(b"PNG")
    (neighborhood / "N001_Neighborhood.reia").write_text("meta", encoding="utf-8")
    (neighborhood / "N001_0x00000000.dat").write_bytes(b"\x01\x02\x03")
    _write_fake_dbpf(characters / "N001_User00000.package", entry_count=1)
    _write_fake_dbpf(characters / "N001_User00001.package", entry_count=1)
    _write_fake_dbpf(lots / "N001_Lot1.package", entry_count=1)
    (storytelling / "webentry_0001.xml").write_text("<story />", encoding="utf-8")
    (storytelling / "thumbnail_0001.jpg").write_bytes(b"JPG")
    _write_fake_dbpf(thumbnails / "N001_FamilyThumbnails.package", entry_count=1)

    session = SaveSession()
    savegame = session.load(root)

    assert savegame.version.startswith("fs-preview:")
    assert len(savegame.households) == 1
    assert len(savegame.neighborhoods) == 1
    assert len(savegame.lots) == 1
    assert savegame.households[0].id == "N001"
    assert savegame.households[0].members == ["N001_User00000", "N001_User00001"]
    assert savegame.households[0].metadata["lot_ids"] == ["N001_Lot1"]
    assert savegame.neighborhoods[0].id == "N001"
    assert savegame.neighborhoods[0].lot_ids == ["N001_Lot1"]
    assert savegame.neighborhoods[0].sim_ids == ["N001_User00000", "N001_User00001"]
    assert savegame.lots[0].id == "N001_Lot1"
    assert savegame.lots[0].neighborhood_id == "N001"
    assert savegame.lots[0].metadata["package_info"]["package_role"] == "Lot"
    assert savegame.households[0].metadata["main_package_exists"] is True
    assert savegame.households[0].metadata["lot_count"] == 1
    assert savegame.households[0].metadata["character_count"] == 2
    assert savegame.households[0].metadata["main_package_info"]["exists"] is True
    assert savegame.households[0].metadata["main_package_info"]["is_dbpf"] is True
    assert savegame.households[0].metadata["main_package_info"]["package_role"] == "Neighborhood Main"
    assert savegame.households[0].metadata["main_package_info"]["parsed_index_entry_count"] == 2
    assert savegame.households[0].metadata["main_package_info"]["index_entries_preview"][0]["type_name"] != ""
    assert savegame.households[0].metadata["main_package_info"]["index_entries_preview"][0]["domain_hint"] != ""
    assert isinstance(savegame.households[0].metadata["main_package_info"]["domain_profile"], list)
    assert savegame.households[0].metadata["thumbnail_package_count"] == 1
    assert savegame.households[0].metadata["thumbnail_package_paths"][0].endswith("N001_FamilyThumbnails.package")
    assert savegame.households[0].metadata["thumbnail_package_infos"][0]["exists"] is True
    file_inventory = savegame.households[0].metadata["file_inventory"]
    assert file_inventory["total_file_count"] == 10
    role_counts = {entry["role"]: entry["count"] for entry in file_inventory["role_profile"]}
    assert role_counts["Neighborhood Main Package"] == 1
    assert role_counts["Neighborhood Preview Image"] == 1
    assert role_counts["Neighborhood Metadata"] == 1
    assert role_counts["Raw Data"] == 1
    assert role_counts["Character Package"] == 2
    assert role_counts["Lot Package"] == 1
    assert role_counts["Thumbnail Package"] == 1
    assert role_counts["Storytelling Entry"] == 1
    assert role_counts["Storytelling Image"] == 1
    extension_counts = {entry["extension"]: entry["count"] for entry in file_inventory["extension_profile"]}
    assert extension_counts[".package"] == 5
    assert extension_counts[".dat"] == 1
    assert extension_counts[".reia"] == 1
    assert savegame.metadata["neighborhood_file_count"] == 10
    assert isinstance(savegame.metadata["neighborhood_file_role_profile"], list)
    assert isinstance(savegame.metadata["neighborhood_file_extension_profile"], list)
    assert len(savegame.sims) == 2
    assert savegame.sims[0].metadata["package_path"].endswith(".package")
    assert savegame.sims[0].metadata["package_info"]["exists"] is True
    assert savegame.sims[0].metadata["package_info"]["package_role"] == "Character/Sim"
    assert savegame.sims[0].metadata["package_info"]["parsed_index_entry_count"] == 1
    assert savegame.metadata["source_kind"] == "folder_preview"
    assert savegame.metadata["lot_count"] == 1
    assert savegame.metadata["neighborhood_manager_exists"] is False
    assert savegame.metadata["neighborhood_manager_info"]["exists"] is False
    assert isinstance(savegame.metadata["package_role_profile"], list)

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
