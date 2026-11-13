# Problems hit while grouping the photos with Jev

In the order they happened.

1. **The criterion was vague.** "Group by what they show" could mean subject category, scene or something else. I made a contact sheet of the first 48 photos to look. It showed about ten object categories (fish, dogs, churches, golf balls and so on), so I asked Jev whether each pair shows "the same kind of main subject," with examples in the question.

2. **The folder holds a file that isn't a photo.** `log.jsonl` sits next to the photos. I only loaded files matching `photo_*.jpg`.

3. **The images were too small for Jev.** Most were 213×160 or 240×160, and Jev requires 280 to 1568 pixels per side. I spotted this before sending anything and upscaled each image so its short side was 280 px, keeping the aspect ratio. Every request went through with no dimension errors.

4. **My first resize code was muddled.** The first version of the scaling logic was hard to follow. I replaced it with one clear line before running anything, so it never caused a failure.

5. **Every HTTPS request failed on certificates.** The first run hit `SSL: CERTIFICATE_VERIFY_FAILED` on all requests, because this python.org Python install has no CA certificates. My retry loop made it worse. It treated the error as temporary, so each request retried 5 times with backoff before the script gave up. No requests reached OpenRouter, so nothing was billed. Fix: I built an SSL context from the macOS bundle at `/etc/ssl/cert.pem` and passed it to `urlopen`. The second run answered all 32,640 pairs in 46 requests ($0.25, about 21 s). A better retry loop would stop at once on certificate errors.

6. **I didn't know the token cost of small images.** The skill estimates about 700 tokens for an image 784 px wide, but these were about 280 px. I kept the 700 estimate as a safe upper bound and capped each request at 900 questions. No request hit the token limit.

7. **Ten photos didn't fit any main group.** At every cut I tried (0.4 to 0.7), 8 groups of about 30 formed, plus a few small groups and single photos. I checked these by eye. They are photos with an unclear main subject: tree trimmers with no saw visible, a child at a window, a golf-ball-shaped radar dome, a cornet, birds in the sky. I left them as Jev grouped them and told you about them, rather than forcing them into a main group.
