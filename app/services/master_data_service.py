"""Master list of documents per department (shop), read from app/data/master_documents.json.

The file is the single source of truth: edit it and restart the server to change the list.
"""

from functools import lru_cache
from pathlib import Path

from app.core.errors import NotFoundError
from app.schemas.master_data import MasterDepartment, MasterDocumentList

MASTER_DOCUMENTS_FILE = Path(__file__).resolve().parents[1] / "data" / "master_documents.json"


@lru_cache
def load_master_documents() -> MasterDocumentList:
    """Parsed and checked once, then cached. Raises ValueError if the file is malformed."""
    data = MasterDocumentList.model_validate_json(MASTER_DOCUMENTS_FILE.read_text(encoding="utf-8"))
    _check_unique_codes(data)
    return data


def get_department(code: str) -> MasterDepartment:
    for department in load_master_documents().departments:
        if department.code == code.strip().upper():
            return department
    raise NotFoundError(f"Department '{code}' not found in the master document list")


def _check_unique_codes(data: MasterDocumentList) -> None:
    department_codes = [department.code for department in data.departments]
    if len(department_codes) != len(set(department_codes)):
        raise ValueError(f"{MASTER_DOCUMENTS_FILE.name}: department codes must be unique")
    for department in data.departments:
        document_codes = [document.code for document in department.documents]
        if len(document_codes) != len(set(document_codes)):
            raise ValueError(f"{MASTER_DOCUMENTS_FILE.name}: document codes must be unique within {department.code}")
