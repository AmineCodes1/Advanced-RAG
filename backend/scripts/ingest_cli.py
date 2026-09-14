from __future__ import annotations

import argparse
import json
import logging

from ingestion.pipeline import ingest_document


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest a PDF into embedded Qdrant")
    parser.add_argument("pdf", help="Path to a PDF document")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = ingest_document(args.pdf)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())