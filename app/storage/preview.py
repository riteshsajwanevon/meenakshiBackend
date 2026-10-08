"""Renders a PNG preview of the first page of an uploaded PDF or image."""

import io

import pypdfium2 as pdfium
from PIL import Image, ImageOps

PDF_RENDER_DPI = 150
MAX_PREVIEW_SIDE_PX = 2000


class PreviewError(Exception):
    """The file could not be opened as a PDF or image."""


def render_preview_png(data: bytes, extension: str) -> bytes:
    try:
        image = _render_pdf_first_page(data) if extension == "pdf" else _open_image(data)
        image.thumbnail((MAX_PREVIEW_SIDE_PX, MAX_PREVIEW_SIDE_PX))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except Exception as exc:  # any decoder failure means the upload is unusable
        raise PreviewError(f"Could not render preview from .{extension} file: {exc}") from exc


def _render_pdf_first_page(data: bytes) -> Image.Image:
    pdf = pdfium.PdfDocument(data)
    try:
        if len(pdf) == 0:
            raise PreviewError("PDF has no pages")
        page = pdf[0]
        try:
            return page.render(scale=PDF_RENDER_DPI / 72).to_pil().convert("RGB")
        finally:
            page.close()
    finally:
        pdf.close()


def _open_image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        image.seek(0)  # first frame of multi-page TIFFs
        image = ImageOps.exif_transpose(image)  # respect phone camera rotation
        return image.convert("RGB")
