"""Turn Jev's pairwise probabilities into groups.

Average-linkage clustering on distance = 1 - P(same), cut at 1 - THRESHOLD.
Uses only Jev's answers (no edit order). Groups are ordered by their first
shot in the edit, and shots within a group stay in edit order.

Usage: python3 group.py scene|setup [threshold]
Writes data/<dataset>/results/<kind>_groups.json
"""
import json
import sys
import os
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

RESULTS = Path(__file__).parent / "data" / os.environ.get("DATASET", "tos") / "results"


def main():
    kind = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    probs = json.loads((RESULTS / f"{kind}_pairs.json").read_text())
    events = sorted({int(e) for pair in probs for e in pair.split("-")})
    index = {e: i for i, e in enumerate(events)}
    dist = np.zeros((len(events), len(events)))
    for pair, p in probs.items():
        a, b = (index[int(e)] for e in pair.split("-"))
        dist[a, b] = dist[b, a] = 1 - p
    labels = fcluster(linkage(squareform(dist), method="average"),
                      t=1 - threshold, criterion="distance")
    groups = {}
    for event, label in zip(events, labels):
        groups.setdefault(label, []).append(event)
    ordered = sorted(groups.values(), key=lambda g: g[0])
    (RESULTS / f"{kind}_groups.json").write_text(json.dumps(ordered))
    for g in ordered:
        print(len(g), g)


if __name__ == "__main__":
    main()
