"""Run pieces of a chunk on this device's CPU cores.

The patterns use this so task authors write a plain single-threaded function and never
touch multiprocessing. Sub-processes look the task up by NAME and re-run discovery, so
this works on Windows (which starts fresh processes) as well as on Linux/Android.
"""
import multiprocessing as mp

from pocketcluster.registry import discover, get_task, loaded_dirs


def _init_child(dirs) -> None:
    discover(dirs, builtin=False)


def _call(args):
    task_name, method, part = args
    return getattr(get_task(task_name), method)(part)


def run_parts(task_name: str, method: str, parts: list[dict], processes: int) -> list:
    """Call `task.<method>(part)` for each part, in parallel, returning results in order."""
    if processes <= 1 or len(parts) <= 1:
        task_obj = get_task(task_name)
        return [getattr(task_obj, method)(p) for p in parts]
    with mp.Pool(
        min(processes, len(parts)), initializer=_init_child, initargs=(loaded_dirs(),)
    ) as pool:
        return pool.map(_call, [(task_name, method, p) for p in parts])
