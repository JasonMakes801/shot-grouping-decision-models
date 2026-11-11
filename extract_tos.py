"""Extract one thumbnail per shot of Tears of Steel (CC BY 3.0, Blender Foundation).

Shots come from PySceneDetect's adaptive detector (data/tos/tos_scenes_adaptive.csv).
For each shot we grab the middle frame of the 1920x800 master and write:
  thumbs/eNNN.jpg      1568x653 (Jev's max side; for display)
  thumbs_784/eNNN.jpg  784x327  (what Jev sees, ~700 tokens each)
Shots listed in EXCLUDE (titles, end credits) are dropped.

Writes data/tos/shots.json.
"""
import csv
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MASTER = Path(os.environ.get("TOS_MASTER", "tears_of_steel_1080p.mov"))   # the 1080p master from mango.blender.org
OUT = Path(__file__).parent / "data" / "tos"
FPS = 24
EXCLUDE = {1, 13, 126, 127, 128, 130}  # black frames, title card, end credits


def read_shots():
    rows = list(csv.reader((OUT / "tos_scenes_adaptive.csv").open()))[2:]
    return [{"event": int(r[0]), "rec_in": int(r[1]) - 1, "rec_out": int(r[4])} for r in rows]


def extract(shot):
    mid = (shot["rec_in"] + shot["rec_out"]) // 2
    name = f"e{shot['event']:03d}.jpg"
    for folder, width in (("thumbs", 1568), ("thumbs_784", 784)):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{mid / FPS:.4f}", "-i", str(MASTER),
             "-frames:v", "1", "-vf", f"scale={width}:-2:flags=lanczos", "-q:v", "3",
             str(OUT / folder / name)],
            check=True)
    return {**shot, "thumb": f"thumbs/{name}", "clip": ""}


def main():
    for folder in ("thumbs", "thumbs_784"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    shots = [s for s in read_shots() if s["event"] not in EXCLUDE]
    with ThreadPoolExecutor(max_workers=8) as pool:
        shots = list(pool.map(extract, shots))
    (OUT / "shots.json").write_text(json.dumps(shots, indent=1))
    print(f"{len(shots)} shots written to {OUT}")


if __name__ == "__main__":
    main()
