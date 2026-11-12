import pytest

from pocketcluster import get_task
from worker.worker import run_task

TASK = "monte_carlo_pi"


def test_split_gives_even_chunks_with_distinct_seeds():
    chunks = get_task(TASK).split({"total_iterations": 30_000_000, "base_seed": 100}, 3)
    assert chunks == [
        {"iterations": 10_000_000, "seed": 100},
        {"iterations": 10_000_000, "seed": 101},
        {"iterations": 10_000_000, "seed": 102},
    ]


def test_split_weighted_by_cores_and_passes_extra_params_through():
    chunks = get_task(TASK).split({"total_iterations": 1000, "processes": 2}, 2, weights=[6, 2])
    assert [c["iterations"] for c in chunks] == [750, 250]
    assert all(c["processes"] == 2 for c in chunks)


def test_split_uses_default_total_and_rejects_nonpositive():
    task = get_task(TASK)
    assert sum(c["iterations"] for c in task.split({}, 3)) == 30_000_000
    with pytest.raises(ValueError):
        task.split({"total_iterations": 0}, 3)


def test_kernel_is_deterministic_per_seed():
    task = get_task(TASK)
    assert task.run(50_000, "a", {}) == task.run(50_000, "a", {})
    assert task.run(50_000, "a", {}) != task.run(50_000, "b", {})


def test_execute_result_shape_single_process():
    r = run_task(TASK, {"iterations": 20_000, "seed": 1, "processes": 1})
    assert set(r) == {"result", "execution_time"}
    assert r["execution_time"] >= 0
    assert set(r["result"]) == {"iterations", "points_inside", "processes"}
    assert r["result"]["iterations"] == 20_000
    assert 0 < r["result"]["points_inside"] < 20_000


def test_multiprocess_is_deterministic_and_complete():
    a = run_task(TASK, {"iterations": 40_001, "seed": 5, "processes": 2})["result"]
    b = run_task(TASK, {"iterations": 40_001, "seed": 5, "processes": 2})["result"]
    assert a == b
    assert a["iterations"] == 40_001 and a["processes"] == 2


def test_execute_rejects_zero_iterations():
    with pytest.raises(ValueError):
        get_task(TASK).execute({"iterations": 0})


def test_aggregate_adds_up_chunks_and_computes_pi():
    results = [
        {"iterations": 100, "points_inside": 78, "processes": 1},
        {"iterations": 100, "points_inside": 79, "processes": 4},
    ]
    assert get_task(TASK).aggregate(results) == {
        "pi": pytest.approx(4 * 157 / 200),
        "points_inside": 157,
        "total_points": 200,
    }


def test_aggregate_rejects_empty():
    with pytest.raises(ValueError):
        get_task(TASK).aggregate([])


def test_end_to_end_local_run_estimates_pi():
    """Split 1M points into 3 chunks, 'run' each as a worker would, aggregate."""
    task = get_task(TASK)
    chunks = task.split({"total_iterations": 1_000_000, "base_seed": 100}, 3)
    results = [run_task(TASK, {**c, "processes": 2})["result"] for c in chunks]
    agg = task.aggregate(results)
    assert agg["total_points"] == 1_000_000
    assert abs(agg["pi"] - 3.14159) < 0.01
