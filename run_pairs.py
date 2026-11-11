"""Ask Jev a yes/no question about every pair of shots.

Shots are split into blocks in edit order. Each request covers the pairs
between two blocks (or within one) and carries only those blocks' thumbnails
in `state`, keyed by event (e001...), so any number of shots fits under Jev's
context limit. Requests run in parallel.
Results: data/<dataset>/results/<kind>_pairs.json  {"038-040": 0.88, ...}

Usage: DATASET=tos python3 run_pairs.py <kind> [--within <groups_kind>]
  --within limits the pairs to shots in the same group of <groups_kind>_groups.json
"""
import itertools
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from jev import decide, image_part

DATA = Path(__file__).parent / "data" / os.environ.get("DATASET", "tos")
JEV_THUMBS = os.environ.get("JEV_THUMBS", "thumbs_784")  # half-size thumbs, about 700 tokens each
BLOCK = 60                 # shots per block
TOKEN_BUDGET = 200_000     # per request, well under Jev's 262k context
IMAGE_TOKENS = 720         # measured ~683 at 784px wide, plus margin

PROMPTS = {
    "scene": {
        "instructions": "Are `{a}` and `{b}` from the same scene: the same location "
                        "during the same continuous stretch of story time?",
        "criteria": {
            "true": "Same location, lighting and time of day. The shots could be cut "
                    "together within one sequence.",
            "false": "A different location, or the same location at a clearly different "
                     "time, such as day versus dusk.",
        },
    },
    # v2: a grading scene is one location under one lighting condition.
    "scene2": {
        "instructions": "Are `{a}` and `{b}` part of the same scene? Count them as the same "
                        "scene only if they share the same location and the same lighting "
                        "conditions: interior or exterior, time of day, weather and quality "
                        "of light all match.",
        "criteria": {
            "true": "Same location under the same lighting. The shots could sit side by side "
                    "in one continuous sequence and share one scene-level grade.",
            "false": "A different location, interior versus exterior, or a change in time of "
                     "day, weather or light quality, such as day versus dusk.",
        },
    },
    # v3: light decides. Same place under a different light is a different grading scene.
    "scene3": {
        "instructions": "Are `{a}` and `{b}` part of the same grading scene? Judge the light first: "
                        "colour temperature, time of day, weather, direction and hardness of the key "
                        "light, and the overall mood. Two shots in the same place under clearly "
                        "different light are different scenes. Shots must also be in the same kind "
                        "of place (the same interior, or the same exterior setting).",
        "criteria": {
            "true": "Same kind of place under the same light. One scene-level grade would suit both.",
            "false": "The light differs (warmer or cooler, brighter or dimmer, different time of day "
                     "or weather), or the place is clearly different.",
        },
    },
    # Subgroups for grading: one grade per subject/angle within a scene.
    "grade": {
        "instructions": "Could `{a}` and `{b}` take the same color grade? Answer yes when both "
                        "shots look at the same subject from the same camera angle, so the "
                        "background, the direction of the light and the skin tones match. Shot "
                        "size can differ if the camera is on the same side and axis.",
        "criteria": {
            "true": "Same subject from the same side and angle, with the same background and "
                    "lighting. A wider and a tighter shot on the same axis count as the same.",
            "false": "A different subject or face, the reverse angle, or a different background "
                     "or lighting direction.",
        },
    },
    "setup": {
        "instructions": "Were `{a}` and `{b}` filmed from the same camera setup? A camera "
                        "setup is one camera position and angle framing the same subject, "
                        "the shot an editor cuts back to. Ignore small differences from actor "
                        "movement, focus or a different moment in the take.",
        "criteria": {
            "true": "Same camera position, angle and subject. The frames could come from "
                    "the same take or a repeat take of that shot.",
            "false": "Different camera position, angle, shot size or subject, even if it "
                     "is the same scene or location.",
        },
    },
}


def question(kind, a, b):
    prompt = PROMPTS[kind]
    return {"type": "noul",
            "instructions": prompt["instructions"].format(a=a, b=b),
            "criteria": prompt["criteria"]}


def main():
    kind = sys.argv[1]
    shots = json.loads((DATA / "shots.json").read_text())
    keys = [f"e{s['event']:03d}" for s in shots]
    images = {key: image_part(DATA / JEV_THUMBS / Path(s["thumb"]).name) for key, s in zip(keys, shots)}
    if "--within" in sys.argv:
        groups = json.loads((DATA / "results" /
                             f"{sys.argv[sys.argv.index('--within') + 1]}_groups.json").read_text())
        pairs = [(f"e{a:03d}", f"e{b:03d}") for g in groups for a, b in itertools.combinations(g, 2)]
    else:
        pairs = list(itertools.combinations(keys, 2))

    # Plan requests: group pairs by (block of a, block of b), then split each
    # group so its images plus questions stay under the token budget.
    block_of = {key: i // BLOCK for i, key in enumerate(keys)}
    by_blocks = {}
    for a, b in pairs:
        by_blocks.setdefault((block_of[a], block_of[b]), []).append((a, b))
    # Question size depends on the prompt: ~135 tokens measured for scene2
    # (about 3.4 characters per token), so estimate from the JSON with margin.
    question_tokens = int(len(json.dumps(question(kind, "e001", "e002"))) / 3) + 10
    chunks = []
    for group in by_blocks.values():
        n_images = len({k for pair in group for k in pair})
        per_request = max(1, (TOKEN_BUDGET - n_images * IMAGE_TOKENS) // question_tokens)
        chunks += [group[i:i + per_request] for i in range(0, len(group), per_request)]

    def run(chunk):
        state = {k: images[k] for k in sorted({k for pair in chunk for k in pair})}
        questions = {f"{a[1:]}-{b[1:]}": question(kind, a, b) for a, b in chunk}
        for attempt in range(3):
            try:
                return decide(state, questions)
            except RuntimeError as err:
                print(f"retry {attempt + 1}: {str(err)[:300]}")
                time.sleep(5 * (attempt + 1))
        raise RuntimeError("chunk failed 3 times")

    start = time.time()
    with ThreadPoolExecutor(max_workers=min(8, len(chunks))) as pool:
        responses = list(pool.map(run, chunks))
    probs = {qid: ans["noul"] for resp in responses for qid, ans in resp["answers"].items()}
    tokens = sum(r["usage"]["input_tokens"] for r in responses)
    cost = sum(r["usage"].get("cost") or 0 for r in responses)
    out = DATA / "results" / f"{kind}{os.environ.get('RESULT_SUFFIX', '')}_pairs.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(probs, indent=0))
    (DATA / "results" / f"{kind}{os.environ.get('RESULT_SUFFIX', '')}_run.json").write_text(json.dumps({
        "kind": kind, "pairs": len(probs), "requests": len(chunks), "input_tokens": tokens,
        "cost": round(cost, 4), "seconds": round(time.time() - start, 1),
        "model": responses[0]["model"], "image_size": "x".join(map(str, Image.open(DATA / JEV_THUMBS / Path(shots[0]["thumb"]).name).size)),
        "scope": "all pairs" if "--within" not in sys.argv else
                 f"pairs within the same {sys.argv[sys.argv.index('--within') + 1]} group",
    }, indent=1))
    print(f"{len(probs)}/{len(pairs)} pairs, {len(chunks)} requests, {tokens} input tokens, "
          f"${cost:.4f}, {time.time() - start:.0f}s -> {out}")


if __name__ == "__main__":
    main()
