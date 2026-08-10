"""Standards-oriented EPUB 3 package builder independent of PDF libraries."""

from __future__ import annotations

import html
import logging
import shutil
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from app.core.config import ConversionOptions
from app.core.models import (
    Chapter,
    ContentElement,
    Footnote,
    Heading,
    ImageAsset,
    ImageBlock,
    ListBlock,
    Paragraph,
    SemanticDocument,
    TableBlock,
)
from app.epub.css import stylesheet

LOGGER = logging.getLogger(__name__)
_CONTAINER_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">
  <rootfiles><rootfile full-path=\"EPUB/content.opf\" media-type=\"application/oebps-package+xml\"/></rootfiles>
</container>
"""


class EpubBuilder:
    """Write a portable reflowable EPUB 3 archive from semantic content."""

    def build(
        self, document: SemanticDocument, output_path: Path, options: ConversionOptions
    ) -> None:
        """Build, atomically publish, and leave validation to the caller."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pdf_to_epub_build_") as temporary:
            root = Path(temporary)
            epub_root = root / "EPUB"
            chapters_dir = epub_root / "chapters"
            images_dir = epub_root / "images"
            chapters_dir.mkdir(parents=True)
            images_dir.mkdir(parents=True)
            (root / "mimetype").write_bytes(b"application/epub+zip")
            meta_inf = root / "META-INF"
            meta_inf.mkdir()
            (meta_inf / "container.xml").write_text(_CONTAINER_XML, encoding="utf-8")
            (epub_root / "styles.css").write_text(
                stylesheet(options.css_style_mode), encoding="utf-8"
            )

            image_paths = self._write_images(document.assets, images_dir, options.optimize_images)
            chapter_paths = self._write_chapters(document.chapters, chapters_dir, image_paths)
            (epub_root / "nav.xhtml").write_text(
                self._nav_xhtml(document, chapter_paths), encoding="utf-8"
            )
            (epub_root / "content.opf").write_text(
                self._opf(document, chapter_paths, image_paths), encoding="utf-8"
            )
            archive_path = root / "book.epub"
            self._zip(root, archive_path)
            temporary_output = output_path.with_suffix(f"{output_path.suffix}.tmp")
            shutil.copyfile(archive_path, temporary_output)
            temporary_output.replace(output_path)

    def _write_images(
        self,
        assets: dict[str, ImageAsset],
        images_dir: Path,
        optimize: bool,
    ) -> dict[str, tuple[str, str]]:
        paths: dict[str, tuple[str, str]] = {}
        for asset_id, asset in assets.items():
            filename, media_type = self._copy_image(asset, images_dir, optimize)
            paths[asset_id] = (filename, media_type)
        return paths

    @staticmethod
    def _copy_image(asset: ImageAsset, destination_dir: Path, optimize: bool) -> tuple[str, str]:
        extension = asset.extension
        filename = f"{asset.id}.{extension}"
        destination = destination_dir / filename
        if not optimize:
            shutil.copyfile(asset.file_path, destination)
            return filename, asset.media_type
        try:
            with Image.open(asset.file_path) as image:
                if extension in {"jpg", "jpeg", "jpx", "jp2", "j2k"}:
                    filename = f"{asset.id}.jpg"
                    destination = destination_dir / filename
                    image.convert("RGB").save(destination, format="JPEG", quality=88, optimize=True)
                    return filename, "image/jpeg"
                if extension == "png":
                    image.save(destination, format="PNG", optimize=True)
                    return filename, "image/png"
                filename = f"{asset.id}.png"
                image.convert("RGBA").save(destination_dir / filename, format="PNG", optimize=True)
                return filename, "image/png"
        except (OSError, ValueError) as error:
            LOGGER.warning("Could not optimize %s: %s", asset.file_path.name, error)
            shutil.copyfile(asset.file_path, destination)
            return filename, asset.media_type

    @staticmethod
    def _write_chapters(
        chapters: list[Chapter],
        destination_dir: Path,
        image_paths: dict[str, tuple[str, str]],
    ) -> list[str]:
        paths: list[str] = []
        for index, chapter in enumerate(chapters, start=1):
            filename = f"chapter_{index:03d}.xhtml"
            xhtml = _chapter_xhtml(chapter, index, image_paths)
            (destination_dir / filename).write_text(xhtml, encoding="utf-8")
            paths.append(f"chapters/{filename}")
        return paths

    @staticmethod
    def _zip(root: Path, destination: Path) -> None:
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(root / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
            for path in sorted(root.rglob("*")):
                if path.is_dir() or path.name == "mimetype" or path == destination:
                    continue
                archive.write(path, path.relative_to(root).as_posix())

    @staticmethod
    def _nav_xhtml(document: SemanticDocument, chapter_paths: list[str]) -> str:
        entries: list[str] = []
        for index, (chapter, path) in enumerate(
            zip(document.chapters, chapter_paths, strict=True), start=1
        ):
            children = [
                element
                for element in chapter.elements
                if isinstance(element, Heading) and element.level > 1
            ]
            child_nav = ""
            if children:
                links = "".join(
                    f'<li><a href="{html.escape(path)}#heading-{index}-{item_index}">{html.escape(item.text)}</a></li>'
                    for item_index, item in enumerate(chapter.elements)
                    if isinstance(item, Heading) and item.level > 1
                )
                child_nav = f"<ol>{links}</ol>"
            entries.append(
                f'<li><a href="{html.escape(path)}">{html.escape(chapter.title)}</a>{child_nav}</li>'
            )
        title = html.escape(document.metadata.title)
        return f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<!DOCTYPE html>
<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" xml:lang=\"{html.escape(document.metadata.language)}\">
<head><title>Contents</title><link rel=\"stylesheet\" type=\"text/css\" href=\"styles.css\"/></head>
<body><nav epub:type=\"toc\" id=\"toc\"><h1>{title}</h1><ol>{"".join(entries)}</ol></nav></body></html>"""

    @staticmethod
    def _opf(
        document: SemanticDocument,
        chapter_paths: list[str],
        image_paths: dict[str, tuple[str, str]],
    ) -> str:
        metadata = document.metadata
        identifier = uuid.uuid5(
            uuid.NAMESPACE_URL, f"pdf-to-epub:{metadata.title}:{metadata.author}"
        )
        modified = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        manifest = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="css" href="styles.css" media-type="text/css"/>',
        ]
        manifest.extend(
            f'<item id="chapter-{index}" href="{path}" media-type="application/xhtml+xml"/>'
            for index, path in enumerate(chapter_paths, start=1)
        )
        for asset_id, (filename, media_type) in image_paths.items():
            properties = ' properties="cover-image"' if asset_id == document.cover_asset_id else ""
            manifest.append(
                f'<item id="{html.escape(asset_id)}" href="images/{html.escape(filename)}" media-type="{media_type}"{properties}/>'
            )
        spine = "".join(
            f'<itemref idref="chapter-{index}"/>' for index in range(1, len(chapter_paths) + 1)
        )
        subject = (
            f"<dc:subject>{html.escape(metadata.subject)}</dc:subject>" if metadata.subject else ""
        )
        publisher = (
            f"<dc:publisher>{html.escape(metadata.publisher)}</dc:publisher>"
            if metadata.publisher
            else ""
        )
        description = (
            f"<dc:description>{html.escape(metadata.description)}</dc:description>"
            if metadata.description
            else ""
        )
        isbn = (
            f'<dc:identifier id="isbn">{html.escape(metadata.isbn)}</dc:identifier>'
            if metadata.isbn
            else ""
        )
        return f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"pub-id\" xml:lang=\"{html.escape(metadata.language)}\" prefix=\"dcterms: http://purl.org/dc/terms/\">
  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">
    <dc:identifier id=\"pub-id\">urn:uuid:{identifier}</dc:identifier>{isbn}
    <dc:title>{html.escape(metadata.title)}</dc:title>
    <dc:creator>{html.escape(metadata.author or "Unknown")}</dc:creator>
    <dc:language>{html.escape(metadata.language or "en")}</dc:language>{publisher}{description}{subject}
    <meta property=\"dcterms:modified\">{modified}</meta>
  </metadata>
  <manifest>{"".join(manifest)}</manifest>
  <spine>{spine}</spine>
</package>"""


def _chapter_xhtml(
    chapter: Chapter,
    chapter_index: int,
    image_paths: dict[str, tuple[str, str]],
) -> str:
    body = "".join(
        _render_element(element, chapter_index, index, image_paths)
        for index, element in enumerate(chapter.elements)
    )
    return f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<!DOCTYPE html>
<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\">
<head><title>{html.escape(chapter.title)}</title><link rel=\"stylesheet\" type=\"text/css\" href=\"../styles.css\"/></head>
<body><section epub:type=\"chapter\">{body}</section></body></html>"""


def _render_element(
    element: ContentElement,
    chapter_index: int,
    element_index: int,
    image_paths: dict[str, tuple[str, str]],
) -> str:
    if isinstance(element, Paragraph):
        return f"<p>{html.escape(element.text)}</p>"
    if isinstance(element, Heading):
        level = min(4, max(1, element.level))
        return f'<h{level} id="heading-{chapter_index}-{element_index}">{html.escape(element.text)}</h{level}>'
    if isinstance(element, ImageBlock):
        image = image_paths.get(element.asset_id)
        if image is None:
            return ""
        alt = html.escape(element.alt_text or element.caption or "Illustration")
        caption = (
            f"<figcaption>{html.escape(element.caption)}</figcaption>" if element.caption else ""
        )
        return (
            f'<figure><img src="../images/{html.escape(image[0])}" alt="{alt}"/>{caption}</figure>'
        )
    if isinstance(element, ListBlock):
        tag = "ol" if element.ordered else "ul"
        return (
            f"<{tag}>{''.join(f'<li>{html.escape(item)}</li>' for item in element.items)}</{tag}>"
        )
    if isinstance(element, TableBlock):
        rows = []
        for row_index, row in enumerate(element.rows):
            cell = "th" if row_index == 0 else "td"
            rows.append(
                f"<tr>{''.join(f'<{cell}>{html.escape(value)}</{cell}>' for value in row)}</tr>"
            )
        return f"<table>{''.join(rows)}</table>"
    if isinstance(element, Footnote):
        identifier = html.escape(element.identifier)
        return f'<aside id="{identifier}" epub:type="footnote"><p>{html.escape(element.text)}</p></aside>'
    return ""
