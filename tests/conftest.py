import pytest

from pocketcluster import discover, registry


@pytest.fixture(scope="session", autouse=True)
def _discover_builtin_tasks():
    """Load the repo's built-in tasks once, failing loudly if any can't be imported."""
    discover(strict=True)


@pytest.fixture
def isolated(monkeypatch):
    """Let a test register throwaway tasks without leaking them into other tests."""
    monkeypatch.setattr(registry, "_REGISTRY", dict(registry._REGISTRY))
    monkeypatch.setattr(registry, "_LOADED_FILES", set(registry._LOADED_FILES))
    monkeypatch.setattr(registry, "_LOADED_DIRS", list(registry._LOADED_DIRS))
    monkeypatch.setattr(registry, "_LOADED_ENTRY_POINTS", set(registry._LOADED_ENTRY_POINTS))
