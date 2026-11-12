# PocketCluster

Hackathon MVP: a distributed CPU compute cluster powered by Android phones.
A laptop **coordinator** splits a job (Monte Carlo estimation of Pi) into chunks,
sends them to phone **workers** over Wi-Fi, and combines the results.

## Layout

| Path | Purpose |
| --- | --- |
| `pocketcluster/` | Task framework shared by both sides (stdlib only): task interface, decomposition helpers, `CountTask` / `ItemsTask` patterns, auto-discovery |
| `tasks/` | One file per task, e.g. `monte_carlo_pi.py`. Drop a file here to add a task |
| `coordinator/` | FastAPI server: device registry, scheduler, result aggregation |
| `worker/` | Stdlib-only Python worker that runs on Android (Termux) |
| `SPEC.md` | Phased plan and progress tracker |
| `dashboard/` | Single-page live dashboard served by the coordinator |
| `scripts/` | Benchmark runner (1 vs 2 vs 3 phones) |
| `tests/` | pytest suite |
| `docs/` | API contract and architecture notes |

## Setup (coordinator)

    uv sync
    uv run uvicorn coordinator.main:app --host 0.0.0.0 --port 8000

Status: skeleton only, no implementation yet.
