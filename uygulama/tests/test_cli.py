from app.cli import build_parser, main
from app.core.config import ConversionOptions


def test_cli_converts_pdf(sample_pdf, tmp_path) -> None:
    output = tmp_path / "cli-output.epub"

    result = main([str(sample_pdf), "--output", str(output)])

    assert result == 0
    assert output.is_file()


def test_cli_defaults_to_text_pages_without_inline_images() -> None:
    parser = build_parser()

    assert not parser.parse_args(["book.pdf"]).include_images
    assert parser.parse_args(["book.pdf", "--include-images"]).include_images


def test_conversion_options_preserve_existing_positional_arguments() -> None:
    options = ConversionOptions(False, "eng", True)

    assert not options.use_ocr
    assert options.ocr_language == "eng"
    assert options.include_images
