"""PocketCluster worker (runs on an Android phone via Termux).

Standard library ONLY, so it installs on Termux with no compiling. The worker never
runs code it receives: it only runs tasks registered by pocketcluster.discover().
Run from the repo root with `python -m worker.worker`.

Phase 1 contains `run_task`, the task-agnostic runner. The HTTP server, task discovery
at startup (`pocketcluster.discover()`) and the coordinator registration come in phase 2.
"""
import time

from pocketcluster import available_tasks, get_task

__all__ = ["available_tasks", "run_task"]


def run_task(task_type: str, params: dict) -> dict:
    """Run one chunk of a registered task; return its result plus how long it took.

    Raises pocketcluster.UnknownTask for an unregistered name (-> HTTP 400). Works for
    every task type because it only deals in dicts.
    """
    task_obj = get_task(task_type)
    start = time.perf_counter()
    result = task_obj.execute(params)
    return {"result": result, "execution_time": round(time.perf_counter() - start, 4)}
