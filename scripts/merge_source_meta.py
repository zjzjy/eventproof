"""Sync source metadata into the precomputed fixture without re-running the LLM."""

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "fixtures" / "tongyu" / "sources.json"
PRECOMPUTED_PATH = ROOT / "fixtures" / "tongyu" / "precomputed.json"


def main() -> None:
    sources = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    source_by_id = {doc["id"]: doc for doc in sources["documents"]}
    precomputed = json.loads(PRECOMPUTED_PATH.read_text(encoding="utf-8"))
    for doc in precomputed["documents"]:
        source = source_by_id.get(doc["id"])
        if not source:
            continue
        for key in ("sort_order", "snippets", "time_precision", "occurred_at"):
            if key in source:
                doc[key] = source[key]
    precomputed["meta"]["source_meta_synced_at"] = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    PRECOMPUTED_PATH.write_text(
        json.dumps(precomputed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("synced", len(precomputed["documents"]), "documents")


if __name__ == "__main__":
    main()
