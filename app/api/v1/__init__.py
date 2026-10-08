from fastapi import APIRouter

from app.api.v1 import activity, auth, master_data, reports, templates, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(reports.router)
api_router.include_router(templates.router)
api_router.include_router(users.router)
api_router.include_router(master_data.router)
api_router.include_router(activity.dashboard_router)
api_router.include_router(activity.audit_router)
api_router.include_router(activity.notifications_router)
api_router.include_router(activity.settings_router)
