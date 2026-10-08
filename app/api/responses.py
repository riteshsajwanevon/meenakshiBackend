from typing import Literal
from urllib.parse import quote

from fastapi import Response


def file_response(data: bytes, media_type: str, filename: str, disposition: Literal["inline", "attachment"]) -> Response:
    return Response(content=data, media_type=media_type, headers={"Content-Disposition": content_disposition(disposition, filename)})


def content_disposition(disposition: str, filename: str) -> str:
    """Content-Disposition with an ASCII fallback plus the exact UTF-8 name (RFC 6266)."""
    ascii_name = filename.encode("ascii", "replace").decode("ascii").replace('"', "'").replace("?", "_")
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
