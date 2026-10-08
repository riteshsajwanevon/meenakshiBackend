"""Client for the separate OCR service: POST {OCR_SERVICE_URL}/v1/ocr/extract (multipart).

The backend sends the original file plus a TemplatePayload describing where each field sits;
the service answers with an OcrResult listing every field it read.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.common import ApiModel

logger = logging.getLogger(__name__)

DEFAULT_USER_MESSAGE = "We could not read this document. Please try again or upload a clearer scan."
UNAVAILABLE_USER_MESSAGE = "The text recognition service is not available right now. Please try again in a few minutes."
TIMEOUT_USER_MESSAGE = "Reading this document took too long. Please try again."


class OcrServiceError(Exception):
    """The OCR call failed. `reason` is stored on the report for support; `user_message` is shown to the user."""

    def __init__(self, reason: str, user_message: str = DEFAULT_USER_MESSAGE):
        super().__init__(reason)
        self.reason = reason
        self.user_message = user_message


# ---- Request payload ----

class TemplateFieldPayload(ApiModel):
    field_key: str
    label: str
    scope: str
    data_type: str
    required: bool
    column_order: int
    validation_rule: str
    region_x: float | None
    region_y: float | None
    region_width: float | None
    region_height: float | None


class TemplatePayload(ApiModel):
    code: str
    quantity_field_key: str | None
    fields: list[TemplateFieldPayload]


# ---- Response ----

class OcrBoundingBox(ApiModel):
    x: float
    y: float
    width: float
    height: float


class OcrField(ApiModel):
    id: str | None = None
    field_name: str
    label: str | None = None
    value: Any = None  # usually a string, but numbers are accepted too
    raw_value: Any = None
    confidence: float | None = None
    status: str | None = None
    scope: str | None = None
    row_index: int | None = None
    bounding_box: OcrBoundingBox | None = None
    page_index: int | None = None


class OcrResult(ApiModel):
    report_type: str | None = None
    document_id: str | None = None
    engine: str | None = None
    page_count: int | None = None
    fields: list[OcrField] = []


@dataclass(frozen=True)
class OcrResponse:
    result: OcrResult
    raw: dict  # the exact JSON returned, stored in ocr_extractions


def extract(*, content: bytes, filename: str, content_type: str, template: TemplatePayload) -> OcrResponse:
    url = f"{settings.OCR_SERVICE_URL.rstrip('/')}/v1/ocr/extract"
    files = {"file": (filename, content, content_type)}
    data = {"templateCode": template.code, "template": json.dumps(template.model_dump(by_alias=True))}

    logger.info("Calling OCR service for template %s (%d bytes)", template.code, len(content))
    response = _post_with_one_retry(url, files=files, data=data)

    if response.is_error:
        raise OcrServiceError(f"OCR service returned HTTP {response.status_code}: {response.text[:500]}")
    try:
        raw = response.json()
        result = OcrResult.model_validate(raw)
    except (ValueError, ValidationError) as exc:
        raise OcrServiceError(f"OCR service returned an unreadable response: {exc}") from exc

    logger.info("OCR service returned %d fields (engine=%s)", len(result.fields), result.engine)
    return OcrResponse(result=result, raw=raw)


def _post_with_one_retry(url: str, *, files: dict, data: dict) -> httpx.Response:
    """Retries once when the connection itself fails; never retries a request the service already received."""
    timeout = httpx.Timeout(connect=10.0, read=settings.OCR_TIMEOUT_SECONDS, write=60.0, pool=10.0)
    for attempt in (1, 2):
        try:
            with httpx.Client(timeout=timeout) as client:
                return client.post(url, files=files, data=data)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            if attempt == 2:
                raise OcrServiceError(f"Could not connect to OCR service at {url}: {exc}", UNAVAILABLE_USER_MESSAGE) from exc
            logger.warning("Could not connect to OCR service (%s); retrying once", exc)
        except httpx.TimeoutException as exc:
            raise OcrServiceError(
                f"OCR service did not answer within {settings.OCR_TIMEOUT_SECONDS:.0f}s", TIMEOUT_USER_MESSAGE
            ) from exc
        except httpx.HTTPError as exc:
            raise OcrServiceError(f"OCR request failed: {exc}") from exc
    raise AssertionError("unreachable")
