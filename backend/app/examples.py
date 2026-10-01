"""Read a local, explicitly prepared held-out snapshot bundle."""
import hashlib
import json
import os
import re
from pathlib import Path

from fastapi import HTTPException


def examples_directory():
    return Path(os.environ.get("CONTENT_EXAMPLES_DIR", Path(__file__).resolve().parents[1] / "data/examples"))


def catalog():
    path = examples_directory() / "catalog.json"
    if not path.exists():
        return {"examples": [], "message": "No example bundle installed. You can still paste your own page."}
    try:
        data = json.loads(path.read_text())
        rows = data["examples"]
        if not re.fullmatch(r"[a-f0-9]{64}", data["manifest_hash"]):
            raise ValueError("Invalid manifest identity")
        if data.get("bundle_version") == 2:
            for row in rows:
                records = row["query_records"]
                digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                if row["query_scope"] != "host" or row["query_record_count"] != len(records) or len(records) != 10 or digest != row["query_set_hash"]:
                    raise ValueError("Invalid host query provenance")
                if any(record["usable"] != (3 <= len(record["query"].strip()) <= 1000) for record in records):
                    raise ValueError("Invalid usable query annotation")
                expected = list(dict.fromkeys(record["query"].strip() for record in records if record["usable"]))
                if row["queries"] != expected or row["unusable_query_count"] != sum(not r["usable"] for r in records):
                    raise ValueError("Invalid deduplicated query set")
        if any(row["split"] != "heldout" or not re.fullmatch(r"[a-f0-9]{64}", row["snapshot_id"]) for row in rows):
            raise ValueError("Invalid held-out catalog")
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "The example catalog is invalid. Rebuild the local bundle.")
    return {"examples": rows, "manifest_hash": data["manifest_hash"], "message": "Saved examples from the host-separated extraction held-out split."}


def load_example(snapshot_id):
    listing = catalog()
    row = next((item for item in listing["examples"] if item["snapshot_id"] == snapshot_id), None)
    if row is None:
        raise HTTPException(404, "Example not found in the held-out catalog.")
    try:
        payload = (examples_directory() / f"{snapshot_id}.txt").read_bytes()
        if hashlib.sha256(payload).hexdigest() != row["payload_hash"]:
            raise ValueError("Snapshot hash mismatch")
        content = payload.decode("utf-8")
    except (OSError, ValueError):
        raise HTTPException(503, "The saved example is missing or changed. Rebuild the local bundle.")
    return {**row, "content": content, "manifest_hash": listing["manifest_hash"]}
