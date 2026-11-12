# PocketCluster: Spec and Progress Tracker

**Goal (what the demo must prove):** multiple Android phones pool their CPU to run a
computational job. A central coordinator splits the job, distributes the chunks
automatically, and combines the results.

**First workload:** Monte Carlo estimation of Pi. Each phone counts how many random
points land inside the unit quarter-circle; `pi ~= 4 * inside / total`.

**Out of scope (do NOT build):** shared memory, virtual OS, LLM/tensor partitioning,
GPU/NPU, arbitrary code execution, auto-discovery beyond registration, multi-network.
Report aggregate RAM but never claim it is pooled.

## Architecture in one paragraph

A FastAPI **coordinator** on a laptop keeps a registry of devices. Phones run a
stdlib-only Python **worker** (Termux) that registers/heartbeats to the coordinator
and exposes `/health` and `/execute`. The coordinator splits a job into chunks, POSTs
each chunk to a worker in parallel, collects `{points_inside, execution_time}`, and
aggregates. A dashboard polls the coordinator. Workers only run **predefined task
types** with numeric parameters, never received code.

## Design rules

- Worker uses **only the Python standard library** (must install on Termux without compiling).
- Coordinator and workers communicate via HTTP + JSON. Contract lives in `docs/API.md`.
- **Task-agnostic framework:** scheduler, dispatcher, retries, registry and dashboard
  only handle generic `params`/`result` dicts. A task is ONE file in a `tasks/` folder,
  discovered automatically on the coordinator and every worker. Adding a task must not
  change framework code. Developers pick a pattern (`CountTask`, `ItemsTask`) or write a
  custom `Task` with the helpers.
- Task files and `pocketcluster/` import only the standard library at top level
  (they also run on phones). A task whose imports fail is skipped and not advertised.
- Dispatch only to devices whose reported `tasks` include the job's `task_type`.
- Split sizes must always **sum exactly** to the requested total.
- Dependencies pinned with `==` in `pyproject.toml`, managed with `uv`.

## Phases

Status key: `[x]` done, `[ ]` to do.

### Phase 1: Core pieces (laptop only, no network)  **DONE**
Branch: `phase-1-core-tasks`

- [x] 1.1 Task-agnostic data models: registration (with supported `tasks`), task request/result, job request (`coordinator/models.py`)
- [x] 1.2 Shared stdlib-only framework package `pocketcluster/`: `Task` interface (split / execute / aggregate)
- [x] 1.3 Decomposition helpers: `split_count`, `split_range`, `split_items`, `sum_numeric`, `concat` (exact sums, weights, order preserved)
- [x] 1.4 Ready-made patterns: `CountTask` ("N units of work") and `ItemsTask` ("process a list"), incl. automatic per-core fan-out on a device
- [x] 1.5 `@task("name")` decorator + auto-discovery of task files from `tasks/`, `--tasks-dir` / `POCKETCLUSTER_TASKS_DIRS`, and entry points; broken task files are skipped, not fatal
- [x] 1.6 Worker `run_task` generic runner that adds timing (`worker/worker.py`)
- [x] 1.7 First task as a single file: `tasks/monte_carlo_pi.py` (a `CountTask`)
- [x] 1.8 Tests for helpers, both patterns, a custom task, discovery and multi-process (`tests/`)
- [x] 1.9 API contract, task contract and "writing a task" guide (`docs/API.md`, `docs/ARCHITECTURE.md`)

**Acceptance:** `uv run pytest` passes; splitting N units always sums to N; a local
run of ~1M points gives Pi within 0.01; a new task works end to end by only dropping a
file in a tasks folder (no framework file edited).

### Phase 2: Worker and coordinator talk to each other (still on the laptop)

- [ ] 2.1 Worker HTTP server: `GET /health`, `POST /execute` (calls `run_task`), unknown task -> 400 (`worker/worker.py`)
- [ ] 2.2 Worker and coordinator call `pocketcluster.discover()` at startup (with `--tasks-dir`); worker registers and heartbeats every ~5 s, reporting the `tasks` it loaded
- [ ] 2.3 Device registry with online/offline by heartbeat timeout (`coordinator/registry.py`)
- [ ] 2.4 Coordinator API: `POST /api/register`, `GET /api/state`, `POST /api/jobs`, `GET /api/jobs/{id}` (`coordinator/main.py`)
- [ ] 2.5 Scheduler: round-robin first, then weight chunks by cores (`coordinator/scheduler.py`)
- [ ] 2.6 Concurrent dispatch to workers with httpx (only to devices supporting the task); record per-chunk time and network overhead
- [ ] 2.7 End-to-end test with 2-3 workers on different local ports acting as fake phones

**Acceptance:** a 30M-point job across 3 local workers returns Pi ~3.14 and per-chunk stats.

### Phase 3: Real phones

- [ ] 3.1 Termux set up on one phone; worker registers with the laptop over Wi-Fi
- [ ] 3.2 Handle phone sleep (Termux wake lock) and firewall/port issues
- [ ] 3.3 Add phones 2 and 3; run a job across all three
- [ ] 3.4 Worker setup steps written in `worker/README.md`

**Acceptance:** 3 phones appear as online; a job runs on them and aggregates correctly.

### Phase 4: Demo features

- [ ] 4.1 Live dashboard: devices, cores, RAM, per-phone task status, Pi estimate (`dashboard/index.html`)
- [ ] 4.2 Fault handling: phone drops mid-job -> chunk reassigned, coordinator stays up
- [ ] 4.3 Benchmark script: 1 vs 2 vs 3 phones; total time, per-phone time, network overhead, iterations/sec (`scripts/benchmark.py`)
- [ ] 4.4 Docs and polish: `docs/ARCHITECTURE.md`, README demo steps, screenshots

**Acceptance:** the checklist below is fully ticked.

## MVP acceptance checklist

- [ ] Three Android phones register with the coordinator
- [ ] Coordinator discovers available workers dynamically
- [ ] One job is divided into multiple tasks
- [ ] Phones execute tasks on their CPUs
- [ ] Results aggregate correctly
- [ ] Dashboard shows device resources and task progress
- [ ] One phone can disconnect without crashing the coordinator
- [ ] Single-phone and multi-phone benchmarks exist

## Known risks

- Pure-Python loops are slow; fine for a demo (visible speedup) but keep chunk sizes tunable.
- Phones thermal-throttle and sleep; benchmark with phones plugged in and awake.
- Dev laptop quirk: on this Windows machine (Python 3.11.0) starting child processes
  prints `Windows fatal exception: access violation` from `popen_spawn_win32`. It
  reproduces with plain Python and no project code, results are still correct and
  tests pass (exit 0). Treat it as environment noise; not seen/expected on Termux.
- Three phones will not be exactly 3x faster (network overhead, uneven hardware).

## Later (after the MVP)

Matrix multiplication as a second workload (the first custom `Task` using the helpers),
optionally pushing task files from the coordinator to opt-in workers (needs a
signature/trust design first), resource-aware scheduling by RAM/load,
native Android worker app, then investigate LLM inference on the same runtime.
