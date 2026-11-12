"""Ready-made task patterns. Pick the one that matches your problem and write only the
part that is specific to it; the framework writes split / execute / aggregate for you.

CountTask   "do N units of work"   (Monte Carlo, brute-force search, simulations)
            you write:  run(count, seed, params)   one single-threaded slice of work
            optional:   finalize(totals)           turn summed totals into the answer

ItemsTask   "process a list"       (resize images, score documents, hash files)
            you write:  run_item(item, params)     or run_batch(items, params)
            optional:   finalize(outputs)          default: {"outputs": [...]} in order

Need something else (matrix blocks, ...)? Subclass `Task` and use the helpers in
pocketcluster.helpers. Both patterns also spread each chunk across the device's CPU
cores automatically (see `processes` below).
"""
import os
from abc import abstractmethod
from collections.abc import Sequence
from typing import Any

from pocketcluster.base import Task
from pocketcluster.helpers import concat, split_count, split_items, sum_numeric
from pocketcluster.parallel import run_parts


def _processes(requested, default, limit: int) -> int:
    """How many local processes to use: request > class default > all cores, within 1..limit."""
    wanted = requested or default or os.cpu_count() or 1
    return max(1, min(int(wanted), max(1, limit)))


class CountTask(Task):
    """A job of `total` identical units of work, split by count.

    Job params:    {total_key: 30_000_000, "base_seed": 100, ...anything else...}
    Chunk params:  {count_key: 10_000_000, "seed": 100, ...anything else...}
    Chunk result:  {count_key: ..., <numeric fields your run() returned, summed>, "processes": n}
    Job result:    finalize(<numeric fields summed over all chunks>)

    Every chunk gets its own `seed`, and every core on a phone gets its own sub-seed, so
    no two workers ever generate the same random numbers.
    """

    total_key: str = "total"  # job param holding the total amount of work
    count_key: str = "count"  # chunk param holding that chunk's share
    default_total: int | None = None  # used when the job omits total_key (None = required)
    sum_keys: Sequence[str] | None = None  # numeric fields to add up (None = all of them)
    default_processes: int | None = None  # None = use all CPU cores

    @abstractmethod
    def run(self, count: int, seed: Any, params: dict[str, Any]) -> dict[str, Any]:
        """Do `count` units of work, single-threaded, and return numeric results.

        `seed` is unique to this slice (feed it to random.Random). `params` holds any
        extra job parameters. The framework adds `count_key` to the result for you.
        """

    def finalize(self, totals: dict[str, Any]) -> dict[str, Any]:
        """Turn the summed totals (including `count_key`) into the job result."""
        return totals

    # ---- the three framework steps -----------------------------------------
    def split(self, job_params, n_chunks, weights=None):
        total = job_params.get(self.total_key, self.default_total)
        if total is None:
            raise ValueError(f"missing job param {self.total_key!r}")
        total = int(total)
        if total <= 0:
            raise ValueError(f"{self.total_key} must be > 0")
        base_seed = int(job_params.get("base_seed", 0))
        shared = {k: v for k, v in job_params.items() if k not in (self.total_key, "base_seed")}
        sizes = split_count(total, n_chunks, weights)
        return [{**shared, self.count_key: n, "seed": base_seed + i} for i, n in enumerate(sizes)]

    def _sum_keys(self) -> list[str] | None:
        if self.sum_keys is None:
            return None
        return [self.count_key, *(k for k in self.sum_keys if k != self.count_key)]

    def run_part(self, part: dict[str, Any]) -> dict[str, Any]:
        count = int(part[self.count_key])
        out = dict(self.run(count, part.get("seed", 0), part))
        out.setdefault(self.count_key, count)
        return out

    def execute(self, params):
        count = int(params[self.count_key])
        if count <= 0:
            raise ValueError(f"{self.count_key} must be > 0")
        seed = params.get("seed", 0)
        procs = _processes(params.get("processes"), self.default_processes, count)
        sizes = split_count(count, procs)
        parts = [{**params, self.count_key: n, "seed": f"{seed}:{i}"} for i, n in enumerate(sizes)]
        results = run_parts(self.name, "run_part", parts, procs)
        out = sum_numeric(results, self._sum_keys())
        out["processes"] = procs
        return out

    def aggregate(self, results):
        if not results:
            raise ValueError("no results to aggregate")
        return self.finalize(sum_numeric(results, self._sum_keys(), exclude=("processes",)))


class ItemsTask(Task):
    """A job that processes a list of independent items.

    Job params:    {"items": [...], ...anything else (shared by every item)...}
    Chunk params:  {"items": [one batch], ...the same shared params...}
    Chunk result:  {"outputs": [one output per item in the batch], "processes": n}
    Job result:    finalize(all outputs concatenated in the original item order)

    Override `run_item` (one item at a time) or `run_batch` (a whole batch at once,
    e.g. when setup is expensive).
    """

    items_key: str = "items"
    default_processes: int | None = 1  # items can be big to copy; opt in via "processes"

    def run_item(self, item: Any, params: dict[str, Any]) -> Any:
        raise NotImplementedError("override run_item(item, params) or run_batch(items, params)")

    def run_batch(self, items: list[Any], params: dict[str, Any]) -> list[Any]:
        return [self.run_item(item, params) for item in items]

    def finalize(self, outputs: list[Any]) -> dict[str, Any]:
        """Turn the ordered list of all outputs into the job result."""
        return {"outputs": outputs}

    # ---- the three framework steps -----------------------------------------
    def split(self, job_params, n_chunks, weights=None):
        if self.items_key not in job_params:
            raise ValueError(f"missing job param {self.items_key!r}")
        shared = {k: v for k, v in job_params.items() if k != self.items_key}
        batches = split_items(job_params[self.items_key], n_chunks, weights)
        return [{**shared, self.items_key: batch} for batch in batches]

    def run_part(self, part: dict[str, Any]) -> dict[str, Any]:
        items = part[self.items_key]
        shared = {k: v for k, v in part.items() if k != self.items_key}
        outputs = list(self.run_batch(items, shared))
        if len(outputs) != len(items):
            raise ValueError(f"run_batch returned {len(outputs)} outputs for {len(items)} items")
        return {"outputs": outputs}

    def execute(self, params):
        items = params[self.items_key]
        if not items:
            return {"outputs": [], "processes": 1}
        procs = _processes(params.get("processes"), self.default_processes, len(items))
        parts = [{**params, self.items_key: batch} for batch in split_items(items, procs)]
        results = run_parts(self.name, "run_part", parts, procs)
        return {"outputs": concat(results, "outputs"), "processes": procs}

    def aggregate(self, results):
        return self.finalize(concat(results, "outputs"))
