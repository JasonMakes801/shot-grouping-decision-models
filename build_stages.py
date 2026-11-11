"""Build the staged sorting animation for the decision-models piece.

One page, embedded once per step with ?stage=1..5: edit order, scenes, the wording change,
grade groups with a zoom on the bridge, and the hand corrections. Data: Jev's scene pass (cut 0.6)
and grade pass (cut 0.5), the first scene wording (cut 0.6), and the hand labels.

Usage: DATASET=tos python3 build_stages.py <out_html> <thumbs_url_prefix>
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from build_label_board import jev_seed

D = Path(__file__).parent / "data" / "tos"


def cluster_all(pairs, events, cut):
    ix = {e: i for i, e in enumerate(events)}
    d = np.ones((len(events),) * 2)
    np.fill_diagonal(d, 0)
    for k, p in pairs.items():
        a, b = map(int, k.split("-"))
        d[ix[a], ix[b]] = d[ix[b], ix[a]] = 1 - p
    lab = fcluster(linkage(squareform(d), "average"), t=1 - cut, criterion="distance")
    groups = {}
    for e, l in zip(events, lab):
        groups.setdefault(l, []).append(e)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


def main():
    out, prefix = Path(sys.argv[1]), sys.argv[2].rstrip("/")
    shots = json.loads((D / "shots.json").read_text())
    events = [s["event"] for s in shots]
    grade = json.loads((D / "results/grade_pairs.json").read_text())
    seed = jev_seed(json.loads((D / "results/scene2_groups.json").read_text()), grade, 0.5)
    seed = sorted(seed, key=lambda sc: min(min(g) for g in sc))
    old = cluster_all(json.loads((D / "results/scene_pairs.json").read_text()), events, 0.6)
    labels = json.loads((D / "labels/tos_labels.json").read_text())
    bridge = next(sc for sc in seed if any(55 in g for g in sc))
    bridge_p = {e: grade.get(f"{min(e, 58):03d}-{max(e, 58):03d}", 0.0) for g in bridge for e in g if e != 58}
    data = {
        "shots": [{"event": e, "thumb": f"{prefix}/e{e:03d}.jpg"} for e in events],
        "seed": seed,
        "old": old,
        "labels": [[g["shots"] for g in sc["groups"]] for sc in labels["scenes"]],
        "moved": labels["changed_from_seed"]["moved_by_hand"],
        "bridgeP": bridge_p,
    }
    html = (Path(__file__).parent / "stages_template.html").read_text().replace("/*DATA*/null", json.dumps(data, separators=(",", ":")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out}: {len(seed)} Jev scenes, {len(old)} old-wording scenes, {len(data['labels'])} labeled scenes")


if __name__ == "__main__":
    main()
