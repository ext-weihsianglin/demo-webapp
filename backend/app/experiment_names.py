"""Readable labels, separate from immutable prompt identities and content hashes."""
import re
import unicodedata


def slug(text, fallback='experiment', limit=64):
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_text.lower()).strip('-')[:limit].rstrip('-') or fallback


def prompt_name(record):
    if record['id'] == record['baseline_id']:
        return f"{record['model']}-baseline-v7"
    rationale = (record.get('optimization_context') or {}).get('rationale') or record['editorial_strategy']
    words = re.findall(r'[a-zA-Z0-9]+', rationale.lower())
    words = [w for w in words if w not in {'a','an','the','and','or','to','of','for','with','that','this','is','it'}]
    description = slug(' '.join(words[:6]), 'rewrite-procedure', 56)
    return f"{record['model']}-{description}-{record['prompt_hash'][:8]}"


def experiment_name(identity, config):
    if not re.fullmatch(r'[a-f0-9]{32}', identity):
        return identity
    return f"{slug(config.get('experiment_name') or config['model']+'-fidelity-search')}-{identity[:8]}"
