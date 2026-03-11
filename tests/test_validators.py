from s2saveforge.core.models import Household, Relationship, SaveGame, Sim
from s2saveforge.core.validators import validate_savegame


def test_validate_detects_invalid_references_and_ranges() -> None:
    save = SaveGame(
        version="0.1",
        households=[Household(id="hh-1", name="Test HH", funds=-5, members=["sim-missing"])],
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
    assert "RELATIONSHIP_UNKNOWN_SIM" in codes
