from backend.app.main import status
from worker.pipeline import JobState


def test_disabled_api_and_terminal_state_contract():
    assert status().repair_enabled is False
    assert JobState.VERIFIED != JobState.DRAFT_PR_CREATED
    assert JobState.NO_REPRODUCIBLE_BUG != JobState.VERIFIED
