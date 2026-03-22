import json
from pathlib import Path

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

    (neighborhood / "N001_Neighborhood.package").write_bytes(b"pkg")
    (characters / "N001_User00000.package").write_bytes(b"sim-a")
    (characters / "N001_User00001.package").write_bytes(b"sim-b")
    (lots / "N001_Lot1.package").write_bytes(b"lot")

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
    assert savegame.households[0].metadata["main_package_info"]["is_dbpf"] is False
    assert len(savegame.sims) == 2
    assert savegame.sims[0].metadata["package_path"].endswith(".package")
    assert savegame.sims[0].metadata["package_info"]["exists"] is True
    assert savegame.metadata["source_kind"] == "folder_preview"
    assert savegame.metadata["neighborhood_manager_exists"] is False
    assert savegame.metadata["neighborhood_manager_info"]["exists"] is False

    with pytest.raises(ReadOnlySaveFormatError):
        session.create_backup()

    with pytest.raises(ReadOnlySaveFormatError):
        session.save()
