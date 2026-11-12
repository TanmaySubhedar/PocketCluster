"""The task interface.

Every task has three steps. The framework (scheduler, dispatcher, retries, dashboard)
only ever handles plain JSON-style dicts and never needs to know what a task means:

    split      job params (+ number of chunks)  -> list of chunk-param dicts   [coordinator]
    execute    one chunk's params               -> that chunk's result dict    [phone]
    aggregate  all chunk results (chunk order)  -> the final job result dict   [coordinator]

Most tasks should NOT subclass Task directly: use CountTask or ItemsTask from
pocketcluster.patterns, which write `split` and `aggregate` for you.
"""
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class UnknownTask(KeyError):
    """Raised when a task name is not registered."""


class Task(ABC):
    #: Name used in API requests. Set for you by the `@task("name")` decorator.
    name: str

    @abstractmethod
    def split(
        self, job_params: dict[str, Any], n_chunks: int, weights: Sequence[float] | None = None
    ) -> list[dict[str, Any]]:
        """Return exactly `n_chunks` parameter dicts, one per chunk.

        `weights` (optional) says how much work each chunk should get relative to the
        others, e.g. each device's core count. Each dict is sent as-is to `execute`.
        """

    @abstractmethod
    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run ONE chunk on a device and return its result dict."""

    @abstractmethod
    def aggregate(self, results: Sequence[dict[str, Any]]) -> dict[str, Any]:
        """Combine every chunk's result into the job result.

        `results` is ordered by chunk index, so order-sensitive tasks can rely on it.
        """
