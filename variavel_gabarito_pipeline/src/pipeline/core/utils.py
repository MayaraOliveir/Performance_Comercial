"""Funcoes utilitarias compartilhadas."""

from __future__ import annotations

from pathlib import Path


EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}


def list_excel_files(directory: str | Path, recursive: bool = False) -> list[Path]:
    """Lista arquivos Excel validos em uma pasta, ignorando temporarios do Excel."""

    base_dir = Path(directory)
    if not base_dir.exists() or not base_dir.is_dir():
        return []

    iterator = base_dir.rglob("*") if recursive else base_dir.iterdir()
    files = [
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in EXCEL_EXTENSIONS
        and not path.name.startswith("~$")
    ]

    return sorted(files, key=lambda item: item.as_posix().lower())
