from app.epub.css import stylesheet
from app.layout.headings import HeadingDetector
from tests.conftest import source_block


def test_detects_numbered_bold_large_heading() -> None:
    body = [source_block(f"Body line {index}.", y0=100 + index * 15) for index in range(4)]
    heading = source_block("1. Introduction", y0=60, font_size=18, bold=True)
    detector = HeadingDetector([*body, heading])

    assert detector.is_heading(heading)
    assert detector.level(heading) == 1


def test_does_not_classify_long_body_sentence_as_heading() -> None:
    body = source_block(
        "This is an ordinary body sentence which ends with normal punctuation.", font_size=10
    )
    detector = HeadingDetector([body])

    assert not detector.is_heading(body)


def test_does_not_classify_a_modestly_larger_body_line_as_heading() -> None:
    blocks = [
        source_block("First body line", y0=100, y1=112, font_size=10),
        source_block("Possible body line", y0=120, y1=134, font_size=12),
        source_block("Next body line", y0=140, y1=152, font_size=10),
    ]

    assert not HeadingDetector(blocks).is_heading(blocks[1])


def test_detects_an_isolated_large_heading_without_bold_metadata() -> None:
    heading = source_block("A Chapter Heading", y0=40, y1=60, font_size=16)
    body = source_block("Body text follows.", y0=100, y1=112, font_size=10)

    assert HeadingDetector([heading, body]).is_heading(heading)


def test_does_not_classify_same_size_bold_body_text_as_heading() -> None:
    body = source_block("Important sentence", y0=100, y1=112, font_size=10, bold=True)

    assert not HeadingDetector([body]).is_heading(body)


def test_heading_styles_are_explicitly_bold() -> None:
    assert "font-weight: 700" in stylesheet()
