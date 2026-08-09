"""Internal EPUB package validation with optional external epubcheck support."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from posixpath import normpath
from xml.etree import ElementTree

from app.core.errors import ValidationError


def validate_epub(path: Path, run_epubcheck: bool = False) -> list[str]:
    """Validate required EPUB files, manifest references, spine, and XHTML well-formedness."""
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if not names or names[0] != "mimetype":
                raise ValidationError("EPUB mimetype must be the first archive entry.")
            mimetype_info = archive.getinfo("mimetype")
            if mimetype_info.compress_type != zipfile.ZIP_STORED:
                raise ValidationError("EPUB mimetype must not be compressed.")
            if archive.read("mimetype") != b"application/epub+zip":
                raise ValidationError("Invalid EPUB mimetype.")
            _require(names, "META-INF/container.xml")
            container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
            rootfile = container.find(
                ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
            )
            if rootfile is None or not rootfile.get("full-path"):
                raise ValidationError("container.xml has no OPF rootfile.")
            opf_path = rootfile.get("full-path")
            _require(names, opf_path)
            package = ElementTree.fromstring(archive.read(opf_path))
            namespace = {"opf": "http://www.idpf.org/2007/opf"}
            manifest = package.find("opf:manifest", namespace)
            spine = package.find("opf:spine", namespace)
            if manifest is None or spine is None:
                raise ValidationError("OPF is missing manifest or spine.")
            items = {item.get("id", ""): item for item in manifest.findall("opf:item", namespace)}
            if not items:
                raise ValidationError("OPF manifest is empty.")
            opf_dir = Path(opf_path).parent
            for item in items.values():
                href = item.get("href")
                if not href:
                    raise ValidationError("OPF manifest item has no href.")
                _require(names, (opf_dir / href).as_posix())
            for itemref in spine.findall("opf:itemref", namespace):
                if itemref.get("idref") not in items:
                    raise ValidationError("OPF spine references an unknown manifest item.")
            for item in items.values():
                if item.get("media-type") == "application/xhtml+xml":
                    xhtml_path = (opf_dir / item.get("href", "")).as_posix()
                    xhtml = ElementTree.fromstring(archive.read(xhtml_path))
                    _validate_references(names, xhtml_path, xhtml)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ValidationError(f"Invalid EPUB package: {error}") from error

    if run_epubcheck:
        executable = shutil.which("epubcheck")
        if executable is None:
            warnings.append("epubcheck was not found; internal validation was used.")
        else:
            completed = subprocess.run(
                [executable, str(path)], capture_output=True, text=True, check=False
            )
            if completed.returncode != 0:
                raise ValidationError(
                    completed.stderr.strip() or completed.stdout.strip() or "epubcheck failed"
                )
    return warnings


def _require(names: list[str], path: str | None) -> None:
    if not path or path not in names:
        raise ValidationError(f"EPUB is missing required file: {path}")


def _validate_references(
    names: list[str], document_path: str, document: ElementTree.Element
) -> None:
    """Reject broken local media and navigation links from XHTML documents."""
    base_path = Path(document_path).parent.as_posix()
    for element in document.iter():
        for attribute in ("href", "src"):
            reference = element.get(attribute)
            if not reference or reference.startswith(("#", "http:", "https:", "mailto:")):
                continue
            local_path = reference.split("#", maxsplit=1)[0]
            if local_path:
                _require(names, normpath(f"{base_path}/{local_path}"))
