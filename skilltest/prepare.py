"""Build the skill test's folder: 256 Imagenette photos, 8 classes of 32, unlabeled, with the answer key kept outside.

Imagenette (fast.ai) is a ten-class ImageNet subset chosen to be easy to tell apart. The 160 px version is used on
purpose: every photo is under Jev's 280 px minimum, so an agent that skips the skill's size rule fails on every image.
The images are downloaded at run time and are not part of this repo (ImageNet terms: no redistribution).

Usage: python3 skilltest/prepare.py      # writes skilltest/fixture/ and skilltest/labels.json
"""
import json, random, shutil, tarfile, urllib.request
from pathlib import Path

HERE = Path(__file__).parent
URL = "https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-160.tgz"
CLASSES = {"n01440764": "tench", "n02102040": "English springer", "n03000684": "chain saw", "n03028079": "church",
           "n03394916": "French horn", "n03417042": "garbage truck", "n03445777": "golf ball", "n03888257": "parachute"}

tgz = HERE / "imagenette2-160.tgz"
if not tgz.exists():
    urllib.request.urlretrieve(URL, tgz)
if not (HERE / "imagenette2-160").exists():
    with tarfile.open(tgz) as t:
        t.extractall(HERE)
rng = random.Random(7)
pool = []
for wnid in CLASSES:
    files = sorted((HERE / "imagenette2-160" / "train" / wnid).glob("*.JPEG"))
    pool += [(wnid, f) for f in rng.sample(files, 32)]
rng.shuffle(pool)
fixture = HERE / "fixture"
shutil.rmtree(fixture, ignore_errors=True)
fixture.mkdir()
labels = {}
for k, (wnid, f) in enumerate(pool, 1):
    name = f"photo_{k:03d}.jpg"
    shutil.copy(f, fixture / name)
    labels[name] = CLASSES[wnid]
(HERE / "labels.json").write_text(json.dumps(labels, indent=1))
print(f"{len(labels)} photos in {fixture}, answer key in {HERE / 'labels.json'}")
