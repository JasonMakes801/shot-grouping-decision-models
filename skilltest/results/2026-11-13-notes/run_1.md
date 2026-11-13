# Problems hit while grouping the photos with Jev

In the order they happened.

1. **The criterion "what they show" was vague.**
   Workaround: I built contact sheets and looked at two of the four (photos 1 to 64 and 129 to 192). The photos fell into about eight subject categories, so I asked Jev whether two photos share the same kind of main subject. I never viewed the other two sheets before choosing the question.

2. **Every image was below Jev's minimum size.** The short side was 160 px, and Jev requires every side to be 280 to 1568 px.
   Workaround: before sending, I upscaled each image so its short side was 280 px and saved it as JPEG. No image was wide enough to need cropping (the widest was about 2.7:1).

3. **The work directory was already in use.** I put my contact sheets in `/tmp/jevwork/` without checking it first. When I then tried to write `run_pairs.py` there, the write failed: a `run_pairs.py`, `probs.json`, `group.py` and contact sheets from a Nov 12 run were already in the folder. My `sheet_*.jpg` files were added next to them, but nothing was overwritten.
   Workaround: I left those files alone and did the rest of the work in a fresh directory made with `mktemp` (`/tmp/jevrun.tRPU/`). I did not reuse the old `probs.json`.

4. **Every request failed with `SSL: CERTIFICATE_VERIFY_FAILED`.** The python.org Python 3.9 build has no CA bundle configured. My script retried each request 3 times and then stopped on the first batch that failed. The error happened during the TLS handshake, so the requests most likely never reached the API.
   Workaround: I reran with `SSL_CERT_FILE=/etc/ssl/cert.pem` (the macOS system bundle) rather than turning off verification. The second run got all 32,640 answers in 42 requests for $0.21.

5. **The shell kept resetting its working directory** to the photo folder after each command that `cd`'d into `/tmp`. This was harmless.
   Workaround: I `cd`'d into the work directory at the start of every command.

6. **Nine photos did not join any of the eight main groups.** They show tree workers, a child at a window, a party under a parachute canopy, a Santorini church dome, a Coney Island building, a radar dome and birds in the sky.
   Workaround: none was needed. I looked at them, judged them truly ambiguous, and left them as small groups (group_9 to group_14) rather than forcing them into a main group. I offered to merge them.

7. **Checking was limited.** I confirmed each main group's subject from only its first image, not by looking at every member. The group sizes (28 to 33, near 256 / 8) and how little the groups changed between cuts of 0.4 and 0.7 suggest they are clean, but I did not look at each photo.
