"""Install the pinned trusted P1 model locally without training or modifying research data."""
import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring import MODEL_SHA256


def prepare(source: Path, output: Path):
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != MODEL_SHA256:
        raise ValueError('Only the pinned P1 v7.1 semantic_context model is supported; source hash mismatch')
    if output.exists():
        raise ValueError('Output exists; use a fresh path to preserve the installed artifact')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print(f'Installed pinned P1 v7.1 model: {MODEL_SHA256}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data/scoring/model.joblib')
    args = parser.parse_args()
    prepare(args.model, args.output)
