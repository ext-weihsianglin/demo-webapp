"""Build the pinned research modules with only import/packaging adaptations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

REVISION = '6a9606d3febaf62f76c8448c44f91a120107e5a6'
REPOSITORY = 'https://github.com/ext-weihsianglin/content-optimization-system'
VERSION = '0.3.0'


def build(uv, output):
    with tempfile.TemporaryDirectory(prefix='content-library-') as temporary:
        root = Path(temporary) / 'source'
        subprocess.run(['git', 'clone', '--quiet', REPOSITORY + '.git', str(root)], check=True)
        subprocess.run(['git', 'checkout', '--quiet', REVISION], cwd=root, check=True)
        manifest = root / 'pyproject.toml'
        text = manifest.read_text().replace('version = "0.1.0"', f'version = "{VERSION}"', 1)
        text = text.replace('[tool.uv]\npackage = false', '''[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["preprocessing", "trad_ml_scorer", "representations", "scripts"]
exclude = ["**/*.html", "**/*.svg", "**/*.png", "trad_ml_scorer/v*", "trad_ml_scorer/interpretation"]
''')
        manifest.write_text(text)
        api = root / 'preprocessing/api.py'
        api.write_text(f'''"""Tuple facade over the exact upstream corpus parser modules."""
from preprocessing.adapters.local import extract_conservative, extract_markdown_text
from preprocessing.downstream import document
from preprocessing.quality import classify_payload, source_inventory
from preprocessing.schema import Snapshot, snapshot_identity
from scripts.analyze_content import words

PARSER_REVISION = "{REVISION}"

def parse_snapshot(payload, href, hostname="", *, source_format=None, source=None):
    payload_hash, identity = snapshot_identity(payload, href)
    format_name = source_format if source_format is not None else classify_payload(payload)
    snapshot = Snapshot(identity, payload_hash, href, hostname, payload, format_name)
    inventory = source_inventory(payload, href, format_name)
    candidate = extract_conservative(snapshot) if format_name == "html" else extract_markdown_text(snapshot)
    source = {{**(source or {{}}), "payload_hash": payload_hash, "href": href,
              "hostname": hostname, "format": format_name}}
    for key in ("source_file", "source_file_hash", "source_row"):
        source.setdefault(key, None)
    doc, chunks = document(snapshot, source, [candidate.to_dict()], inventory)
    doc["scorer_source_word_count"] = len(words(inventory["body_text"]))
    doc["raw_payload_path"] = None
    doc["raw_payload_reference"] = {{key: source[key] for key in
                                    ("source_file", "source_file_hash", "source_row", "payload_hash")}}
    doc["chunks"] = chunks
    doc["candidate_diagnostics"] = dict(doc.get("representation", {{}}))
    return doc, chunks
''')
        subprocess.run(['git', 'add', '-N', 'preprocessing/api.py'], cwd=root, check=True)
        patch = subprocess.check_output(['git', 'diff', '--', 'pyproject.toml', 'preprocessing/api.py'], cwd=root)
        output.mkdir(parents=True, exist_ok=True)
        subprocess.run([uv, 'build', '--wheel', '--out-dir', str(output.resolve())], cwd=root, check=True)
        wheel = output / f'content_optimization_exploration-{VERSION}-py3-none-any.whl'
        (output / 'content-optimization-library-v3.patch').write_bytes(patch)
        fingerprints = {}
        installed = set(zipfile.ZipFile(wheel).namelist())
        for folder in ('preprocessing', 'trad_ml_scorer', 'representations', 'scripts'):
            for path in (root / folder).rglob('*.py'):
                name = str(path.relative_to(root))
                if name in installed:
                    fingerprints[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        identity = {'repository': REPOSITORY, 'base_revision': REVISION, 'version': VERSION,
            'wheel': wheel.name, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
            'packaging_patch': 'content-optimization-library-v3.patch',
            'status': 'Pinned merged upstream v7.1 modules plus tuple facade and explicit format override',
            'module_sha256': fingerprints}
        (output / 'provenance-v3.json').write_text(json.dumps(identity, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uv', default='uv')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'packages')
    args = parser.parse_args()
    build(args.uv, args.output)
