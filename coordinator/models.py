"""Shared message shapes between the coordinator, workers and dashboard.

Task-agnostic: task-specific data travels inside plain `params` / `result` dicts that
only the task implementations understand. See docs/API.md for the HTTP contract.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field


class DeviceRegistration(BaseModel):
    """What a worker sends to POST /api/register (also used as its heartbeat)."""

    name: str
    url: str  # where the coordinator can reach the worker, e.g. http://192.168.1.20:8001
    cores: int = Field(ge=1)
    available_ram_gb: float | None = None
    active_tasks: int = Field(default=0, ge=0)
    tasks: list[str] = Field(default_factory=list)  # task types this worker can execute


class TaskRequest(BaseModel):
    """What the coordinator sends to a worker's POST /execute (one chunk)."""

    task_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """What a worker returns from POST /execute."""

    result: dict[str, Any]  # task-specific, e.g. {"iterations": ..., "points_inside": ...}
    execution_time: float  # seconds spent computing on the phone
    worker: str | None = None


class JobRequest(BaseModel):
    """What a user sends to POST /api/jobs."""

    task_type: str = "monte_carlo_pi"
    params: dict[str, Any] = Field(default_factory=dict)  # task-specific job parameters
    max_devices: int | None = Field(default=None, ge=1)
    strategy: Literal["round_robin", "weighted"] = "round_robin"
