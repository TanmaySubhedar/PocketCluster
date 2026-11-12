"""Monte Carlo estimation of Pi: the whole task in one file.

Throw random darts at a 1x1 square; the fraction landing inside the quarter-circle
approaches pi/4. This uses the CountTask pattern, so we only write the single-threaded
dart-throwing (`run`) and the final maths (`finalize`). The framework splits the darts
across phones, then across each phone's CPU cores, and adds the counts back up.

Job params:  {"total_iterations": 30000000, "base_seed": 100}
Job result:  {"pi": 3.1415, "points_inside": ..., "total_points": ...}
"""
import random

from pocketcluster import CountTask, task


@task("monte_carlo_pi")
class MonteCarloPi(CountTask):
    total_key = "total_iterations"
    count_key = "iterations"
    default_total = 30_000_000

    def run(self, count, seed, params):
        rand = random.Random(seed).random
        inside = 0
        for _ in range(count):
            x = rand()
            y = rand()
            if x * x + y * y <= 1.0:
                inside += 1
        return {"points_inside": inside}

    def finalize(self, totals):
        inside, total = totals["points_inside"], totals["iterations"]
        return {"pi": 4.0 * inside / total, "points_inside": inside, "total_points": total}
