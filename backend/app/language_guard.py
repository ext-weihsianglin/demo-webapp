"""Local, conservative language-change detection; not a semantic guarantee."""
from functools import lru_cache
from lingua import LanguageDetectorBuilder


@lru_cache(maxsize=1)
def detector():
    # Load language models lazily; short/ambiguous text is explicitly unverified.
    return LanguageDetectorBuilder.from_all_languages().build()


@lru_cache(maxsize=512)
def confident_language(text):
    if sum(char.isalpha() for char in text) < 40:
        return None
    values = detector().compute_language_confidence_values(text)
    if not values or values[0].value < 0.8 or values[0].value - values[1].value < 0.2:
        return None
    return values[0].language.iso_code_639_1.name.lower()


def compare_language(before, after):
    source = confident_language(before)
    proposed = confident_language(after)
    return {'status': 'unverified' if not source or not proposed else 'preserved' if source == proposed else 'changed',
            'source_language': source, 'proposed_language': proposed}
