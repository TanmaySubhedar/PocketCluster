"""Task registry and auto-discovery.

Tasks register themselves with the `@task("name")` decorator. `discover()` imports every
task file it can find, so adding a task means dropping a file in a tasks folder: no
framework file is ever edited. Both the coordinator and each worker call `discover()`
at startup. Sources, in order:

  1. the repo's built-in `tasks/` folder
  2. folders passed in (`--tasks-dir`) and in env var POCKETCLUSTER_TASKS_DIRS
  3. installed packages exposing the entry-point group `pocketcluster.tasks`

A task file that fails to import (say it needs numpy and a phone doesn't have it) is
skipped with a warning and simply not registered, so that worker won't advertise it.
"""
import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from pocketcluster.base import Task, UnknownTask

log = logging.getLogger("pocketcluster")

ENTRY_POINT_GROUP = "pocketcluster.tasks"
ENV_DIRS = "POCKETCLUSTER_TASKS_DIRS"
BUILTIN_DIR = Path(__file__).resolve().parent.parent / "tasks"

_REGISTRY: dict[str, Task] = {}
_LOADED_FILES: set[Path] = set()
_LOADED_DIRS: list[Path] = []
_LOADED_ENTRY_POINTS: set[str] = set()


class TaskLoadError(Exception):
    """A task file or package could not be loaded (raised only in strict mode)."""


@dataclass(frozen=True)
class LoadFailure:
    source: str
    error: str


def register(task_obj: Task) -> Task:
    if task_obj.name in _REGISTRY:
        raise ValueError(f"task {task_obj.name!r} is already registered")
    _REGISTRY[task_obj.name] = task_obj
    return task_obj


def task(name: str):
    """Class decorator: `@task("my_task")` on a Task subclass registers an instance of it."""

    def decorator(cls):
        if not (isinstance(cls, type) and issubclass(cls, Task)):
            raise TypeError("@task can only decorate a Task subclass (e.g. CountTask, ItemsTask)")
        cls.name = name
        register(cls())
        return cls

    return decorator


def get_task(name: str) -> Task:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise UnknownTask(f"unknown task_type {name!r}") from None


def available_tasks() -> list[str]:
    return sorted(_REGISTRY)


def loaded_dirs() -> list[Path]:
    """Task folders loaded so far (used to set up worker sub-processes)."""
    return list(_LOADED_DIRS)


def _load_file(path: Path) -> None:
    module_name = f"pocketcluster_task_{path.stem}_{abs(hash(str(path))) & 0xFFFFFFFF:x}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise


def _load_dir(directory: Path, failures: list[LoadFailure]) -> None:
    if not directory.is_dir():
        failures.append(LoadFailure(str(directory), "tasks folder does not exist"))
        return
    if directory not in _LOADED_DIRS:
        _LOADED_DIRS.append(directory)
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_") or path in _LOADED_FILES:
            continue
        _LOADED_FILES.add(path)
        try:
            _load_file(path)
        except Exception as e:  # noqa: BLE001 - one bad task file must not stop the rest
            failures.append(LoadFailure(str(path), f"{type(e).__name__}: {e}"))


def _load_entry_points(failures: list[LoadFailure]) -> None:
    for ep in metadata.entry_points(group=ENTRY_POINT_GROUP):
        if ep.name in _LOADED_ENTRY_POINTS:
            continue
        _LOADED_ENTRY_POINTS.add(ep.name)
        try:
            ep.load()  # importing the module runs its @task decorators
        except Exception as e:  # noqa: BLE001 - one bad plugin must not stop the rest
            failures.append(LoadFailure(f"entry point {ep.name}", f"{type(e).__name__}: {e}"))


def discover(
    extra_dirs=(), *, builtin: bool = True, entry_points: bool = True, strict: bool = False
) -> list[LoadFailure]:
    """Find and register every task. Safe to call repeatedly (already-loaded files are skipped).

    Returns the list of things that failed to load. With `strict=True` the first failure
    raises TaskLoadError instead (used by tests; workers run non-strict).
    """
    dirs: list[Path] = [BUILTIN_DIR] if builtin else []
    dirs += [Path(p) for p in os.environ.get(ENV_DIRS, "").split(os.pathsep) if p]
    dirs += [Path(p) for p in extra_dirs]

    failures: list[LoadFailure] = []
    seen: set[Path] = set()
    for d in dirs:
        d = d.resolve()
        if d not in seen:
            seen.add(d)
            _load_dir(d, failures)
    if entry_points:
        _load_entry_points(failures)

    for f in failures:
        log.warning("could not load tasks from %s: %s", f.source, f.error)
    if strict and failures:
        raise TaskLoadError("; ".join(f"{f.source}: {f.error}" for f in failures))
    return failures
