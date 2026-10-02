"""Build the pinned research modules with only import/packaging adaptations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

REVISION = '864e6634a54ad80ac1657129e994b18c3a1f7eff'
REPOSITORY = 'https://github.com/ext-weihsianglin/content-optimization-system'
VERSION = '0.2.0'


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
        parser = root / 'trad_ml_scorer/retention_features.py'
        text = parser.read_text().replace('def parse_snapshot(payload, href, hostname="", source=None):',
            'def parse_snapshot(payload, href, hostname="", source=None, *, source_format=None):')
        text = text.replace('format_name = classify_payload(payload)',
            'format_name = source_format if source_format is not None else classify_payload(payload)')
        parser.write_text(text)
        api = root / 'preprocessing/api.py'
        api.write_text(f'''"""Tuple facade over the exact upstream corpus parser."""
from trad_ml_scorer.retention_features import parse_snapshot as _parse

PARSER_REVISION = "{REVISION}"

def parse_snapshot(payload, href, hostname="", *, source_format=None, source=None):
    doc = _parse(payload, href, hostname, source, source_format=source_format)
    doc["candidate_diagnostics"] = dict(doc.get("representation", {{}}))
    return doc, doc["chunks"]
''')
        subprocess.run(['git', 'add', '-N', 'preprocessing/api.py'], cwd=root, check=True)
        patch = subprocess.check_output(['git', 'diff', '--', 'pyproject.toml',
            'preprocessing/api.py', 'trad_ml_scorer/retention_features.py'], cwd=root)
        output.mkdir(parents=True, exist_ok=True)
        subprocess.run([uv, 'build', '--wheel', '--out-dir', str(output.resolve())], cwd=root, check=True)
        wheel = output / f'content_optimization_exploration-{VERSION}-py3-none-any.whl'
        (output / 'content-optimization-library-v2.patch').write_bytes(patch)
        fingerprints = {}
        installed = set(zipfile.ZipFile(wheel).namelist())
        for folder in ('preprocessing', 'trad_ml_scorer', 'representations', 'scripts'):
            for path in (root / folder).rglob('*.py'):
                name = str(path.relative_to(root))
                if name in installed:
                    fingerprints[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        identity = {'repository': REPOSITORY, 'base_revision': REVISION, 'version': VERSION,
            'wheel': wheel.name, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
            'packaging_patch': 'content-optimization-library-v2.patch',
            'status': 'Pinned merged upstream modules plus tuple facade and explicit format override',
            'module_sha256': fingerprints}
        (output / 'provenance-v2.json').write_text(json.dumps(identity, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uv', default='uv')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'packages')
    args = parser.parse_args()
    build(args.uv, args.output)
