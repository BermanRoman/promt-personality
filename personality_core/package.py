"""Site archive: a page folder (index.html + assets) and a zip of it, ready to upload as one URL."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from .report import ASSETS, render_report

ASSET_FILES = ("report.css", "scenes.js")
# Только для Apache-хостинга: запрет индексации и кэш ассетов; на других серверах файл безвреден.
HTACCESS = """<IfModule mod_headers.c>
  Header set X-Robots-Tag "noindex, nofollow, noarchive"
  <FilesMatch "\\.(css|js)$">
    Header set Cache-Control "public, max-age=604800"
  </FilesMatch>
</IfModule>
"""
# Фиксированное время в архиве: одинаковые входы дают одинаковый zip.
ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_site(out_dir: str | os.PathLike, calculation: dict, narrative: dict | None = None,
               protected_paths: tuple = (), banner: str | None = None) -> tuple[Path, Path]:
    """Write <out_dir>/ (index.html, assets/, .htaccess, manifest.json) and <out_dir>.zip.

    The folder is built next to the destination and swapped in whole, so an interrupted run never
    leaves a half-written page. Returns (folder, zip).
    """
    destination = Path(out_dir).resolve()
    for protected in protected_paths:
        path = Path(protected).resolve()
        if path == destination or destination in path.parents:
            raise ValueError("site folder must not contain the input files")
    archive_path = destination.with_name(destination.name + ".zip")
    # Перезаписываем только свой прошлый выпуск: пустая или отсутствующая папка либо папка с нашим manifest.json.
    if destination.is_symlink():
        raise ValueError("site folder must not be a symbolic link")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("site path exists and is not a folder")
        if any(destination.iterdir()):
            try:
                previous = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                previous = None
            if not (isinstance(previous, dict) and "calculation_id" in previous and "files" in previous):
                raise ValueError("site folder is not empty and is not a previous report page; choose another path")
    if archive_path.exists() and not destination.exists():
        raise ValueError("an archive with this name already exists next to the folder; choose another path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {
        "index.html": render_report(calculation, narrative, assets="external", banner=banner).encode("utf-8"),
        ".htaccess": HTACCESS.encode("utf-8"),
    }
    for name in ASSET_FILES:
        files[f"assets/{name}"] = (ASSETS / name).read_bytes()
    manifest = {
        "calculation_id": calculation.get("calculation_id"),
        "narrative": narrative is not None,
        "files": {name: {"bytes": len(data), "sha256": _sha256(data)} for name, data in sorted(files.items())},
    }
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    staging = Path(tempfile.mkdtemp(prefix="." + destination.name + ".", dir=destination.parent))
    try:
        os.chmod(staging, 0o755)
        for name, data in files.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.chmod(target, 0o644)
        archive_tmp = staging.parent / (staging.name + ".zip.tmp")
        with zipfile.ZipFile(archive_tmp, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(files):
                info = zipfile.ZipInfo(f"{destination.name}/{name}", ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100644) << 16
                archive.writestr(info, files[name])
        # Старый выпуск сначала отодвигается и удаляется только после успешной замены.
        backup = None
        if destination.exists():
            backup = destination.parent / (staging.name + ".old")
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except OSError:
            if backup is not None:
                os.replace(backup, destination)
            raise
        os.replace(archive_tmp, archive_path)
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        leftover = staging.parent / (staging.name + ".zip.tmp")
        if leftover.exists():
            leftover.unlink()
    return destination, archive_path
