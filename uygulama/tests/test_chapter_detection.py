from app.core.models import Heading, Paragraph
from app.layout.analyzer import build_chapters


def test_builds_chapters_at_primary_headings() -> None:
    chapters = build_chapters(
        [
            Heading("Chapter One", 1),
            Paragraph("First chapter text."),
            Heading("Chapter Two", 1),
            Paragraph("Second chapter text."),
        ],
        detect_chapters=True,
    )

    assert [chapter.title for chapter in chapters] == ["Chapter One", "Chapter Two"]
    assert [len(chapter.elements) for chapter in chapters] == [2, 2]
