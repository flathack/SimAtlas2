import json
from pathlib import Path

from s2saveforge.core.service import SaveSession


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
