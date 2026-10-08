from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

MAX_PAGE_SIZE = 100


def normalize_page(page: int, size: int) -> tuple[int, int]:
    """Clamp paging input instead of rejecting it: page >= 0 and 1 <= size <= 100."""
    return max(page, 0), min(max(size, 1), MAX_PAGE_SIZE)


def count_rows(db: Session, stmt: Select) -> int:
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
