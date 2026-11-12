---
name: group-images-with-jev
description: Group a folder of images into sets that count as "the same" by a criterion stated in words (same scene, same product, same camera setup, same artist), using TypeSafe's Jev decision model through OpenRouter's Decisions API. Use when asked to cluster, group, sort or dedupe images by meaning with Jev or a decision model, instead of embeddings.
---

# Group images with Jev

Jev answers fixed questions with probabilities. It does not write text. To group N images, ask one yes/no
question per pair of images, then cluster the probabilities in your own code. Jev never returns groups.

## The call

```
POST https://openrouter.ai/api/alpha/decisions
Authorization: Bearer $OPENROUTER_API_KEY
Content-Type: application/json

{
  "model": "typesafe/jev-1.14",
  "state": {
    "img_007": {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
    "img_012": {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
  },
  "questions": {
    "007-012": {
      "type": "noul",
      "instructions": "Do `img_007` and `img_012` show the same product?",
      "criteria": {"true": "Same product, any angle or lighting.", "false": "A different product or brand."}
    }
  }
}
```

- Put each image in `state` once, under a name you choose, and refer to it by that name in backticks.
- The reply is `answers["007-012"] = {"type": "noul", "noul": 0.87}`: the probability of yes. `usage.cost` is the price in dollars.
- On OpenRouter no extra header is needed for images. TypeSafe's own API is different (`POST https://api.typesafe.ai/v1/systemone`, images in `assets`, header `TypeSafe-Danger-Zone-Images: true`); do not mix the two.

## Rules that make requests fail

1. **Image size.** Each side must be 280 to 1568 pixels. Resize first, keeping the aspect ratio, and save as JPEG. Otherwise: `400 Invalid image dimensions`. Very wide or tall images (beyond about 5:1) cannot meet both limits; crop them.
2. **Request size.** A request must stay under 262,144 tokens. Budget about 700 tokens per image at 784 px wide and about 135 tokens per question. Otherwise: `400 max_tokens_exceeded`. N images make N×(N−1)/2 pairs, so anything past a few dozen images needs several requests:
   - split the images into blocks of at most 60
   - one request per pair of blocks (and one per block for the pairs inside it), carrying only those blocks' images
   - keep each request under about 200,000 tokens; split its questions further if needed
   - send requests in parallel (8 at a time works)
3. **Images in questions are expensive.** An image placed inside `instructions` is billed again for every question that uses it. Keep images in `state`.

## From pair probabilities to groups

```python
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

# probs: {"007-012": 0.87, ...} over every pair; ids: sorted image ids
ix = {e: i for i, e in enumerate(ids)}
dist = np.ones((len(ids), len(ids))); np.fill_diagonal(dist, 0)
for pair, p in probs.items():
    a, b = pair.split("-"); dist[ix[a], ix[b]] = dist[ix[b], ix[a]] = 1 - p
labels = fcluster(linkage(squareform(dist), "average"), t=1 - 0.6, criterion="distance")
```

Average linkage merges groups while the average probability between them stays above the cut (0.6 here).
Start between 0.5 and 0.6. Write the result as `{"group_1": [ids...], ...}`.

## When the groups are wrong

- Change the question before the cut. Say what "same" means and what it does not, in `instructions` and in
  both `criteria`. Example: "same scene" merged day and dusk shots of one place; adding "and the same lighting:
  time of day, weather and quality of light all match" split them.
- Then adjust the cut: higher gives more, smaller groups.
- For nested groups (scenes, then camera setups inside each scene), ask a coarse question over all pairs, then
  a finer question only for pairs inside each coarse group. It is far fewer questions than asking the fine one
  everywhere.

## Look it up

If a request fails in a way this skill doesn't explain, or you need something it doesn't cover, check the source.
OpenRouter marks this route alpha ("the shape may change"), so the source wins over this file:

- OpenRouter Decisions API reference: https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request
- OpenRouter's guide to images in decisions: https://openrouter.ai/docs/guides/community/multimodal-decisions
- TypeSafe's docs index (question types, image limits, known limits of Jev): https://docs.typesafe.ai/llms.txt

## Cost and time

Input tokens only, at $0.042 per million; output is free. 124 images and 7,626 questions cost about $0.07 and
took about 5 seconds in 16 parallel requests.

Worked example, with the full code: https://fullstate.dev/work/decision-models/ and
https://github.com/JasonMakes801/shot-grouping-decision-models (`run_pairs.py` batches, `group.py` clusters).
