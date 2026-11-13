"""Query-time cost of each retriever as memory grows. Wall clock, single thread, this machine.

    python -m tcmfaudit.run_cost

The production retriever scores each (memory, ancestor) pair with a Python-level cosine, so
its cost is O(memories x ancestors) interpreter calls. ``tcmf_vectorized`` is the same ranking
(parity-tested) as two matrix products, to separate the algorithm's cost from the
implementation's.
"""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import replace

from . import AUDIT_ROOT, graphs
from . import retrievers as R
from .world import WorldConfig, generate

OUT = AUDIT_ROOT / "results" / "cost.json"
REPEATS = 5
METHODS = {
    "vector": R.rank_vector,
    "episodic": R.rank_episodic,
    "graph_union": R.rank_graph_union,
    "tcmf_vectorized": R.rank_tcmf_variant,
    "tcmf_deployed": R.rank_tcmf_deployed,
}


def main() -> None:
    rows = []
    for n_memories in (100, 1000, 5000):
        for other_events in (6, 18):
            cfg = replace(WorldConfig(), n_noise=n_memories - 15 - other_events, n_decoy_events=other_events)
            world = generate(cfg, 0)
            og = graphs.oracle(world)
            production, _ = R.prepare_tcmf_deployed(world, og)
            for name, fn in METHODS.items():
                # Loading memories into the production stores is setup, not query time.
                query = (lambda: production(world.n)) if name == "tcmf_deployed" else (lambda: fn(world, og))
                times = []
                for _ in range(REPEATS):
                    start = time.perf_counter()
                    query()
                    times.append((time.perf_counter() - start) * 1000)
                rows.append({"memories": world.n, "institution_events": len(og.nodes) - 1,
                             "method": name, "median_ms": round(statistics.median(times), 3)})
                print(rows[-1])
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
