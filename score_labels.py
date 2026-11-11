"""Score Jev's pairwise answers against hand labels from the labeling board.

Two levels, matching the two passes:
  scene: every pair of shots, truth = same scene id, prediction = scene2_pairs.json
  grade: pairs within the same labeled scene, truth = same grade group, prediction = grade_pairs.json
         (grade_all_pairs.json, the one-pass test, is scored over all pairs with truth = same group)

For each level: AUC (ranking), precision / recall / F1 at a cutoff on P(same), and cluster-level
purity and adjusted Rand index after average-linkage clustering at the same cutoff (the board's rule).

Usage: DATASET=tos python3 score_labels.py <labels.json> [--scene-cut 0.6] [--grade-cut 0.5] [--prefix clef_] [--scene-kind scene2|scene]
  --prefix clef_ scores Cloudflare Clef's answers; --scene-kind scene scores the first, story-time wording.
"""
import itertools
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

DATA = Path(__file__).parent / "data" / os.environ.get("DATASET", "tos")


def pair_key(a, b):
    return f"{min(a, b):03d}-{max(a, b):03d}"


def auc(same, diff):
    if not same or not diff:
        return None
    same, diff = np.array(same), np.array(diff)
    return float(np.mean([(same > d).mean() + 0.5 * (same == d).mean() for d in diff]))


def prf(truth, pred):
    tp = sum(1 for t, p in zip(truth, pred) if t and p)
    fp = sum(1 for t, p in zip(truth, pred) if not t and p)
    fn = sum(1 for t, p in zip(truth, pred) if t and not p)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1, tp, fp, fn


def adjusted_rand(a, b):
    """Adjusted Rand index between two labelings (lists of hashable labels)."""
    from collections import Counter
    pairs = Counter(zip(a, b))
    ca, cb = Counter(a), Counter(b)
    comb = lambda x: x * (x - 1) / 2
    sum_ab = sum(comb(v) for v in pairs.values())
    sum_a = sum(comb(v) for v in ca.values())
    sum_b = sum(comb(v) for v in cb.values())
    total = comb(len(a))
    expected = sum_a * sum_b / total if total else 0
    maxi = (sum_a + sum_b) / 2
    return (sum_ab - expected) / (maxi - expected) if maxi != expected else 1.0


def cluster(events, probs, cutoff):
    """Average linkage on 1 - P(same), cut at 1 - cutoff. Returns {event: cluster id}."""
    if len(events) == 1:
        return {events[0]: 1}
    dist = np.ones((len(events), len(events)))
    np.fill_diagonal(dist, 0)
    for i, a in enumerate(events):
        for j, b in enumerate(events):
            if i < j:
                dist[i, j] = dist[j, i] = 1 - probs.get(pair_key(a, b), 0.0)
    labels = fcluster(linkage(squareform(dist), "average"), t=1 - cutoff, criterion="distance")
    return dict(zip(events, map(int, labels)))


def purity(pred, truth):
    groups = {}
    for e, c in pred.items():
        groups.setdefault(c, []).append(truth[e])
    return sum(max(g.count(v) for v in set(g)) for g in groups.values()) / len(pred)


def score(name, events, truth_of, probs, cutoff, pairs=None):
    pairs = pairs if pairs is not None else list(itertools.combinations(events, 2))
    truth = [truth_of[a] == truth_of[b] for a, b in pairs]
    p = [probs.get(pair_key(a, b), 0.0) for a, b in pairs]
    pred = [x >= cutoff for x in p]
    same = [x for x, t in zip(p, truth) if t]
    diff = [x for x, t in zip(p, truth) if not t]
    precision, recall, f1, tp, fp, fn = prf(truth, pred)
    clus = cluster(events, probs, cutoff)
    report = {
        "level": name, "shots": len(events), "pairs": len(pairs), "same_pairs": len(same), "cutoff": cutoff,
        "auc": round(auc(same, diff), 3) if same and diff else None,
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "true_pos": tp, "false_pos": fp, "false_neg": fn,
        "mean_p_same": round(float(np.mean(same)), 3) if same else None,
        "mean_p_different": round(float(np.mean(diff)), 3) if diff else None,
        "clusters_predicted": len(set(clus.values())), "clusters_true": len(set(truth_of[e] for e in events)),
        "purity": round(purity(clus, truth_of), 3),
        "adjusted_rand": round(adjusted_rand([clus[e] for e in events], [truth_of[e] for e in events]), 3),
    }
    print(f"{name:12s} shots {len(events):3d} pairs {len(pairs):5d} same {len(same):4d} | auc {report['auc']}  "
          f"P {report['precision']} R {report['recall']} F1 {report['f1']} @ {cutoff} | "
          f"clusters {report['clusters_predicted']} vs {report['clusters_true']}  purity {report['purity']}  ARI {report['adjusted_rand']}")
    return report


def main():
    args = sys.argv[1:]
    opt = lambda k, d: args[args.index(k) + 1] if k in args else d
    labels = json.loads(Path(args[0]).read_text())
    scene_cut, grade_cut = float(opt("--scene-cut", 0.6)), float(opt("--grade-cut", 0.5))
    prefix, scene_kind = opt("--prefix", ""), opt("--scene-kind", "scene2")
    if labels.get("unsorted"):
        print(f"warning: {len(labels['unsorted'])} shots unsorted, they are left out of the scores")
    scene_of = {r["event"]: r["scene"] for r in labels["shots"]}
    group_of = {r["event"]: r["group"] for r in labels["shots"]}
    events = sorted(scene_of)
    results = DATA / "results"
    scene_probs = json.loads((results / f"{prefix}{scene_kind}_pairs.json").read_text())
    grade_probs = json.loads((results / f"{prefix}grade_pairs.json").read_text())
    reports = [score("scene", events, scene_of, scene_probs, scene_cut)]
    # grade pass as run: pairs inside the model's own scenes. Scored within the labeled scenes,
    # where every pair has a label. Pairs never asked (different scene) count as P = 0.
    within = [(a, b) for a, b in itertools.combinations(events, 2) if scene_of[a] == scene_of[b]]
    reports.append(score("grade", events, group_of, grade_probs, grade_cut, pairs=within))
    if not prefix and (results / "grade_all_pairs.json").exists():
        all_probs = json.loads((results / "grade_all_pairs.json").read_text())
        reports.append(score("grade_1pass", events, group_of, all_probs, grade_cut))
    for r in reports:
        r["shots_right"] = round(r["purity"] * r["shots"])
    print(f"shots in the right scene: {reports[0]['shots_right']} of {len(events)} | "
          f"in the right grade group: {reports[1]['shots_right']} of {len(events)}")
    out = results / f"{prefix}{scene_kind}_label_scores.json"
    out.write_text(json.dumps({"labels": args[0], "scene_cut": scene_cut, "grade_cut": grade_cut, "reports": reports}, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
