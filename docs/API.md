# PocketCluster API contract

All messages are JSON over HTTP on the local Wi-Fi. The Python shapes live in
`coordinator/models.py`; this file is the source of truth if they ever disagree.

The framework is **task-agnostic**: it only moves around `params` and `result`
dictionaries. What they contain is defined by each task type (see "Task types" below).
Workers only run **registered task types**. They never execute code sent to them.

## Worker (runs on each phone, default port 8001)

### `GET /health`
```json
{ "status": "ok", "name": "phone_a", "url": "http://192.168.1.20:8001",
  "cores": 8, "available_ram_gb": 3.2, "active_tasks": 0,
  "tasks": ["monte_carlo_pi"] }
```

### `POST /execute`
Runs ONE chunk of a job.
```json
{ "task_type": "monte_carlo_pi",
  "params": { "iterations": 10000000, "seed": 101 } }
```
Response `200`:
```json
{ "result": { "iterations": 10000000, "points_inside": 7853980, "processes": 8 },
  "execution_time": 12.4, "worker": "phone_a" }
```
- `result` is task-specific. `execution_time` (seconds computing on the phone) and
  `worker` are added by the framework for every task.
- Errors: `400` unknown `task_type` or bad params, `500` the task crashed.
  Body: `{"error": "..."}`.

## Coordinator (laptop, default port 8000)

### `POST /api/register` (also the heartbeat, sent every ~5 s)
```json
{ "name": "phone_a", "url": "http://192.168.1.20:8001", "cores": 8,
  "available_ram_gb": 3.2, "active_tasks": 0, "tasks": ["monte_carlo_pi"] }
```
A device with no heartbeat for ~15 s is shown as `offline`. The coordinator only sends
a chunk to devices whose `tasks` list contains that job's `task_type`.

### `GET /api/state`
Devices plus recent jobs, for the dashboard.

### `POST /api/jobs`
```json
{ "task_type": "monte_carlo_pi",
  "params": { "total_iterations": 30000000, "base_seed": 100 },
  "max_devices": 3, "strategy": "round_robin" }
```
Returns `{ "job_id": "..." }` immediately; the job runs in the background.
`params` is task-specific. `strategy` is `round_robin` (equal chunks) or `weighted`
(chunks sized in proportion to each device's cores).

### `GET /api/jobs/{job_id}`
```json
{ "job_id": "...", "task_type": "monte_carlo_pi", "status": "running|done|failed",
  "result": { "pi": 3.14159, "points_inside": 23561925, "total_points": 30000000 },
  "wall_time": 13.1,
  "chunks": [ { "index": 0, "device": "phone_a",
                "params": { "iterations": 10000000, "seed": 100 },
                "result": { "iterations": 10000000, "points_inside": 7853980, "processes": 8 },
                "execution_time": 12.4, "network_overhead": 0.3, "status": "done" } ] }
```
- `result` (job level) comes from the task's `aggregate`.
- `network_overhead` = round-trip time minus the worker's own `execution_time`.
- Generic stats (wall time, per-chunk times) work for every task. Throughput
  (units per second) is task-specific and will be shown only where a task defines it.

## The task contract

A task is one file in a `tasks/` folder (see `docs/ARCHITECTURE.md`) with three steps:

| Step | Runs on | Signature |
|------|---------|-----------|
| `split` | coordinator | `(job_params, n_chunks, weights) -> [chunk_params, ...]` |
| `execute` | phone | `(chunk_params) -> chunk_result` |
| `aggregate` | coordinator | `([chunk_result, ...]) -> job_result` (results in chunk order) |

Rules: all values are JSON-serializable dicts; `split` returns exactly `n_chunks`
chunks. The coordinator and every worker load the same task files at startup, and a
worker advertises (in `tasks`) only the tasks it managed to load.

Most tasks use a ready-made pattern instead of writing these by hand:
`CountTask` (job params hold a total amount of work, plus optional `base_seed`; chunk
params get a share and a `seed`) and `ItemsTask` (job params hold `items`; chunk params
get one batch of them). Any extra job params are passed unchanged to every chunk, so a
job may include `"processes": N` to cap how many CPU cores each phone uses.

## Task types

### `monte_carlo_pi` (a `CountTask`)
- Job params: `total_iterations` (default 30,000,000), `base_seed` (default 0).
- Chunk params: `iterations`, `seed`, optional `processes` (null = all cores).
- Chunk result: `iterations`, `points_inside`, `processes`.
- Job result: `pi`, `points_inside`, `total_points`; `pi = 4 * points_inside / total_points`.
- Chunk `i` uses seed `base_seed + i`; each worker further splits its chunk across its
  cores with seeds `"<seed>:<core>"`, so no two cores generate the same points.
