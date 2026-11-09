from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES: tuple[str, ...] = ("ru", "en")

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@lru_cache(maxsize=None)
def _load_locale(language: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{language}.json"
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def normalize_language(language: str | None) -> str:
    """Return the given language when supported, otherwise the default."""
    if language in SUPPORTED_LANGUAGES:
        return language
    return DEFAULT_LANGUAGE


def detect_language(language_code: str | None) -> str:
    """Map a Telegram ``language_code`` to a supported language."""
    code = (language_code or "").strip().lower()
    if code.startswith("ru"):
        return "ru"
    if code.startswith("en"):
        return "en"
    return DEFAULT_LANGUAGE


def translate(language: str, key: str, **kwargs: Any) -> str:
    """Look up ``key`` in ``language`` and interpolate ``kwargs``."""
    lang = normalize_language(language)
    template = _load_locale(lang).get(key)
    if template is None:
        template = _load_locale(DEFAULT_LANGUAGE).get(key)
    if template is None:
        raise KeyError(f"Missing translation key {key!r}")
    if kwargs:
        return template.format(**kwargs)
    return template


def button_labels(key: str) -> frozenset[str]:
    """Return every localized label for ``key`` (used for button matching)."""
    return frozenset(
        _load_locale(language)[key]
        for language in SUPPORTED_LANGUAGES
        if key in _load_locale(language)
    )
