"""Ready-made helpers for cutting work up and putting results back together.

Use these inside a custom `Task.split` / `Task.aggregate`. All of them guarantee that
nothing is lost or duplicated: chunk sizes always add up to exactly the total.
"""
from collections.abc import Sequence
from typing import Any


def split_count(total: int, n_chunks: int, weights: Sequence[float] | None = None) -> list[int]:
    """Split `total` units of work into `n_chunks` whole numbers that sum to exactly `total`.

    Without weights the split is as even as possible. With weights (e.g. each phone's
    core count) sizes are proportional to them. Uses the largest-remainder method so
    rounding never loses or invents a unit.
    """
    if total < 0:
        raise ValueError("total must be >= 0")
    if n_chunks < 1:
        raise ValueError("n_chunks must be >= 1")
    if weights is None:
        weights = [1.0] * n_chunks
    if len(weights) != n_chunks:
        raise ValueError("weights must have one entry per chunk")
    if any(w <= 0 for w in weights):
        raise ValueError("weights must be positive")

    weight_sum = sum(weights)
    exact = [total * w / weight_sum for w in weights]
    sizes = [int(x) for x in exact]
    leftover = total - sum(sizes)
    # Hand the remaining units to the chunks with the largest fractional parts.
    by_fraction = sorted(range(n_chunks), key=lambda i: exact[i] - sizes[i], reverse=True)
    for i in by_fraction[:leftover]:
        sizes[i] += 1
    return sizes


def split_range(
    total: int, n_chunks: int, weights: Sequence[float] | None = None
) -> list[tuple[int, int]]:
    """Split `range(total)` into contiguous `(start, stop)` slices (e.g. matrix row blocks)."""
    slices, start = [], 0
    for size in split_count(total, n_chunks, weights):
        slices.append((start, start + size))
        start += size
    return slices


def split_items(
    items: Sequence[Any], n_chunks: int, weights: Sequence[float] | None = None
) -> list[list[Any]]:
    """Cut a list into `n_chunks` contiguous batches, preserving order.

    Concatenating the batches gives back the original list. A batch may be empty when
    there are more chunks than items.
    """
    if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
        raise TypeError("items must be a list or tuple")
    return [list(items[a:b]) for a, b in split_range(len(items), n_chunks, weights)]


def sum_numeric(
    results: Sequence[dict[str, Any]],
    keys: Sequence[str] | None = None,
    exclude: Sequence[str] = (),
) -> dict[str, Any]:
    """Add up the numeric fields of several result dicts.

    `keys=None` sums every numeric field (bools and non-numbers are skipped), minus any
    in `exclude`. With `keys`, only those are summed and each must be present.
    """
    totals: dict[str, Any] = {}
    if keys is not None:
        return {k: sum(r[k] for r in results) for k in keys}
    for r in results:
        for k, v in r.items():
            if k in exclude or isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            totals[k] = totals.get(k, 0) + v
    return totals


def concat(results: Sequence[dict[str, Any]], key: str) -> list[Any]:
    """Flatten the list stored under `key` in every result, in chunk order."""
    return [x for r in results for x in r[key]]
