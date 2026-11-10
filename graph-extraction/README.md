# Graph extraction

This directory contains the Google Colab notebook used for offline entity and
relation extraction. Keeping extraction offline avoids consuming local GPU VRAM
during normal GraphRAG queries.

## Flow

1. Open `extraction_triplets.ipynb` in Google Colab with a free T4 runtime.
2. Upload text or PDF-derived text files, or mount Google Drive.
3. Run all cells and download `triplets.json`.
4. Copy the JSON to `backend/graph_import/data/triplets.json`.
5. Start Neo4j with `docker/docker-compose.yml`.
6. Run `uv run python -m graph_import.import_triplets graph_import/data/triplets.json`
   from the `backend` directory.
7. Use `verify_queries.cypher` in Neo4j Browser to inspect the imported graph.

The JSON contract is:

```json
[
  {
    "subject": "Alice",
    "relation": "works_for",
    "object": "Acme",
    "confidence": 0.91,
    "source_doc": "example.txt",
    "source_page": null
  }
]
```

The importer normalizes entity names and uses `MERGE`, so importing the same
file repeatedly does not create duplicate entity or relationship records.
