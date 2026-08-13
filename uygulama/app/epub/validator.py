"""Internal EPUB package validation with optional external epubcheck support."""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from posixpath import normpath
from xml.etree import ElementTree

from app.core.errors import ValidationError
from app.core.normalizer import is_language_tag

_OPF_NAMESPACE = "http://www.idpf.org/2007/opf"
_DC_NAMESPACE = "http://purl.org/dc/elements/1.1/"
_XML_LANGUAGE = "{http://www.w3.org/XML/1998/namespace}lang"


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
            namespace = {"opf": _OPF_NAMESPACE, "dc": _DC_NAMESPACE}
            metadata = package.find("opf:metadata", namespace)
            manifest = package.find("opf:manifest", namespace)
            spine = package.find("opf:spine", namespace)
            if metadata is None or manifest is None or spine is None:
                raise ValidationError("OPF is missing metadata, manifest, or spine.")
            language = metadata.find("dc:language", namespace)
            if language is None or not (language.text or "").strip():
                raise ValidationError("OPF metadata has no publication language.")
            if not is_language_tag(language.text or ""):
                raise ValidationError("OPF metadata has an invalid publication language.")
            manifest_items = manifest.findall("opf:item", namespace)
            identifiers = [item.get("id", "") for item in manifest_items]
            hrefs = [item.get("href", "") for item in manifest_items]
            if not manifest_items:
                raise ValidationError("OPF manifest is empty.")
            if any(not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
                raise ValidationError("OPF manifest item IDs must be present and unique.")
            if any(not value for value in hrefs) or len(set(hrefs)) != len(hrefs):
                raise ValidationError("OPF manifest hrefs must be present and unique.")
            items = dict(zip(identifiers, manifest_items, strict=True))
            navigation = [
                item
                for item in manifest_items
                if "nav" in (item.get("properties") or "").split()
            ]
            if len(navigation) != 1:
                raise ValidationError("EPUB must declare exactly one navigation document.")
            opf_dir = Path(opf_path).parent
            for item in items.values():
                href = item.get("href")
                if not href:
                    raise ValidationError("OPF manifest item has no href.")
                _require(names, (opf_dir / href).as_posix())
            spine_items = spine.findall("opf:itemref", namespace)
            if not spine_items:
                raise ValidationError("OPF spine is empty.")
            for itemref in spine_items:
                if itemref.get("idref") not in items:
                    raise ValidationError("OPF spine references an unknown manifest item.")
            xhtml_documents: dict[str, ElementTree.Element] = {}
            for item in items.values():
                if item.get("media-type") == "application/xhtml+xml":
                    xhtml_path = (opf_dir / item.get("href", "")).as_posix()
                    xhtml = ElementTree.fromstring(archive.read(xhtml_path))
                    xhtml_documents[xhtml_path] = xhtml
                    if item not in navigation and not (
                        xhtml.get(_XML_LANGUAGE) or xhtml.get("lang")
                    ):
                        raise ValidationError(f"XHTML document has no language: {xhtml_path}")
            for xhtml_path, xhtml in xhtml_documents.items():
                _validate_references(names, xhtml_path, xhtml, xhtml_documents)
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ValidationError(f"Invalid EPUB package: {error}") from error

    if run_epubcheck:
        command = _epubcheck_command(path)
        if command is None:
            raise ValidationError("epubcheck was requested but was not found.")
        else:
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=180,
                )
            except subprocess.TimeoutExpired as error:
                raise ValidationError("epubcheck timed out.") from error
            if completed.returncode != 0:
                raise ValidationError(
                    completed.stderr.strip() or completed.stdout.strip() or "epubcheck failed"
                )
    return warnings


def _require(names: list[str], path: str | None) -> None:
    if not path or path not in names:
        raise ValidationError(f"EPUB is missing required file: {path}")


def _validate_references(
    names: list[str],
    document_path: str,
    document: ElementTree.Element,
    xhtml_documents: dict[str, ElementTree.Element],
) -> None:
    """Reject broken local media and navigation links from XHTML documents."""
    base_path = Path(document_path).parent.as_posix()
    for element in document.iter():
        for attribute in ("href", "src"):
            reference = element.get(attribute)
            if not reference or reference.startswith(
                ("#", "http:", "https:", "mailto:", "tel:")
            ):
                if reference and reference.startswith("#"):
                    _require_fragment(document_path, reference[1:], xhtml_documents)
                continue
            local_path, _, fragment = reference.partition("#")
            if local_path:
                target_path = normpath(f"{base_path}/{local_path}")
                _require(names, target_path)
                if fragment and target_path in xhtml_documents:
                    _require_fragment(target_path, fragment, xhtml_documents)


def _require_fragment(
    document_path: str,
    fragment: str,
    xhtml_documents: dict[str, ElementTree.Element],
) -> None:
    document = xhtml_documents.get(document_path)
    if document is None or not any(element.get("id") == fragment for element in document.iter()):
        raise ValidationError(f"XHTML reference has no target: {document_path}#{fragment}")


def epubcheck_available() -> bool:
    """Return whether an executable or configured EPUBCheck JAR can run."""
    return _epubcheck_command(Path("book.epub")) is not None


def _epubcheck_command(path: Path) -> list[str] | None:
    executable = shutil.which("epubcheck")
    if executable is not None:
        return [executable, str(path)]
    jar_value = os.environ.get("EPUBCHECK_JAR")
    java = shutil.which("java")
    if jar_value and java and Path(jar_value).is_file():
        return [java, "-jar", jar_value, str(path)]
    return None
