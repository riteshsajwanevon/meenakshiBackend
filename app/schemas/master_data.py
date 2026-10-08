from app.schemas.common import ApiModel


class MasterDocument(ApiModel):
    s_no: int
    code: str
    name: str


class MasterDepartment(ApiModel):
    code: str
    name: str  # the shop name from the master list
    documents: list[MasterDocument]


class MasterDocumentList(ApiModel):
    title: str
    departments: list[MasterDepartment]
