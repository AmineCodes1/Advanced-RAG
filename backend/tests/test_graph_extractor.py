import json

from ingestion.graph_extractor import extract_triplets


class FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, **kwargs):
        return {"response": self.response}


def test_extract_triplets_parses_json_and_adds_provenance() -> None:
    triplets = extract_triplets(
        "Alice works for Acme.",
        "document.pdf",
        3,
        client=FakeClient(
            json.dumps(
                [
                    {
                        "subject": "Alice",
                        "relation": "works_for",
                        "object": "Acme",
                        "confidence": 0.9,
                    }
                ]
            )
        ),
    )

    assert triplets[0].source_doc == "document.pdf"
    assert triplets[0].source_page == 3
    assert triplets[0].confidence == 0.9


def test_extract_triplets_rejects_invalid_response() -> None:
    assert extract_triplets("No facts.", "document.pdf", None, client=FakeClient("{}")) == []


def test_extract_triplets_accepts_single_object_response() -> None:
    triplets = extract_triplets(
        "Alice works for Acme.",
        "document.pdf",
        None,
        client=FakeClient(
            '{"subject":"Alice","relation":"works_for","object":"Acme","confidence":0.8}'
        ),
    )

    assert len(triplets) == 1
