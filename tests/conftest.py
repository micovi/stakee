"""Shared fixtures: a throwaway models/ folder for anything that writes the library."""

import pytest

from stakee import build, docs, export


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    for module in (export, docs, build):
        monkeypatch.setattr(module, "MODELS", tmp_path)
    return tmp_path
