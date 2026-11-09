"""One state vocabulary and transition graph for API services and workers."""

from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    BASELINING = "baselining"
    REPRODUCED = "reproduced"
    REPAIRING = "repairing"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    PUBLISHING = "publishing"
    DRAFT_PR_CREATED = "draft_pr_created"
    NO_REPRODUCIBLE_BUG = "no_reproducible_bug"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureReason(StrEnum):
    ENVIRONMENT = "environment"
    REPRODUCTION = "reproduction"
    MODEL = "model"
    PATCH = "patch"
    VERIFICATION = "verification"
    PUBLISHING = "publishing"
    DEADLINE = "deadline_exceeded"
    RETRIES = "retries_exhausted"
    BUDGET = "budget_exhausted"


TERMINAL = frozenset({JobState.DRAFT_PR_CREATED, JobState.NO_REPRODUCIBLE_BUG,
                      JobState.FAILED, JobState.CANCELLED})
TRANSITIONS = {
    JobState.QUEUED: {JobState.BASELINING},
    JobState.BASELINING: {JobState.REPRODUCED, JobState.NO_REPRODUCIBLE_BUG},
    JobState.REPRODUCED: {JobState.REPAIRING},
    JobState.REPAIRING: {JobState.VERIFYING},
    JobState.VERIFYING: {JobState.VERIFIED, JobState.REPAIRING},
    JobState.VERIFIED: {JobState.PUBLISHING},
    JobState.PUBLISHING: {JobState.DRAFT_PR_CREATED, JobState.VERIFIED},
}


class Conflict(ValueError):
    pass


class NotFound(LookupError):
    pass


class LeaseLost(Conflict):
    pass


class BudgetExceeded(Conflict):
    pass


def check_transition(current: JobState, target: JobState) -> None:
    if current in TERMINAL or (target not in {JobState.FAILED, JobState.CANCELLED}
                              and target not in TRANSITIONS.get(current, set())):
        raise Conflict("Illegal job state transition")
