from app.cli import main


def test_cli_converts_pdf(sample_pdf, tmp_path) -> None:
    output = tmp_path / "cli-output.epub"

    result = main([str(sample_pdf), "--output", str(output)])

    assert result == 0
    assert output.is_file()
