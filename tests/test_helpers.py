import pytest

from pocketcluster import concat, split_count, split_items, split_range, sum_numeric


@pytest.mark.parametrize("total,n", [(30_000_000, 3), (10, 3), (7, 7), (5, 8), (0, 4), (1, 1)])
def test_split_count_sums_exactly(total, n):
    sizes = split_count(total, n)
    assert len(sizes) == n
    assert sum(sizes) == total
    assert max(sizes) - min(sizes) <= 1  # as even as possible


def test_split_count_weighted_is_proportional_and_exact():
    assert split_count(1000, 3, weights=[8, 4, 4]) == [500, 250, 250]


def test_split_count_weighted_rounding_never_loses_work():
    assert sum(split_count(1001, 3, weights=[1, 1, 1])) == 1001
    assert sum(split_count(999_999, 4, weights=[8, 6, 4, 3])) == 999_999


@pytest.mark.parametrize(
    "kwargs",
    [
        {"total": -1, "n_chunks": 2},
        {"total": 10, "n_chunks": 0},
        {"total": 10, "n_chunks": 2, "weights": [1]},
        {"total": 10, "n_chunks": 2, "weights": [1, 0]},
    ],
)
def test_split_count_rejects_bad_input(kwargs):
    with pytest.raises(ValueError):
        split_count(**kwargs)


def test_split_range_is_contiguous_and_covers_everything():
    slices = split_range(10, 3)
    assert slices == [(0, 4), (4, 7), (7, 10)]
    assert split_range(10, 2, weights=[3, 2]) == [(0, 6), (6, 10)]


def test_split_items_preserves_order_and_content():
    items = list(range(10))
    batches = split_items(items, 3)
    assert [x for b in batches for x in b] == items
    assert [len(b) for b in batches] == [4, 3, 3]


def test_split_items_more_chunks_than_items_gives_empty_batches():
    batches = split_items(["a", "b"], 4)
    assert len(batches) == 4
    assert [x for b in batches for x in b] == ["a", "b"]


def test_split_items_rejects_non_lists():
    with pytest.raises(TypeError):
        split_items("abc", 2)
    with pytest.raises(TypeError):
        split_items(5, 2)


def test_sum_numeric_auto_and_with_keys():
    results = [{"a": 1, "b": 2.5, "ok": True, "s": "x", "processes": 8}, {"a": 3, "b": 1}]
    assert sum_numeric(results, exclude=("processes",)) == {"a": 4, "b": 3.5}
    assert sum_numeric(results, keys=["a"]) == {"a": 4}
    with pytest.raises(KeyError):
        sum_numeric(results, keys=["missing"])


def test_concat_flattens_in_order():
    assert concat([{"o": [1, 2]}, {"o": []}, {"o": [3]}], "o") == [1, 2, 3]
