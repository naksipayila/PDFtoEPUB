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
