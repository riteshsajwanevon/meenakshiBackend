from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.master_data import MasterDepartment, MasterDocumentList
from app.services import master_data_service

router = APIRouter(prefix="/master-data", tags=["Master data"])


@router.get("/documents", response_model=MasterDocumentList)
def list_master_documents(_: CurrentUser):
    """Every department (shop) with its document types."""
    return master_data_service.load_master_documents()


@router.get("/documents/{department_code}", response_model=MasterDepartment)
def get_department_documents(department_code: str, _: CurrentUser):
    """One department's document types, e.g. /master-data/documents/WELD_SHOP."""
    return master_data_service.get_department(department_code)
