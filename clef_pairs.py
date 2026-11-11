"""Run the pairwise scene and grade passes on Cloudflare's Clef through OpenRouter's Decisions API.

Same stills (784 px wide), same question wording and criteria as run_pairs.py, so the only change is
the model. Clef differs from Jev in two ways that shape the requests:
  - at most 4 images per request, placed as image_url parts in a top-level `state` array, ahead of
    the text. Clef cannot address images by name, so questions refer to them by position
    ("the first image", "the third image").
  - Workers AI estimates request size from base64 length (about 4 characters per token) against a
    65,536-token window, so each still is re-encoded until it is under MAX_BYTES (same pixels,
    stronger JPEG compression only where needed).
Coverage: shots are paired up (62 pairs); every request carries two of those pairs (4 images) and
asks only the shot pairs not yet asked, so each of the 7,626 pairs is asked exactly once.

Usage: DATASET=tos python3 clef_pairs.py scene2|grade [--within clef_scene2] [--model cloudflare/clef] [--test]
Writes data/tos/results/clef_<kind>_pairs.json, clef_<kind>_run.json, and raw replies to clef_<kind>_raw.jsonl.
"""
import base64
import io
import itertools
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from jev import decide
from run_pairs import PROMPTS

DATA = Path(__file__).parent / "data" / os.environ.get("DATASET", "tos")
MAX_BYTES = 44_000
ORDINAL = ["first", "second", "third", "fourth"]


def small_jpeg(path):
    im = Image.open(path).convert("RGB")
    for q in (90, 85, 80, 75, 70, 65, 60, 55, 50):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q)
        if buf.tell() <= MAX_BYTES:
            return buf.getvalue(), q
    return buf.getvalue(), q


def question(kind, x, y):
    """The run_pairs.py question, with shot names swapped for image positions."""
    p = PROMPTS[kind]
    a, b = f"the {ORDINAL[x]} image", f"the {ORDINAL[y]} image"
    return {"type": "noul",
            "instructions": p["instructions"].replace("`{a}`", a).replace("`{b}`", b),
            "criteria": p["criteria"]}


def plan(keys, wanted):
    """Requests of up to 4 images covering every wanted pair once."""
    rng = random.Random(0)
    order = keys[:]
    rng.shuffle(order)
    duos = [order[i:i + 2] for i in range(0, len(order), 2)]
    asked, reqs = set(), []
    for d1, d2 in itertools.combinations(duos, 2):
        imgs = d1 + d2
        pairs = [(a, b) for a, b in itertools.combinations(imgs, 2)
                 if frozenset((a, b)) in wanted and frozenset((a, b)) not in asked]
        if pairs:
            asked.update(frozenset(p) for p in pairs)
            reqs.append((imgs, pairs))
    missing = wanted - asked
    for a, b in (tuple(m) for m in missing):          # odd count leaves a singleton duo; mop up
        reqs.append(([a, b], [(a, b)]))
    return reqs


def main():
    kind = sys.argv[1]
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "cloudflare/clef"
    tag = model.split("/")[-1].replace("-", "_")
    shots = json.loads((DATA / "shots.json").read_text())
    keys = [s["event"] for s in shots]
    images, quality = {}, {}
    for s in shots:
        data, q = small_jpeg(DATA / "thumbs_784" / Path(s["thumb"]).name)
        images[s["event"]] = "data:image/jpeg;base64," + base64.b64encode(data).decode()
        quality[s["event"]] = q
    if "--within" in sys.argv:
        groups = json.loads((DATA / "results" / f"{sys.argv[sys.argv.index('--within') + 1]}_groups.json").read_text())
        wanted = {frozenset(p) for g in groups for p in itertools.combinations(g, 2)}
    else:
        wanted = {frozenset(p) for p in itertools.combinations(keys, 2)}
    reqs = plan(keys, wanted)
    if "--test" in sys.argv:
        reqs = reqs[:1]
    print(f"{model}: {len(wanted)} pairs in {len(reqs)} requests; "
          f"{sum(q < 90 for q in quality.values())} stills re-encoded below quality 90")

    raw = (DATA / "results" / f"{tag}_{kind}_raw.jsonl").open("a")

    def run(req):
        imgs, pairs = req
        state = [{"type": "image_url", "image_url": {"url": images[e]}} for e in imgs]
        pos = {e: i for i, e in enumerate(imgs)}
        qs = {f"{min(a, b):03d}-{max(a, b):03d}": question(kind, pos[a], pos[b]) for a, b in pairs}
        for attempt in range(6):
            try:
                t = time.time()
                resp = decide(state, qs, model=model)
                resp["_seconds"] = round(time.time() - t, 2)
                resp["_images"] = imgs
                return resp
            except RuntimeError as err:
                msg = str(err)
                if attempt == 5:
                    return {"_error": msg[:500], "_images": imgs, "_pairs": list(qs)}
                time.sleep(min(60, 3 * 2 ** attempt))

    start = time.time()
    probs, cost, tokens, errors, lat = {}, 0.0, 0, [], []
    with ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "8"))) as pool:
        futs = [pool.submit(run, r) for r in reqs]
        for k, f in enumerate(as_completed(futs), 1):
            resp = f.result()
            raw.write(json.dumps({k2: v for k2, v in resp.items()}) + "\n")
            if "_error" in resp:
                errors.append(resp)
            else:
                for qid, ans in resp["answers"].items():
                    probs[qid] = ans.get("noul", ans.get("probabilities", {}).get("true"))
                cost += resp.get("usage", {}).get("cost") or 0
                tokens += resp.get("usage", {}).get("input_tokens") or 0
                lat.append(resp["_seconds"])
            if k % 100 == 0 or k == len(futs):
                print(f"  {k}/{len(futs)} requests, {len(probs)} answers, {len(errors)} errors, ${cost:.4f}, {time.time() - start:.0f}s", flush=True)
    if "--test" in sys.argv:
        print(json.dumps({k2: v for k2, v in resp.items() if k2 != "_images"}, indent=1)[:2500])
        return
    out = DATA / "results" / f"{tag}_{kind}_pairs.json"
    out.write_text(json.dumps(probs, indent=0))
    run_info = {"kind": kind, "model": model, "pairs": len(probs), "pairs_wanted": len(wanted), "requests": len(reqs),
                "errors": len(errors), "input_tokens": tokens, "cost": round(cost, 4), "seconds": round(time.time() - start, 1),
                "median_request_seconds": sorted(lat)[len(lat) // 2] if lat else None,
                "workers": int(os.environ.get("WORKERS", "8")), "image_size": "784x326",
                "max_image_bytes": MAX_BYTES, "stills_reencoded": sum(q < 90 for q in quality.values())}
    (DATA / "results" / f"{tag}_{kind}_run.json").write_text(json.dumps(run_info, indent=1))
    print(json.dumps(run_info, indent=1))


if __name__ == "__main__":
    main()
