# Architecture

PocketCluster has four kinds of parts:

- **`pocketcluster/`**: the task framework (standard library only), imported by both sides.
- **Coordinator** (laptop, FastAPI): device registry, scheduler, job runner.
- **Workers** (phones, stdlib-only Python): run one chunk of a job and report back.
- **Dashboard** (browser): polls the coordinator and shows what is happening.

The coordinator, scheduler and dashboard are **task-agnostic**: they handle "a job made of
chunks; each chunk has parameters and a result" and never mention Pi. Everything specific
to a kind of computation lives in a *task file* in a `tasks/` folder.

## Code layout

```
pocketcluster/base.py        Task interface: split(), execute(), aggregate()
pocketcluster/helpers.py     split_count / split_range / split_items / sum_numeric / concat
pocketcluster/patterns.py    CountTask and ItemsTask (ready-made decompositions)
pocketcluster/registry.py    @task decorator, get_task(), discover()
pocketcluster/parallel.py    spreads a chunk across the device's CPU cores
tasks/                       built-in tasks, ONE FILE PER TASK (monte_carlo_pi.py, ...)
coordinator/                 FastAPI app (calls split + aggregate)
worker/                      phone server (calls execute)
```

Both the coordinator and each worker call `pocketcluster.discover()` at startup, which
imports every file in `tasks/`, in any folder given with `--tasks-dir` or the
`POCKETCLUSTER_TASKS_DIRS` environment variable, and in any installed package that
exposes the entry-point group `pocketcluster.tasks`. A file that fails to import (e.g.
it needs a library a phone lacks) is skipped with a warning, so that worker simply does
not advertise the task and the coordinator never sends it any.

## Writing a task: pick a tier

A job is cut up in two stages: the coordinator splits it across **phones**, then each
phone splits its chunk across its own **CPU cores**. The patterns do both for you.

| Tier | Use it for | You write | Framework does |
|------|-----------|-----------|----------------|
| `CountTask` | "do N units of work": Monte Carlo, search, simulation | `run(count, seed, params)`, optionally `finalize(totals)` | exact weighted split of N, unique seeds, per-core fan-out, summing the numeric results |
| `ItemsTask` | "process this list": images, documents, files | `run_item(item, params)` or `run_batch(items, params)`, optionally `finalize(outputs)` | cutting the list in order, shared params, per-core fan-out, re-joining outputs in original order |
| `Task` | anything else: matrix blocks, ... | `split`, `execute`, `aggregate`, using the helpers | nothing special; you control it |

Example, the whole Monte Carlo task, condensed (the real file is `tasks/monte_carlo_pi.py`):

```python
import random
from pocketcluster import CountTask, task

@task("monte_carlo_pi")
class MonteCarloPi(CountTask):
    total_key = "total_iterations"
    count_key = "iterations"
    default_total = 30_000_000

    def run(self, count, seed, params):
        rand = random.Random(seed).random
        inside = sum(1 for _ in range(count) if rand() ** 2 + rand() ** 2 <= 1.0)
        return {"points_inside": inside}

    def finalize(self, totals):
        inside, total = totals["points_inside"], totals["iterations"]
        return {"pi": 4 * inside / total, "points_inside": inside, "total_points": total}
```

Adding a task = adding one file to a tasks folder. No framework file is edited.

### Rules for task files
- Top-level imports should be **standard library + `pocketcluster` only**, because the
  same file is loaded on phones. If a task needs another library, import it at the top
  anyway: phones lacking it will skip the task and not advertise it.
- All params and results are JSON-serializable dicts.
- `aggregate` receives results in chunk order.
- `run` / `run_item` must not rely on shared state: they run in separate processes.

## Where the code must live
The computation runs on the phone, so the phone needs the task file. Today this is done
by installing the same repo (or tasks folder) on every phone. Because workers only run
tasks from their own registry, they never execute code received over the network. Pushing
task files from the coordinator to opt-in workers is a possible later feature (it needs a
signature/trust design first).

## Running the worker
The worker is a package, so run it from the repo root: `python -m worker.worker`.
On Termux, clone the repo (or copy `pocketcluster/`, `worker/` and `tasks/`) onto the phone.
