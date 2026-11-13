# Problems hit while grouping the photos with Jev

In the order they happened:

1. **The photos were below Jev's minimum image size.** Every photo has a short side of 160 px, and Jev requires at least 280 px on each side. I upscaled each image so its short side was 300 px (keeping the aspect ratio) and re-saved it as JPEG before sending. Nothing was close to the 1568 px maximum or the 5:1 aspect limit, so no cropping was needed.

2. **The criterion "what they show" had to be interpreted.** The request didn't say how fine-grained the groups should be. A contact sheet showed a set of object categories (fish, spaniels, churches, French horns, garbage trucks, golf balls, chainsaws, parachutes), so I asked "same kind of main subject" and told the model to ignore setting, angle, people and style.

3. **The request size forced many requests.** 256 images make 32,640 pairs, far over the 262,144-token limit for a single request. I split the images into blocks of 60, made one set of requests per pair of blocks, and split each block pair's questions to stay under about 190,000 tokens, assuming about 400 tokens per image and 135 per question. That came to 37 requests, sent 8 at a time. None hit the token limit.

4. **The scratch directory I picked was already in use.** Writing to `/tmp/jevwork/run_pairs.py` failed because that file already existed, along with `probs.json`, `group.py` and contact sheets from an earlier run. I didn't overwrite or use any of them. I made a fresh directory with `mktemp -d` (`/tmp/jev_run2_0dQE/`) and worked there.

5. **The first API run failed with an SSL error.** Python 3.9 from python.org on this Mac couldn't verify OpenRouter's HTTPS certificate (`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`). No requests had gone through. I reran with `SSL_CERT_FILE` pointed at certifi's CA bundle, which was already installed, and all 37 requests succeeded ($0.2410, 32,640 answers).

6. **Some photos didn't fit any group.** Clustering at a cut of 0.5 gave eight clean groups of 29 to 32 photos, plus one group of 3 and five singletons whose subject is ambiguous: bare trees, a radar dome, distant canopies, buildings. Changing the cut didn't change this: from 0.4 to 0.7 the main groups stayed the same and only the leftovers changed. I left those photos in their own small groups instead of forcing them into a category, and listed them in my summary.

7. **Minor: the shell's working directory kept resetting.** Each `cd /tmp/...` was undone after the command, so I used absolute paths or put `cd` in the same command. This didn't affect the results.
