from s2saveforge.core.models import Household, Lot, Neighborhood, Relationship, SaveGame, Sim
from s2saveforge.core.validators import group_issues_by_entity, summarize_issues, validate_savegame


def test_validate_detects_invalid_references_and_ranges() -> None:
    save = SaveGame(
        version="0.1",
        households=[Household(id="hh-1", name="Test HH", funds=-5, members=["sim-missing"])],
        neighborhoods=[Neighborhood(id="N001", name="N001", household_ids=["hh-missing"], lot_ids=["lot-missing"], sim_ids=["sim-missing"])],
        lots=[Lot(id="lot-1", name="Lot", neighborhood_id="N404", household_id="hh-404")],
        sims=[
            Sim(
                id="sim-1",
                name="Alice",
                age_stage="adult",
                aspiration="family",
                household_id="hh-unknown",
                career="Science",
                career_level=99,
                needs={"hunger": 120},
                skills={"logic": 12},
            )
        ],
        relationships=[Relationship(sim_a="sim-1", sim_b="sim-404", score_daily=0, score_lifetime=0)],
    )

    issues = validate_savegame(save)
    codes = {issue.code for issue in issues}

    assert "SIM_UNKNOWN_HOUSEHOLD" in codes
    assert "SIM_CAREER_LEVEL_RANGE" in codes
    assert "SIM_NEED_RANGE" in codes
    assert "SIM_SKILL_RANGE" in codes
    assert "HOUSEHOLD_NEGATIVE_FUNDS" in codes
    assert "HOUSEHOLD_UNKNOWN_MEMBER" in codes
    assert "NEIGHBORHOOD_UNKNOWN_HOUSEHOLD" in codes
    assert "NEIGHBORHOOD_UNKNOWN_LOT" in codes
    assert "NEIGHBORHOOD_UNKNOWN_SIM" in codes
    assert "LOT_UNKNOWN_NEIGHBORHOOD" in codes
    assert "LOT_UNKNOWN_HOUSEHOLD" in codes
    assert "RELATIONSHIP_UNKNOWN_SIM" in codes


def test_validate_detects_preview_filesystem_problems() -> None:
    save = SaveGame(
        version="fs-preview:C:/fake/Neighborhoods",
        households=[
            Household(
                id="N999",
                name="N999",
                funds=0,
                members=[],
                metadata={
                    "kind": "neighborhood_preview",
                    "main_package_exists": False,
                    "characters_dir_exists": False,
                    "lots_dir_exists": False,
                    "character_count": 0,
                    "lot_count": 0,
                },
            )
        ],
        sims=[],
        relationships=[],
        metadata={
            "source_kind": "folder_preview",
            "neighborhood_manager_exists": False,
        },
    )

    issues = validate_savegame(save)
    codes = {issue.code for issue in issues}

    assert "PREVIEW_MISSING_NEIGHBORHOOD_MANAGER" in codes
    assert "PREVIEW_MISSING_MAIN_PACKAGE" in codes
    assert "PREVIEW_MISSING_CHARACTERS_DIR" in codes
    assert "PREVIEW_MISSING_LOTS_DIR" in codes
    assert "PREVIEW_NO_CHARACTER_PACKAGES" in codes
    assert "PREVIEW_NO_LOT_PACKAGES" in codes


def test_issue_helpers_summarize_and_group() -> None:
    save = SaveGame(
        version="0.1",
        households=[Household(id="hh-1", name="Test HH", funds=-5, members=["missing"])],
        sims=[],
        relationships=[],
    )

    issues = validate_savegame(save)
    summary = summarize_issues(issues)
    grouped = group_issues_by_entity(issues)

    assert summary["total"] == len(issues)
    assert summary["warning"] >= 1
    assert summary["error"] >= 1
    assert "hh-1" in grouped


def test_validate_detects_duplicate_neighborhood_and_lot_ids() -> None:
    save = SaveGame(
        version="0.1",
        neighborhoods=[
            Neighborhood(id="N001", name="One"),
            Neighborhood(id="N001", name="Two"),
        ],
        lots=[
            Lot(id="lot-1", name="Lot A", neighborhood_id="N001"),
            Lot(id="lot-1", name="Lot B", neighborhood_id="N001"),
        ],
    )

    issues = validate_savegame(save)
    codes = {issue.code for issue in issues}

    assert "NEIGHBORHOOD_DUPLICATE_ID" in codes
    assert "LOT_DUPLICATE_ID" in codes
