# Grouping a film's shots by asking a decision model

Code and data for [*Ask, Don’t Embed: Grouping Shots with a Decision Model*](https://fullstate.dev/work/decision-models/). The job: take the 124 shots of
[Tears of Steel](https://mango.blender.org), one still per shot, and group them twice, first into scenes
(one location under one light) and then, inside each scene, into grade groups (the setups one color grade
could cover). Instead of embedding the stills and clustering vectors, every pair of shots gets one yes/no
question to a decision model, and the probabilities are clustered.

| | Jev 1.14 (TypeSafe) | Clef (Cloudflare) |
|---|---|---|
| Questions | 7,626 scene + 903 grade | 7,626 scene + 877 grade |
| Requests | 16 + 6 | 1,891 + 684 |
| Cost | $0.079 | $0.97 |
| Wall-clock time | 7.8 s | 6 min 32 s |
| Shots in the right scene | 122 of 124 | 115 of 124 |
| Shots in the right grade group | 124 of 124 | 97 of 124 |

Both models were called through [OpenRouter's Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)
(`POST https://openrouter.ai/api/alpha/decisions`), which is marked alpha: "the shape may change."
Measured November 2026 with `typesafe/jev-1.14-20261014` and `cloudflare/clef`.

## Reproduce

```bash
pip install -r requirements.txt
./reproduce.sh            # score the saved answers against the hand labels: no key, no cost
```

To ask the models again you need an OpenRouter key in `OPENROUTER_API_KEY` (or a `.env` file here):

```bash
./reproduce.sh --run      # Jev again, about $0.08 and ten seconds
./reproduce.sh --clef     # Jev and Clef, about $1 and seven minutes
```

The stills are already in `data/tos/thumbs_784` (what the models saw) and `data/tos/thumbs` (full size).
To extract them yourself from the 1080p master, set `TOS_MASTER` to its path and run `python3 extract_tos.py`.

## The two questions

Scenes, one `noul` (yes/no) question per pair of shots, all 7,626 pairs:

```
Are `{a}` and `{b}` part of the same scene? Count them as the same scene only if they share the same
location and the same lighting conditions: interior or exterior, time of day, weather and quality of
light all match.
```

Grade groups, asked only for pairs inside the same scene:

```
Could `{a}` and `{b}` take the same color grade? Answer yes when both shots look at the same subject from
the same camera angle, so the background, the direction of the light and the skin tones match. Shot size
can differ if the camera is on the same side and axis.
```

Each also carries `criteria` describing what a yes and a no look like. The exact text is `PROMPTS` in
`run_pairs.py`, which also holds the first scene wording (`scene`, "the same continuous stretch of story
time") that scored 118 of 124.

## From probabilities to groups

The model returns one probability per pair, not groups. `group.py` builds groups with average-linkage
hierarchical clustering on distance 1 − P(same), cut at 0.6 for scenes and 0.5 for grade groups. A pair
can score above the cut and still end up split, because average linkage weighs each shot against all of
its would-be group mates.

## How a request is packed

- **Jev** reads images anywhere in `state`, under names you choose, so a request carries up to 120 stills
  (two blocks of 60) and every question between them refers to stills by name in backticks. Images in
  `state` are billed once per request. Each request is planned to stay under 200,000 tokens, below the
  262,144-token limit OpenRouter lists for Jev. See `run_pairs.py`.
- **Clef** takes at most four images per request, as `image_url` parts in a top-level `state` array, and
  cannot address them by name, so questions say "the first image", "the third image". Every still is
  sent about 31 times. Workers AI sizes requests from base64 length, so 67 of the 124 stills are
  re-encoded at stronger JPEG compression to fit, at the same 784 px. See `clef_pairs.py`.

## Ground truth

`data/tos/labels/tos_labels.json` holds hand labels for all 124 shots: 20 scenes and 68 grade groups.
They started from Jev's own grouping, and six shots were moved by hand after reviewing contact sheets of
every scene (five between scenes, one grade merge). The file lists the moves and the reasons. Because the
labels began as Jev's output, they favor Jev. Treat the Clef comparison as directional.

To label from scratch or correct the labels yourself, build the labeling board:

```bash
python3 build_label_board.py        # writes data/tos/labels/index.html; open it in a browser
```

## Files

| File | What it does |
|---|---|
| `jev.py` | Minimal Decisions API client (standard library plus `certifi`) |
| `run_pairs.py` | Jev: one yes/no question per pair, blocked and parallel |
| `clef_pairs.py` | Clef: the same questions, four images per request |
| `group.py` | Average-linkage clustering of pair probabilities into groups |
| `score_labels.py` | Scores against the hand labels: shots right, AUC, precision and recall, adjusted Rand |
| `extract_tos.py` | Middle frame of each shot from the master, at 1568 px and 784 px |
| `build_label_board.py`, `label_template.html` | Browser board for hand labeling, seeded from Jev's groups |
| `build_viz.py`, `viz_template.html`, `board_theme_fullstate.css` | The interactive board: edit order, Jev's groups, hand-corrected groups |
| `build_stages.py`, `stages_template.html` | The five-step sorting animation used in the write-up |
| `data/tos/results/` | Every answer, run log and score: `scene2` and `grade` are Jev, `scene` is the first wording, `clef_` is Clef, `*_raw.jsonl` are Clef's raw replies |

## Credits and license

Code: MIT. Stills from *Tears of Steel*, (CC) Blender Foundation | mango.blender.org, licensed
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Shot boundaries from
[PySceneDetect](https://www.scenedetect.com/)'s adaptive detector (`data/tos/tos_scenes_adaptive.csv`).
