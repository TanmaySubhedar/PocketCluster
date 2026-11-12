"""Dropping a file in a tasks folder is all it takes to add a task."""
import textwrap

import pytest

import pocketcluster
from pocketcluster import TaskLoadError, discover, get_task
from worker.worker import run_task

DOUBLE = textwrap.dedent(
    """
    from pocketcluster import ItemsTask, task

    @task("double")
    class Double(ItemsTask):
        def run_item(self, item, params):
            return item * 2
    """
)


def write(folder, name, body):
    (folder / name).write_text(body, encoding="utf-8")


def test_dropping_a_file_registers_the_task(isolated, tmp_path):
    write(tmp_path, "double.py", DOUBLE)
    assert discover([tmp_path], builtin=False, entry_points=False, strict=True) == []
    assert "double" in pocketcluster.available_tasks()
    assert run_task("double", {"items": [1, 2, 3]})["result"]["outputs"] == [2, 4, 6]


def test_discover_is_idempotent(isolated, tmp_path):
    write(tmp_path, "double.py", DOUBLE)
    discover([tmp_path], builtin=False, entry_points=False, strict=True)
    discover([tmp_path], builtin=False, entry_points=False, strict=True)  # no "already registered"
    assert pocketcluster.available_tasks().count("double") == 1


def test_files_starting_with_underscore_are_ignored(isolated, tmp_path):
    write(tmp_path, "_helper.py", "raise RuntimeError('should never be imported')")
    assert discover([tmp_path], builtin=False, entry_points=False, strict=True) == []


def test_broken_file_is_skipped_but_others_still_load(isolated, tmp_path):
    write(tmp_path, "a_broken.py", "import definitely_not_installed_xyz")
    write(tmp_path, "b_good.py", DOUBLE)
    failures = discover([tmp_path], builtin=False, entry_points=False)
    assert len(failures) == 1
    assert "a_broken.py" in failures[0].source and "ModuleNotFoundError" in failures[0].error
    assert "double" in pocketcluster.available_tasks()  # a phone just wouldn't advertise the broken one


def test_strict_mode_raises(isolated, tmp_path):
    write(tmp_path, "broken.py", "raise RuntimeError('boom')")
    with pytest.raises(TaskLoadError, match="boom"):
        discover([tmp_path], builtin=False, entry_points=False, strict=True)


def test_duplicate_task_name_across_files_is_reported(isolated, tmp_path):
    write(tmp_path, "one.py", DOUBLE)
    write(tmp_path, "two.py", DOUBLE)
    failures = discover([tmp_path], builtin=False, entry_points=False)
    assert len(failures) == 1 and "already registered" in failures[0].error


def test_missing_folder_is_reported_not_fatal(isolated, tmp_path):
    failures = discover([tmp_path / "nope"], builtin=False, entry_points=False)
    assert len(failures) == 1 and "does not exist" in failures[0].error


def test_env_var_adds_folders(isolated, tmp_path, monkeypatch):
    write(tmp_path, "double.py", DOUBLE)
    monkeypatch.setenv("POCKETCLUSTER_TASKS_DIRS", str(tmp_path))
    discover(builtin=False, entry_points=False, strict=True)
    assert "double" in pocketcluster.available_tasks()


def test_builtin_tasks_are_discovered():
    assert "monte_carlo_pi" in pocketcluster.available_tasks()
    assert get_task("monte_carlo_pi").name == "monte_carlo_pi"


def test_multiprocess_works_for_a_task_loaded_from_a_folder(isolated, tmp_path):
    """Sub-processes must find the task by name even though it came from a dropped-in file
    (this is the path that matters on Windows, where child processes start fresh)."""
    write(tmp_path, "double.py", DOUBLE)
    discover([tmp_path], builtin=False, entry_points=False, strict=True)
    out = run_task("double", {"items": list(range(6)), "processes": 2})["result"]
    assert out == {"outputs": [0, 2, 4, 6, 8, 10], "processes": 2}
