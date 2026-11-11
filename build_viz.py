"""Build the scene-group board page from Jev's pairwise answers.

Writes <out_dir>/index.html plus <out_dir>/thumbs/eNNN.jpg (320px wide).
The page regroups live in the browser (average linkage, same as group.py).

Usage: DATASET=tos python3 build_viz.py <out_dir> [scene_kind] [grade_kind] [--standalone] [--labels labels.json] [--theme fullstate]
  --standalone wraps the page in its own HTML document for self-hosting
  (the artifact viewer supplies that shell itself).
"""
import json
import re
import sys
import os
from pathlib import Path

from PIL import Image

from run_pairs import PROMPTS

DATA = Path(__file__).parent / "data" / os.environ.get("DATASET", "tos")
TEMPLATE = Path(__file__).parent / "viz_template.html"

# Per-film page text.
FILMS = {
    "tos": {
        "title": "Tears of Steel, Regrouped",
        "subtitle": "The film starts in edit order. Jev 1.14 then sorts its 124 shots in two "
                    "passes, judging one still per shot without the edit order. Each column is "
                    "a scene: one location under one light. Inside it, each block is a grade "
                    "group: the same subject from the same angle, which one grade could cover.",
        "credit": '<p class="credit">Stills from <a href="https://mango.blender.org" '
                  'target="_blank" rel="noopener">Tears of Steel</a>, (CC) Blender Foundation '
                  '| mango.blender.org, licensed CC BY 3.0.</p>',
        "tc_start_frames": 0,
    },
}


STANDALONE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
:root { padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); }
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; font-size: 14px; }
img { max-width: 100%; }
[hidden] { display: none !important; }
</style>
"""


def main():
    standalone = "--standalone" in sys.argv
    labels_path = None
    if "--labels" in sys.argv:
        labels_path = Path(sys.argv[sys.argv.index("--labels") + 1])
        del sys.argv[sys.argv.index("--labels"):sys.argv.index("--labels") + 2]
    sys.argv = [a for a in sys.argv if a != "--standalone"]
    out = Path(sys.argv[1])
    scene_kind = sys.argv[2] if len(sys.argv) > 2 else "scene2"
    grade_kind = sys.argv[3] if len(sys.argv) > 3 else "grade"
    (out / "thumbs").mkdir(parents=True, exist_ok=True)
    shots = json.loads((DATA / "shots.json").read_text())
    for s in shots:
        im = Image.open(DATA / s["thumb"])
        im.resize((320, round(im.height * 320 / im.width)), Image.LANCZOS).save(
            out / "thumbs" / Path(s["thumb"]).name, quality=85)
    payload = {
        "shots": [{"event": s["event"], "clip": s["clip"], "recIn": s["rec_in"],
                   "recOut": s["rec_out"], "thumb": "thumbs/" + Path(s["thumb"]).name}
                  for s in shots],
        "scenePairs": json.loads((DATA / "results" / f"{scene_kind}_pairs.json").read_text()),
        "gradePairs": json.loads((DATA / "results" / f"{grade_kind}_pairs.json").read_text()),
        "runs": [{**json.loads((DATA / "results" / f"{k}_run.json").read_text()),
                  "prompt": PROMPTS[k]} for k in (scene_kind, grade_kind)],
    }
    theme_css = None
    if "--theme" in sys.argv:
        theme_css = (Path(__file__).parent / f"board_theme_{sys.argv[sys.argv.index('--theme') + 1]}.css").read_text()
        del sys.argv[sys.argv.index("--theme"):sys.argv.index("--theme") + 2]
    if labels_path:
        # Hand labels from the labeling board: a third view, "corrected by hand", with moved shots marked.
        lab = json.loads(labels_path.read_text())
        payload["labels"] = {
            "scenes": [{"name": sc.get("name", ""), "groups": [g["shots"] for g in sc["groups"]]} for sc in lab["scenes"]],
            "moved": lab.get("changed_from_seed", {}).get("moved_by_hand", []),
        }
    film = FILMS[os.environ.get("DATASET", "tos")]
    payload["tcStartFrames"] = film["tc_start_frames"]
    html = (TEMPLATE.read_text()
            .replace("{{TITLE}}", film["title"])
            .replace("{{SUBTITLE}}", film["subtitle"])
            .replace("{{CREDIT}}", film["credit"])
            .replace("/*DATA*/null", json.dumps(payload, separators=(",", ":"))))
    if theme_css:
        # swap the Google Fonts link for the site's own fonts, and layer the theme over the template's styles
        html = re.sub(r'<link rel="(preconnect|stylesheet)" href="https://fonts\.(googleapis|gstatic)\.com[^>]*>\n?', "", html)
        html = html.replace("</style>", theme_css + "\n</style>", 1)
    if standalone:
        html = STANDALONE_HEAD + html.replace("<!--BODY-->", "</head>\n<body>", 1) + "\n</body>\n</html>\n"
    (out / "index.html").write_text(html)
    print(f"wrote {out / 'index.html'} and {len(shots)} thumbs")


if __name__ == "__main__":
    main()
