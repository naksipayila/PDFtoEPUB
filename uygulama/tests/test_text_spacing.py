from app.core.normalizer import join_line_text
from app.ocr.engine import _join_ocr_words
from app.pdf.page_parser import _line_text


def test_joins_tightly_split_ocr_word_without_merging_normal_words() -> None:
    data = {
        "text": ["Hü", "manizim", "doğru"],
        "left": [10, 34, 100],
        "width": [22, 60, 45],
        "height": [20, 20, 20],
    }

    assert _join_ocr_words(data, [0, 1, 2]) == "Hümanizim doğru"


def test_rebuilds_native_line_from_character_geometry() -> None:
    line = {
        "spans": [
            {
                "size": 10,
                "chars": [
                    {"c": "H", "bbox": (0, 0, 5, 10)},
                    {"c": "ü", "bbox": (5, 0, 10, 10)},
                    {"c": "m", "bbox": (10.4, 0, 15.4, 10)},
                    {"c": "a", "bbox": (15.4, 0, 20.4, 10)},
                    {"c": "n", "bbox": (20.4, 0, 25.4, 10)},
                    {"c": "i", "bbox": (25.4, 0, 30.4, 10)},
                    {"c": "z", "bbox": (30.4, 0, 35.4, 10)},
                    {"c": "i", "bbox": (35.4, 0, 40.4, 10)},
                    {"c": "m", "bbox": (40.4, 0, 45.4, 10)},
                ],
            }
        ]
    }

    assert _line_text(line) == "Hümanizim"


def test_repairs_hard_and_soft_hyphenated_line_breaks_without_a_space() -> None:
    assert join_line_text("yaşam-", "ının") == "yaşamının"
    assert join_line_text("sosya\u00ad", "lizm") == "sosyalizm"


def test_preserves_a_soft_hyphen_until_the_next_line_is_joined() -> None:
    partial = join_line_text("sosya\u00ad", "lizm\u00ad")

    assert join_line_text(partial, "öncesinde") == "sosyalizmöncesinde"
