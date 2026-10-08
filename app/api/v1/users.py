from fastapi import APIRouter

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.schemas.common import PageResponse
from app.schemas.user import CreateUserRequest, CreateUserResponse, DepartmentView, UpdateUserRequest, UserStats, UserView
from app.services import user_service

router = APIRouter(tags=["Users & departments"])


@router.get("/users", response_model=PageResponse[UserView])
def list_users(db: DbSession, _: AdminUser, q: str | None = None, role: str | None = None, page: int = 0, size: int = 20):
    return user_service.list_users(db, q=q, role=role, page=page, size=size)


@router.get("/users/stats", response_model=UserStats)
def user_stats(db: DbSession, _: AdminUser):
    return user_service.user_stats(db)


@router.post("/users", response_model=CreateUserResponse)
def create_user(body: CreateUserRequest, db: DbSession, admin: AdminUser):
    return user_service.create_user(db, admin, body)


@router.patch("/users/{user_id}", response_model=UserView)
def update_user(user_id: int, body: UpdateUserRequest, db: DbSession, admin: AdminUser):
    return user_service.update_user(db, admin, user_id, body)


@router.get("/departments", response_model=list[DepartmentView])
def list_departments(db: DbSession, _: CurrentUser):
    return user_service.list_departments(db)
