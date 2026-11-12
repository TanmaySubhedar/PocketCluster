"""PocketCluster's task framework: standard library only, shared by coordinator and workers.

A task file only needs:

    from pocketcluster import CountTask, task
"""
from pocketcluster.base import Task, UnknownTask
from pocketcluster.helpers import concat, split_count, split_items, split_range, sum_numeric
from pocketcluster.patterns import CountTask, ItemsTask
from pocketcluster.registry import (
    LoadFailure,
    TaskLoadError,
    available_tasks,
    discover,
    get_task,
    register,
    task,
)

__all__ = [
    "CountTask",
    "ItemsTask",
    "LoadFailure",
    "Task",
    "TaskLoadError",
    "UnknownTask",
    "available_tasks",
    "concat",
    "discover",
    "get_task",
    "register",
    "split_count",
    "split_items",
    "split_range",
    "sum_numeric",
    "task",
]
