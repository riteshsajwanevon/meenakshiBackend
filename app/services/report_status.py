"""Report status state machine. All status changes go through `transition`."""

from app.core.errors import ConflictError
from app.models import Report
from app.models.enums import ReportStatus as S

ALLOWED_TRANSITIONS: dict[S, set[S]] = {
    S.UPLOADED: {S.PROCESSING},
    S.PROCESSING: {S.OCR_COMPLETED, S.FAILED},
    S.OCR_COMPLETED: {S.VALIDATION_REQUIRED},
    S.FAILED: {S.PROCESSING},
    S.VALIDATION_REQUIRED: {S.VALIDATED},
    S.VALIDATED: {S.APPROVED, S.VALIDATION_REQUIRED},
    S.APPROVED: set(),
}


def transition(report: Report, target: S) -> None:
    if target not in ALLOWED_TRANSITIONS[report.status]:
        raise ConflictError(f"A report in status {report.status} cannot move to {target}")
    report.status = target
