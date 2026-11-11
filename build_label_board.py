"""Build the hand-labeling board: a standalone page for sorting shots into scenes and grade groups by hand.

The page starts from Jev's own grouping (so the person corrects rather than builds from scratch) and
records which shots were moved, so the export says how far the labels are from the seed. Jev's
pairwise probabilities ride along for review: click a shot to see them, and doubtful shots are flagged.
Shots are dragged (or keyed) between scene columns and grade blocks. Labels autosave in the browser
and export as <dataset>_labels.json, which score_labels.py reads.

Writes <out_dir>/index.html plus <out_dir>/thumbs/eNNN.jpg (320 px wide) and reads the
full-size stills from data/<dataset>/thumbs for the lightbox.

Usage: DATASET=tos python3 build_label_board.py [out_dir]   (default data/<dataset>/labels)
Then open <out_dir>/index.html in a browser.
"""
import json
import os
import sys
from pathlib import Path

from PIL import Image

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

DATASET = os.environ.get("DATASET", "tos")
GRADE_CUT = 0.5


def jev_seed(scene_groups, grade_pairs, cutoff):
    """Jev's grouping as a starting point: scenes from the scene pass, grade groups cut inside each
    scene with the same average-linkage rule as make_groups.py. Returns [[events...], ...] per scene."""
    out = []
    for shots in sorted(scene_groups):
        shots = sorted(shots)
        if len(shots) == 1:
            out.append([shots])
            continue
        dist = np.ones((len(shots), len(shots)))
        np.fill_diagonal(dist, 0)
        for a, i in enumerate(shots):
            for b, j in enumerate(shots):
                k = f"{min(i, j):03d}-{max(i, j):03d}"
                if k in grade_pairs:
                    dist[a, b] = 1 - grade_pairs[k]
        labels = fcluster(linkage(squareform(dist), "average"), t=1 - cutoff, criterion="distance")
        groups = {}
        for shot, label in zip(shots, labels):
            groups.setdefault(label, []).append(shot)
        out.append(sorted(groups.values()))
    return out


DATA = Path(__file__).parent / "data" / DATASET
TEMPLATE = Path(__file__).parent / "label_template.html"
TITLES = {
    "tos": ("Tears of Steel, by hand",
            "Sort the 124 shots into scenes (one location under one light) and, inside each scene, "
            "grade groups (same subject from the same side, which one grade could cover). The board "
            "starts from Jev's grouping. Fix what is wrong, and the export records what you moved."),
}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / "labels"
    (out / "thumbs").mkdir(parents=True, exist_ok=True)
    shots = json.loads((DATA / "shots.json").read_text())
    for s in shots:
        name = Path(s["thumb"]).name
        if not (out / "thumbs" / name).exists():
            im = Image.open(DATA / s["thumb"])
            im.resize((320, round(im.height * 320 / im.width)), Image.LANCZOS).save(out / "thumbs" / name, quality=85)
    full_rel = os.path.relpath(DATA / "thumbs", out)
    results = DATA / "results"
    scene_pairs = json.loads((results / "scene2_pairs.json").read_text())
    grade_pairs = json.loads((results / "grade_pairs.json").read_text())
    seed = jev_seed(json.loads((results / "scene2_groups.json").read_text()), grade_pairs, GRADE_CUT)
    payload = {
        "scenePairs": scene_pairs, "gradePairs": grade_pairs,
        "seed": {"source": "scene2_groups.json (scene pass, average linkage, cut 0.5) and grade_pairs.json "
                           f"(grade pass, average linkage, cut {GRADE_CUT})",
                 "model": json.loads((results / "scene2_run.json").read_text()).get("model"),
                 "scenes": seed},
        "dataset": DATASET,
        "fps": 24,
        "tcStartFrames": 0,
        "shots": [{"event": s["event"], "recIn": s["rec_in"], "recOut": s["rec_out"],
                   "thumb": "thumbs/" + Path(s["thumb"]).name,
                   "full": f"{full_rel}/{Path(s['thumb']).name}"} for s in shots],
    }
    title, subtitle = TITLES.get(DATASET, (f"{DATASET}, by hand", "Sort shots into scenes and grade groups."))
    html = (TEMPLATE.read_text()
            .replace("{{TITLE}}", title)
            .replace("{{SUBTITLE}}", subtitle)
            .replace("/*DATA*/null", json.dumps(payload, separators=(",", ":"))))
    (out / "index.html").write_text(html)
    print(f"wrote {out / 'index.html'} with {len(shots)} shots")
    print(f"open: file://{(out / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
