import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class ApiModel(BaseModel):
    """Base for every request/response body: snake_case in Python, camelCase in JSON."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class PageResponse(ApiModel, Generic[T]):
    content: list[T]
    page: int
    size: int
    total_elements: int
    total_pages: int

    @classmethod
    def of(cls, content: list[T], *, page: int, size: int, total: int) -> "PageResponse[T]":
        return cls(content=content, page=page, size=size, total_elements=total, total_pages=math.ceil(total / size))


class MessageResponse(ApiModel):
    message: str
