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

## The agent skill

`skills/group-images-with-jev/SKILL.md` teaches a coding agent to do this job on any images, by any criterion you
can state in words: the call, the three rules that make requests fail (image size, request size, where images go),
turning pair probabilities into groups, and what to change when the groups are wrong. It follows the
[Agent Skills](https://agentskills.io) format, which Claude Code, Codex, Gemini CLI, Cursor and others read.

```bash
npx skills add JasonMakes801/shot-grouping-decision-models
```

Or copy `skills/group-images-with-jev/` into your project's `.claude/skills/`.

### How the skill is tested

`skilltest/` runs fresh, headless Claude Code agents on a job the repo does not contain: 256 photos from
[Imagenette](https://github.com/fastai/imagenette), 8 classes of 32, at 160 px, so every photo is under Jev's 280 px
minimum. Each agent gets a clean folder with only the photos and the skill, and one sentence that does not mention
the skill: "Group the photos in this folder by what they show, using Jev. Write the groups to groups.json."
A run passes only if the agent loaded the skill on its own, every photo is grouped, at least 90% land in a group
whose majority is their class, at least 90% sit in their class's largest group, and no request failed with an error
the skill warns about.

```bash
python3 skilltest/prepare.py                              # downloads Imagenette, builds the folder and answer key
OPENROUTER_API_KEY=... python3 skilltest/run_test.py 3    # three agents in parallel, then scores each
```

Results on 2026-11-12, Claude Code 2.1.322 with its default model (`skilltest/results/2026-11-12.jsonl`):

| Run | Skill loaded | Groups | In a majority-correct group | In their class's largest group | Errors | Turns | Minutes |
|---|---|---|---|---|---|---|---|
| 1 | yes | 11 | 253 of 256 | 96.9% | none | 21 | 1.6 |
| 2 | yes | 12 | 253 of 256 | 96.1% | none | 19 | 1.4 |
| 3 | yes | 14 | 252 of 256 | 95.3% | none | 13 | 1.3 |

All three passed. Every agent loaded the skill as its first action, upscaled the photos, batched the 32,640
pair questions into 36 to 46 requests, and paid Jev $0.21 to $0.26. The extra groups are a few strays of one to
three photos each; each class's main group held 28 to 34 photos.

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
| `skills/group-images-with-jev/SKILL.md` | The agent skill for this job |
| `skilltest/` | The skill's test: `prepare.py` builds the folder, `run_test.py` runs the agents, `check.py` scores a run |
| `data/tos/results/` | Every answer, run log and score: `scene2` and `grade` are Jev, `scene` is the first wording, `clef_` is Clef, `*_raw.jsonl` are Clef's raw replies |

## Credits and license

Code: MIT. Stills from *Tears of Steel*, (CC) Blender Foundation | mango.blender.org, licensed
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Shot boundaries from
[PySceneDetect](https://www.scenedetect.com/)'s adaptive detector (`data/tos/tos_scenes_adaptive.csv`).
