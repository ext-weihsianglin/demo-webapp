"""Package the frozen held-out snapshots locally; never fetch pages or resample."""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb


def prepare(root: Path, output: Path):
    manifest = json.loads((root / "evaluation/extraction/manifest.json").read_text())
    expected_hash = manifest["manifest_hash"]
    hashed = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    actual_hash = hashlib.sha256(json.dumps(hashed, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError("Frozen manifest hash mismatch")
    train_hosts = {row["hostname"] for row in manifest["snapshots"] if row["split"] == "dev"}
    train_payloads = {row["payload_hash"] for row in manifest["snapshots"] if row["split"] == "dev"}
    if output.exists():
        raise ValueError("Output already exists; use a fresh directory to preserve the bundle.")
    examples, payloads, verified_files = [], [], set()
    connection = duckdb.connect()
    try:
        # Every host prompt can live in any source shard, not just the selected row's shard.
        raw_files = {row["source_file"]: row["source_file_hash"] for row in manifest["snapshots"]}
        for filename, expected in raw_files.items():
            raw = root / filename
            if hashlib.sha256(raw.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Source parquet hash mismatch: {raw.name}")
            verified_files.add((str(raw), expected))
        host_queries = {}
        for hostname in {row["hostname"] for row in manifest["snapshots"] if row["split"] == "heldout"}:
            records = []
            for filename in sorted(raw_files):
                rows = connection.execute("SELECT prompt, href, file_row_number FROM read_parquet(?, file_row_number=true) WHERE hostname = ? ORDER BY file_row_number", [str(root / filename), hostname]).fetchall()
                for prompt, href, number in rows:
                    query = (prompt or "").strip()
                    records.append({"query": query, "href": href, "source_file": filename,
                                    "source_row": number, "usable": 3 <= len(query) <= 1000})
            if len(records) != 10:
                raise ValueError(f"Expected ten frozen observations for host {hostname}, got {len(records)}")
            host_queries[hostname] = records
        for row in manifest["snapshots"]:
            if row["split"] != "heldout":
                continue
            if row["hostname"] in train_hosts or row["payload_hash"] in train_payloads:
                raise ValueError("Development/held-out overlap")
            identity = row["snapshot_id"]
            payload = (root / f"data/evaluation/{identity}.txt").read_bytes()
            if hashlib.sha256(payload).hexdigest() != row["payload_hash"]:
                raise ValueError(f"Snapshot hash mismatch: {identity}")
            raw = root / row["source_file"]
            file_identity = (str(raw), row["source_file_hash"])
            if file_identity not in verified_files:
                if hashlib.sha256(raw.read_bytes()).hexdigest() != row["source_file_hash"]:
                    raise ValueError(f"Source parquet hash mismatch: {raw.name}")
                verified_files.add(file_identity)
            source = connection.execute("SELECT prompt, href, hostname, html_content FROM read_parquet(?, file_row_number=true) WHERE file_row_number = ?", [str(raw), row["source_row"]]).fetchone()
            if source is None or source[1] != row["href"] or source[2] != row["hostname"] or source[3].encode() != payload:
                raise ValueError(f"Source row mismatch: {identity}")
            sidecar = json.loads((root / f"data/evaluation/{identity}.source.json").read_text())
            examples.append({"snapshot_id": identity, "payload_hash": row["payload_hash"], "href": row["href"], "hostname": row["hostname"], "format": row["format"], "split": "heldout", "title": sidecar.get("title") or row["href"], "query": source[0], "characters": len(payload.decode()),
                             "queries": list(dict.fromkeys(record["query"] for record in host_queries[row["hostname"]] if record["usable"])),
                             "query_records": host_queries[row["hostname"]], "query_scope": "host",
                             "query_record_count": len(host_queries[row["hostname"]]),
                             "unusable_query_count": sum(not record["usable"] for record in host_queries[row["hostname"]]),
                             "query_set_hash": hashlib.sha256(json.dumps(host_queries[row["hostname"]], sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
            payloads.append((identity, payload))
    finally:
        connection.close()
    output.mkdir(parents=True)
    for identity, payload in payloads:
        (output / f"{identity}.txt").write_bytes(payload)
    (output / "catalog.json").write_text(json.dumps({"bundle_version": 2, "manifest_hash": expected_hash, "examples": sorted(examples, key=lambda row: row["hostname"])}, indent=2))
    print(f"Prepared {len(examples)} held-out examples in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/examples")
    args = parser.parse_args()
    prepare(args.research_root, args.output)
