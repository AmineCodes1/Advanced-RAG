import json

import pytest

from graph_import.import_triplets import load_triplets, normalize_name


def test_normalize_name_is_case_and_whitespace_insensitive() -> None:
    assert normalize_name("  Alice   Smith ") == "alice smith"


def test_load_triplets_validates_contract(tmp_path) -> None:
    path = tmp_path / "triplets.json"
    path.write_text(
        json.dumps(
            [
                {
                    "subject": "Alice",
                    "relation": "works_for",
                    "object": "Acme",
                    "confidence": 0.9,
                    "source_doc": "a.txt",
                    "source_page": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    triplets = load_triplets(path)
    assert triplets[0].subject == "Alice"


def test_load_triplets_rejects_invalid_confidence(tmp_path) -> None:
    path = tmp_path / "triplets.json"
    path.write_text(
        json.dumps(
            [
                {
                    "subject": "Alice",
                    "relation": "works_for",
                    "object": "Acme",
                    "confidence": 2,
                    "source_doc": "a.txt",
                    "source_page": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="confidence"):
        load_triplets(path)
