"""Transactional editing of source-page-linked text inside generated EPUB files."""

from __future__ import annotations

import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from posixpath import normpath
from xml.etree import ElementTree

from app.core.errors import ValidationError
from app.epub.validator import validate_epub

_XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
_EPUB_NAMESPACE = "http://www.idpf.org/2007/ops"
_PADDING = re.compile(r"^(\s*)(.*?)(\s*)$", re.DOTALL)
_MODIFIED = re.compile(
    rb'(<meta\s+property=["\']dcterms:modified["\']>)[^<]*(</meta>)'
)
ElementTree.register_namespace("", _XHTML_NAMESPACE)
ElementTree.register_namespace("epub", _EPUB_NAMESPACE)


@dataclass(frozen=True, slots=True)
class ReviewEntry:
    """One editable XHTML text slot associated with a source PDF page."""

    key: str
    page_number: int
    kind: str
    text: str


@dataclass(slots=True)
class _TextSlot:
    element: ElementTree.Element
    attribute: str
    prefix: str
    suffix: str
    page_number: int
    kind: str


class EpubTextReview:
    """Load, edit, validate, and atomically republish an EPUB's visible text."""

    def __init__(self, epub_path: Path) -> None:
        self.epub_path = epub_path.expanduser().resolve()
        self._entries: dict[str, bytes] = {}
        self._entry_order: list[str] = []
        self._chapter_roots: dict[str, ElementTree.Element] = {}
        self._slots: dict[str, _TextSlot] = {}
        validate_epub(self.epub_path)
        try:
            with zipfile.ZipFile(self.epub_path) as archive:
                self._entry_order = archive.namelist()
                self._entries = {name: archive.read(name) for name in self._entry_order}
            self._load_chapters()
        except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError) as error:
            raise ValidationError(f"EPUB inceleme için açılamadı: {error}") from error

    @property
    def pages(self) -> list[int]:
        return sorted({slot.page_number for slot in self._slots.values()})

    def entries_for_page(self, page_number: int) -> list[ReviewEntry]:
        return [
            ReviewEntry(key, slot.page_number, slot.kind, self._slot_value(slot).strip())
            for key, slot in self._slots.items()
            if slot.page_number == page_number
        ]

    def update(self, key: str, text: str) -> None:
        slot = self._slots[key]
        value = f"{slot.prefix}{text.strip()}{slot.suffix}"
        setattr(slot.element, slot.attribute, value)

    def save(self) -> None:
        """Validate a corrected candidate before replacing the original EPUB."""
        self._synchronize_navigation()
        self._update_modified_time()
        for name, root in self._chapter_roots.items():
            self._entries[name] = _serialize_xhtml(root)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{self.epub_path.stem}-review-",
                suffix=".epub.tmp",
                dir=self.epub_path.parent,
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
            self._write_archive(temporary_path)
            with temporary_path.open("rb+") as staged:
                os.fsync(staged.fileno())
            validate_epub(temporary_path)
            temporary_path.replace(self.epub_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _load_chapters(self) -> None:
        counter = 0

        def visit(element: ElementTree.Element, inherited_page: int | None) -> None:
            nonlocal counter
            raw_pages = element.get("data-source-pages") or element.get("data-source-page")
            source_pages = [
                int(value)
                for value in (raw_pages or "").split(",")
                if value.strip().isdigit()
            ]
            page_number = source_pages[0] if source_pages else inherited_page
            kind = _local_name(element.tag)
            if page_number is not None and element.text and element.text.strip():
                counter += 1
                self._slots[f"text-{counter}"] = _make_slot(
                    element, "text", element.text, page_number, kind
                )
                for additional_page in source_pages[1:]:
                    counter += 1
                    self._slots[f"text-{counter}"] = _make_slot(
                        element, "text", element.text, additional_page, kind
                    )
            for child in element:
                visit(child, page_number)
                if page_number is not None and child.tail and child.tail.strip():
                    counter += 1
                    self._slots[f"text-{counter}"] = _make_slot(
                        child, "tail", child.tail, page_number, kind
                    )

        for name, data in self._entries.items():
            if not name.startswith("EPUB/chapters/") or not name.endswith(".xhtml"):
                continue
            root = ElementTree.fromstring(data)
            self._chapter_roots[name] = root
            visit(root, None)

    def _synchronize_navigation(self) -> None:
        navigation_data = self._entries.get("EPUB/nav.xhtml")
        if navigation_data is None:
            return
        navigation = ElementTree.fromstring(navigation_data)
        targets: dict[str, str] = {}
        for chapter_name, chapter in self._chapter_roots.items():
            relative_path = chapter_name.removeprefix("EPUB/")
            first_heading = ""
            for element in chapter.iter():
                local_name = _local_name(element.tag)
                if local_name not in {"h1", "h2", "h3", "h4"}:
                    continue
                text = " ".join("".join(element.itertext()).split())
                identifier = element.get("id")
                if not first_heading and local_name == "h1":
                    first_heading = text
                if identifier:
                    targets[f"{relative_path}#{identifier}"] = text
            if first_heading:
                targets[relative_path] = first_heading
                title = chapter.find(f".//{{{_XHTML_NAMESPACE}}}title")
                if title is not None:
                    title.text = first_heading

        for link in navigation.iter(f"{{{_XHTML_NAMESPACE}}}a"):
            href = link.get("href", "")
            target = normpath(href.split("#", maxsplit=1)[0])
            fragment = href.split("#", maxsplit=1)[1] if "#" in href else ""
            key = f"{target}#{fragment}" if fragment else target
            if key in targets:
                link.text = targets[key]
        self._entries["EPUB/nav.xhtml"] = _serialize_xhtml(navigation)

    def _write_archive(self, destination: Path) -> None:
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "mimetype", self._entries["mimetype"], compress_type=zipfile.ZIP_STORED
            )
            for name in self._entry_order:
                if name == "mimetype":
                    continue
                archive.writestr(name, self._entries[name])

    def _update_modified_time(self) -> None:
        opf = self._entries.get("EPUB/content.opf")
        if opf is None:
            return
        modified = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self._entries["EPUB/content.opf"] = _MODIFIED.sub(
            lambda match: match.group(1) + modified.encode("ascii") + match.group(2),
            opf,
            count=1,
        )

    @staticmethod
    def _slot_value(slot: _TextSlot) -> str:
        return getattr(slot.element, slot.attribute) or ""


def _make_slot(
    element: ElementTree.Element,
    attribute: str,
    value: str,
    page_number: int,
    kind: str,
) -> _TextSlot:
    match = _PADDING.match(value)
    prefix, _, suffix = match.groups() if match else ("", value, "")
    return _TextSlot(element, attribute, prefix, suffix, page_number, kind)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _serialize_xhtml(root: ElementTree.Element) -> bytes:
    serialized = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    declaration, body = serialized.split(b"?>", maxsplit=1)
    return declaration + b"?>\n<!DOCTYPE html>" + body
