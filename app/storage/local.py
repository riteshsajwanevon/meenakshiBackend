"""Local-disk file storage for uploads and previews (FILE_STORAGE_PATH)."""

import logging
import os
import re
import tempfile
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_FILENAME_LENGTH = 100


class LocalFileStorage:
    """Stores bytes under a root folder. Keys look like "<uuid>/<filename>"."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file first so a crash never leaves a half-written file behind.
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            tmp.write(data)
        os.replace(tmp.name, path)

    def read(self, key: str) -> bytes:
        """Raises FileNotFoundError if the file is missing."""
        return self._path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            path = self._path_for(key)
            path.unlink(missing_ok=True)
            if path.parent != self.root and not any(path.parent.iterdir()):
                path.parent.rmdir()
        except OSError:
            logger.warning("Could not delete stored file %s", key, exc_info=True)

    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Storage key escapes the storage folder: {key!r}")
        return path


@lru_cache
def get_storage() -> LocalFileStorage:
    return LocalFileStorage(settings.FILE_STORAGE_PATH)


def display_filename(filename: str | None) -> str:
    """The file's base name as the user knows it (drops any client-side folder path)."""
    name = re.split(r"[\\/]", filename or "")[-1].strip()
    return name[:255] or "document"


def sanitize_filename(filename: str | None) -> str:
    """A safe name for disk: letters, digits, dot, dash and underscore only."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", display_filename(filename)).strip("._")
    if len(cleaned) > _MAX_FILENAME_LENGTH:
        stem, dot, extension = cleaned.rpartition(".")
        cleaned = (stem[: _MAX_FILENAME_LENGTH - len(extension) - 1] + dot + extension) if dot else cleaned[:_MAX_FILENAME_LENGTH]
    return cleaned or "file"
