"""Throwaway tasks proving each decomposition tier works end to end, with no change to
any framework code. `run_task` plays the part of a phone executing one chunk."""
import pytest

import pocketcluster
from pocketcluster import CountTask, ItemsTask, Task, UnknownTask, get_task, split_range, task
from worker.worker import run_task


def run_job(name, job_params, n_chunks, weights=None):
    """Mini local coordinator: split -> 'phones' execute -> aggregate."""
    t = get_task(name)
    chunks = t.split(job_params, n_chunks, weights)
    assert len(chunks) == n_chunks
    return t.aggregate([run_task(name, c)["result"] for c in chunks])


# ---- tier 1: CountTask ------------------------------------------------------
def test_count_task_needs_only_run(isolated):
    @task("ones")
    class Ones(CountTask):
        total_key = "n"
        count_key = "size"
        default_processes = 1

        def run(self, count, seed, params):
            return {"ones": count * params.get("weight", 1)}

    out = run_job("ones", {"n": 1000, "weight": 3}, 3, weights=[1, 2, 2])
    assert out == {"size": 1000, "ones": 3000}  # finalize defaults to the summed totals


def test_count_task_finalize_and_seeds(isolated):
    seen = []

    @task("seeds")
    class Seeds(CountTask):
        default_total = 10
        default_processes = 1

        def run(self, count, seed, params):
            seen.append(seed)
            return {"hits": count}

        def finalize(self, totals):
            return {"hits": totals["hits"], "count": totals["count"], "done": True}

    assert run_job("seeds", {"base_seed": 7}, 2) == {"hits": 10, "count": 10, "done": True}
    assert seen == ["7:0", "8:0"]  # distinct per chunk (and per core: "<seed>:<core>")


def test_count_task_validates_total(isolated):
    @task("needs_total")
    class NeedsTotal(CountTask):
        def run(self, count, seed, params):
            return {}

    with pytest.raises(ValueError, match="missing job param 'total'"):
        get_task("needs_total").split({}, 2)
    with pytest.raises(ValueError):
        get_task("needs_total").split({"total": 0}, 2)


# ---- tier 2: ItemsTask ------------------------------------------------------
def test_items_task_needs_only_run_item(isolated):
    @task("powers")
    class Powers(ItemsTask):
        def run_item(self, item, params):
            return item ** params.get("power", 2)

    out = run_job("powers", {"items": list(range(10)), "power": 3}, 3, weights=[1, 2, 3])
    assert out == {"outputs": [i**3 for i in range(10)]}  # original order preserved


def test_items_task_batch_override_and_finalize(isolated):
    @task("total_len")
    class TotalLen(ItemsTask):
        def run_batch(self, items, params):
            return [len(s) for s in items]

        def finalize(self, outputs):
            return {"total": sum(outputs)}

    assert run_job("total_len", {"items": ["a", "bb", "ccc", "dddd"]}, 3) == {"total": 10}


def test_items_task_more_chunks_than_items_and_empty_job(isolated):
    @task("ident")
    class Ident(ItemsTask):
        def run_item(self, item, params):
            return item

    assert run_job("ident", {"items": [1, 2]}, 5) == {"outputs": [1, 2]}
    assert run_job("ident", {"items": []}, 3) == {"outputs": []}


def test_items_task_errors(isolated):
    @task("bad_batch")
    class BadBatch(ItemsTask):
        def run_batch(self, items, params):
            return []

    @task("no_impl")
    class NoImpl(ItemsTask):
        pass

    with pytest.raises(ValueError, match="outputs"):
        run_task("bad_batch", {"items": [1]})
    with pytest.raises(NotImplementedError):
        run_task("no_impl", {"items": [1]})
    with pytest.raises(ValueError, match="missing job param 'items'"):
        get_task("no_impl").split({}, 2)


# ---- tier 3: custom Task using the helpers ----------------------------------
def test_custom_task_with_helpers(isolated):
    @task("sum_range")
    class SumRange(Task):
        def split(self, job_params, n_chunks, weights=None):
            return [{"start": a, "stop": b} for a, b in split_range(job_params["n"], n_chunks, weights)]

        def execute(self, params):
            return {"partial": sum(range(params["start"], params["stop"]))}

        def aggregate(self, results):
            return {"sum": sum(r["partial"] for r in results)}

    assert run_job("sum_range", {"n": 1000}, 4, weights=[1, 2, 3, 4]) == {"sum": sum(range(1000))}


# ---- registration rules -----------------------------------------------------
def test_registration_rules(isolated):
    @task("once")
    class Once(ItemsTask):
        def run_item(self, item, params):
            return item

    assert "once" in pocketcluster.available_tasks()
    with pytest.raises(ValueError, match="already registered"):

        @task("once")
        class Again(ItemsTask):
            pass

    with pytest.raises(TypeError):

        @task("not_a_task")
        class Plain:
            pass

    with pytest.raises(UnknownTask):
        get_task("nope")
    with pytest.raises(UnknownTask):
        run_task("nope", {})


def test_throwaway_tasks_do_not_leak():
    assert pocketcluster.available_tasks() == ["monte_carlo_pi"]
