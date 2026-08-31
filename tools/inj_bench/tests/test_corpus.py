"""Corpus schema validation tests."""

from __future__ import annotations

import pytest

from inj_bench.corpus import CorpusError, load_corpus


def test_sampler_loads():
    corpus = load_corpus("sampler")
    assert corpus.version == 1
    assert corpus.name == "ce-sampler"
    assert len(corpus.entries) >= 35


def test_published_only_subset():
    full = load_corpus("sampler")
    published = load_corpus("sampler", published_only=True)
    assert 14 <= len(published.entries) <= 16
    assert len(published.entries) < len(full.entries)
    assert all(entry.published for entry in published.entries)


def test_duplicate_id_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
version: 1
name: bad
entries:
  - id: dup
    category: benign
    expected: pass
    payload: one
  - id: dup
    category: benign
    expected: pass
    payload: two
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(CorpusError, match="duplicate"):
        load_corpus(str(path))


def test_invalid_expected_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
version: 1
name: bad
entries:
  - id: x
    category: benign
    expected: maybe
    payload: hi
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(CorpusError, match="expected"):
        load_corpus(str(path))
