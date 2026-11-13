"""Run fresh, headless Claude Code agents on the skill test, then score each run.

Each run gets its own clean folder: the 256 photos and the skill in .claude/skills/, nothing else, and its own
TMPDIR so parallel runs cannot see each other's scratch files. The prompt does not mention the skill.
After the job, the same session is asked to list every problem it hit and how it got around it (notes.md).

Usage: OPENROUTER_API_KEY=... python3 skilltest/run_test.py [n_runs]     (run prepare.py first)
"""
import json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
SKILL = HERE.parent / "skills" / "group-images-with-jev" / "SKILL.md"
PROMPT = "Group the photos in this folder by what they show, using Jev. Write the groups to groups.json."
TOOLS = "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Skill"
NO_MCP = ["--strict-mcp-config", "--mcp-config", '{"mcpServers": {}}']   # no MCP servers from the machine running the test
NOTES_PROMPT = ("Now that you are done: list every problem you hit during this task and how you got around it, "
                "including small ones, in the order they happened. Write them to notes.md. If there were none, say so.")


def one(i):
    d = HERE / "runs" / f"run_{i}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(HERE / "fixture", d)
    (d / ".claude/skills/group-images-with-jev").mkdir(parents=True)
    shutil.copy(SKILL, d / ".claude/skills/group-images-with-jev/SKILL.md")
    tmp = d.parent / f"tmp_{i}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    env = dict(os.environ, TMPDIR=str(tmp))
    cmd = ["claude", "-p", PROMPT, "--output-format", "stream-json", "--verbose", "--allowedTools", TOOLS] + NO_MCP
    logfile = d.parent / f"run_{i}.log.jsonl"   # outside the agent's folder, so it isn't mistaken for data
    with open(logfile, "w") as log:
        try:
            subprocess.run(cmd, cwd=d, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=45 * 60)
        except subprocess.TimeoutExpired:
            log.write(json.dumps({"type": "result", "subtype": "timeout_45min"}) + "\n")
    shutil.copy(logfile, d / "log.jsonl")   # check.py reads it from the run folder
    # Agent notes: asked after the job, in the same session, so the request can't change how the job is done.
    notes = ["claude", "-p", NOTES_PROMPT, "--continue", "--output-format", "json", "--allowedTools", "Write"] + NO_MCP
    with open(d / "notes.log.json", "w") as out:
        try:
            subprocess.run(notes, cwd=d, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=5 * 60)
        except subprocess.TimeoutExpired:
            pass
    return subprocess.run([sys.executable, str(HERE / "check.py"), str(d)], capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("set OPENROUTER_API_KEY")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    # One at a time by default: agents often write scratch files to a literal /tmp path, which TMPDIR
    # doesn't redirect, so parallel runs can collide. Set PARALLEL=1 to run them side by side anyway.
    with ThreadPoolExecutor(max_workers=n if os.environ.get("PARALLEL") else 1) as pool:
        for r in pool.map(one, range(1, n + 1)):
            print(r, flush=True)
