"""Score one skill-test run. It passes only if all of these hold:
  - the agent loaded the skill (the prompt never mentions it)
  - every photo is in a group, at least 90% are in a group whose majority is their class,
    and at least 90% sit in their class's largest group (so splitting a class doesn't pass)
  - no request failed with the errors the skill warns about (image size, request size)
Usage: python3 skilltest/check.py <run_dir>   (reads run_dir/groups.json, run_dir/log.jsonl, labels.json beside this file)"""
import json, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).parent
run = Path(sys.argv[1]); labels = json.loads((HERE / "labels.json").read_text())
out = {"run": run.name}
# 1. skill loaded?
log = (run / "log.jsonl").read_text() if (run / "log.jsonl").exists() else ""
out["skill_loaded"] = ('"group-images-with-jev"' in log and ('"name":"Skill"' in log.replace(" ", "") or "SKILL.md" in log))
# 2. groups right?
groups = None
try:
    g = json.loads((run / "groups.json").read_text())
    if isinstance(g, dict) and all(isinstance(v, list) for v in g.values()): groups = list(g.values())
    elif isinstance(g, list): groups = [x if isinstance(x, list) else x.get("images") or x.get("files") for x in g]
    elif isinstance(g, dict):   # filename -> group
        inv = {}; [inv.setdefault(v, []).append(k) for k, v in g.items()]; groups = list(inv.values())
except Exception as e:
    out["groups_error"] = str(e)[:120]
if groups:
    names = lambda xs: [Path(str(x)).name for x in xs]
    groups = [names(x) for x in groups]
    placed = [n for x in groups for n in x if n in labels]
    right = sum(max(Counter(labels[n] for n in x if n in labels).values(), default=0) for x in groups)
    # each class's share in its single largest group: catches a class split across several groups
    group_of = {n: k for k, x in enumerate(groups) for n in x}
    kept = sum(max(Counter(group_of[n] for n in labels if labels[n] == c and n in group_of).values(), default=0)
               for c in set(labels.values()))
    out.update(groups=len(groups), placed=len(set(placed)), right=right, accuracy=round(right / len(labels), 3),
               classes_kept_together=round(kept / len(labels), 3))
else:
    out.update(groups=0, placed=0, right=0, accuracy=0.0, classes_kept_together=0.0)
# 3. known failures in the log
# only in what tools returned to the agent, not in the skill's own text (which names these errors)
results = []
for line in log.splitlines():
    try: ev = json.loads(line)
    except Exception: continue
    content = ev.get("message", {}).get("content") if ev.get("type") == "user" else None
    for c in content if isinstance(content, list) else []:
        if c.get("type") == "tool_result":
            t = c.get("content"); t = t if isinstance(t, str) else json.dumps(t)
            if "# Group images with Jev" not in t: results.append(t)
seen = "\n".join(results)
traps = {"size": "Invalid image dimensions", "tokens": "max_tokens_exceeded"}
out["traps_hit"] = [k for k, s in traps.items() if s in seen]
# usage from the final result event
for line in log.splitlines():
    try: ev = json.loads(line)
    except Exception: continue
    if ev.get("type") == "result":
        out.update(turns=ev.get("num_turns"), agent_cost_usd=round(ev.get("total_cost_usd") or 0, 2),
                   minutes=round((ev.get("duration_ms") or 0) / 60000, 1), stop=ev.get("subtype"))
out["pass"] = bool(out["skill_loaded"] and out["accuracy"] >= 0.9 and out.get("classes_kept_together", 0) >= 0.9
                   and out["placed"] == len(labels) and not out["traps_hit"])
print(json.dumps(out))
