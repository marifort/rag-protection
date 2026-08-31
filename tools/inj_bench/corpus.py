"""Load and validate the injection benchmark corpus (YAML)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

import yaml

from .models import CORPUS_VECTORS, EXPECTED_VERDICTS, Corpus, CorpusEntry

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
DEFAULT_CORPUS = CORPUS_DIR / "sampler.yaml"
EE_CORPUS_NAMES = frozenset({"full", "full-v1", "ee-full-v1"})


class CorpusError(Exception):
    """Raised when a corpus file cannot be parsed or validated (CLI exit code 2)."""


def _resolve_ee_corpus(name: str) -> Path:
    """Load EE full corpus when inj_bench runs with enterprise on PYTHONPATH."""
    try:
        from rag_protection_enterprise.entitlements import Entitlements
        from rag_protection_enterprise.inj_corpus import InjCorpusError, resolve_inj_corpus_path
    except ImportError as exc:
        raise CorpusError(
            f"EE corpus {name!r} requires rag-protection-enterprise on PYTHONPATH"
        ) from exc
    try:
        return resolve_inj_corpus_path(name, entitlements=Entitlements.from_env())
    except InjCorpusError as exc:
        raise CorpusError(str(exc)) from exc


def resolve_corpus_path(name_or_path: Optional[str]) -> Path:
    if not name_or_path or name_or_path == "sampler":
        return DEFAULT_CORPUS
    key = name_or_path.strip().lower().replace(".yaml", "")
    if key in EE_CORPUS_NAMES or key.startswith("full-"):
        return _resolve_ee_corpus(key)
    path = Path(name_or_path)
    if path.exists():
        return path
    candidate = CORPUS_DIR / name_or_path
    if candidate.exists():
        return candidate
    candidate_yaml = CORPUS_DIR / f"{name_or_path}.yaml"
    if candidate_yaml.exists():
        return candidate_yaml
    raise CorpusError(f"corpus not found: {name_or_path}")


def load_corpus(
    path: Optional[str] = None,
    *,
    published_only: bool = False,
) -> Corpus:
    corpus_path = resolve_corpus_path(path)
    try:
        raw = yaml.safe_load(corpus_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CorpusError(f"cannot read corpus ({corpus_path}): {exc}") from exc
    except yaml.YAMLError as exc:
        raise CorpusError(f"invalid YAML in {corpus_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise CorpusError("corpus root must be a mapping")

    version = raw.get("version")
    if version != 1:
        raise CorpusError("corpus version must be 1")

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CorpusError("corpus must include a non-empty 'name'")

    items = raw.get("entries")
    if not isinstance(items, list) or not items:
        raise CorpusError("corpus must include a non-empty 'entries' list")

    entries: List[CorpusEntry] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        entry = _parse_entry(item, index)
        if entry.id in seen_ids:
            raise CorpusError(f"duplicate corpus id: {entry.id}")
        seen_ids.add(entry.id)
        if published_only and not entry.published:
            continue
        entries.append(entry)

    if not entries:
        raise CorpusError("no corpus entries matched the requested filter")

    return Corpus(
        version=version,
        name=name,
        description=str(raw.get("description") or ""),
        entries=entries,
    )


def _parse_entry(item: Any, index: int) -> CorpusEntry:
    if not isinstance(item, dict):
        raise CorpusError(f"entries[{index}] must be a mapping")

    entry_id = item.get("id")
    payload = item.get("payload")
    category = item.get("category")
    expected = item.get("expected")

    if not isinstance(entry_id, str) or not entry_id.strip():
        raise CorpusError(f"entries[{index}] missing non-empty 'id'")
    if not isinstance(payload, str):
        raise CorpusError(f"entries[{index}] ({entry_id}) missing 'payload' string")
    if not isinstance(category, str) or not category.strip():
        raise CorpusError(f"entries[{index}] ({entry_id}) missing 'category'")
    if expected not in EXPECTED_VERDICTS:
        raise CorpusError(
            f"entries[{index}] ({entry_id}) expected must be one of "
            f"{sorted(EXPECTED_VERDICTS)}"
        )

    vector = item.get("vector", "direct")
    if vector not in CORPUS_VECTORS:
        raise CorpusError(
            f"entries[{index}] ({entry_id}) vector must be one of "
            f"{sorted(CORPUS_VECTORS)}"
        )

    source = item.get("source", "")
    if source is not None and not isinstance(source, str):
        raise CorpusError(f"entries[{index}] ({entry_id}) source must be a string")

    published = item.get("published", True)
    if not isinstance(published, bool):
        raise CorpusError(f"entries[{index}] ({entry_id}) published must be a boolean")

    return CorpusEntry(
        id=entry_id,
        payload=payload,
        category=category,
        expected=expected,
        vector=vector,
        source=str(source or ""),
        published=published,
    )
