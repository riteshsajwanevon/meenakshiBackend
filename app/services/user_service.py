"""Admin user management and departments."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.core.time import start_of_utc_day, utcnow
from app.db.pagination import count_rows, normalize_page
from app.models import Department, Report, Role, User
from app.models.enums import AuditAction, EntityType, RoleCode
from app.schemas.common import PageResponse
from app.schemas.user import CreateUserRequest, CreateUserResponse, DepartmentView, UpdateUserRequest, UserStats, UserView
from app.services import audit_service
from app.services.auth_service import find_user_by_email, revoke_all_refresh_tokens


def _reports_submitted_column():
    return (
        select(func.count(Report.id)).where(Report.uploaded_by_id == User.id).correlate(User).scalar_subquery()
    ).label("reports_submitted")


def list_users(db: Session, *, q: str | None, role: str | None, page: int, size: int) -> PageResponse[UserView]:
    page, size = normalize_page(page, size)
    stmt = select(User, _reports_submitted_column())
    if q and q.strip():
        term = q.strip()
        stmt = stmt.where(or_(User.email.icontains(term, autoescape=True), User.full_name.icontains(term, autoescape=True)))
    if role_code := _parse_role_filter(role):
        stmt = stmt.where(User.roles.any(Role.code == role_code))

    total = count_rows(db, stmt)
    rows = db.execute(stmt.order_by(User.full_name, User.id).offset(page * size).limit(size)).all()
    content = [UserView.from_model(user, reports_submitted) for user, reports_submitted in rows]
    return PageResponse[UserView].of(content, page=page, size=size, total=total)


def user_stats(db: Session) -> UserStats:
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_accounts = db.scalar(select(func.count(User.id)).where(User.active.is_(True))) or 0
    reports_today = db.scalar(select(func.count(Report.id)).where(Report.created_at >= start_of_utc_day(utcnow().date()))) or 0
    # The Java backend reports active accounts for both fields; kept identical for frontend parity.
    return UserStats(total_users=total_users, active_now=active_accounts, active_accounts=active_accounts, reports_today=reports_today)


def create_user(db: Session, actor: User, request: CreateUserRequest) -> CreateUserResponse:
    email = request.email.strip().lower()
    if find_user_by_email(db, email) is not None:
        raise ConflictError("A user with this email already exists")

    temporary_password = security.generate_temporary_password()
    user = User(
        email=email,
        full_name=request.full_name.strip(),
        password_hash=security.hash_password(temporary_password),
        active=True,
        roles=[_get_role(db, request.role)],
    )
    db.add(user)
    db.flush()  # assigns user.id for the audit entry
    audit_service.record(
        db, actor=actor, action=AuditAction.USER_CREATED, entity_type=EntityType.USER, entity_id=user.id,
        details={"email": email, "role": request.role},
    )
    db.commit()
    return CreateUserResponse(user=UserView.from_model(user, reports_submitted=0), temporary_password=temporary_password)


def update_user(db: Session, actor: User, user_id: int, request: UpdateUserRequest) -> UserView:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    if user.id == actor.id and (request.active is False or (request.role and request.role != RoleCode.ADMIN)):
        raise ConflictError("You cannot deactivate your own account or remove your own admin access")

    changes = {}
    if request.full_name is not None:
        user.full_name = request.full_name.strip()
        changes["fullName"] = user.full_name
    if request.role is not None:
        user.roles = [_get_role(db, request.role)]
        changes["role"] = request.role
    if request.active is not None and request.active != user.active:
        user.active = request.active
        changes["active"] = request.active
        if not request.active:
            revoke_all_refresh_tokens(db, user.id)

    if changes:
        audit_service.record(
            db, actor=actor, action=AuditAction.USER_UPDATED, entity_type=EntityType.USER, entity_id=user.id, details=changes
        )
        db.commit()
    reports_submitted = db.scalar(select(func.count(Report.id)).where(Report.uploaded_by_id == user.id)) or 0
    return UserView.from_model(user, reports_submitted)


def list_departments(db: Session) -> list[DepartmentView]:
    departments = db.scalars(select(Department).where(Department.active.is_(True)).order_by(Department.name))
    return [DepartmentView.model_validate(department) for department in departments]


def _get_role(db: Session, code: RoleCode) -> Role:
    role = db.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise NotFoundError(f"Role {code} is not set up in the database")
    return role


def _parse_role_filter(role: str | None) -> RoleCode | None:
    if role is None or not role.strip() or role.strip().upper() == "ALL":
        return None
    try:
        return RoleCode(role.strip().upper())
    except ValueError:
        raise BadRequestError(f"Unknown role '{role}'. Use one of: ALL, {', '.join(RoleCode)}") from None
