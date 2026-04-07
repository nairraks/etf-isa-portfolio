#!/usr/bin/env python3
"""Pre-commit hook: ensure all notebook code cells have the hide-input tag.

Automatically adds the 'hide-input' tag to any code cell that lacks it,
so the deployed Jupyter Book collapses code by default.
"""
import json
import sys
import subprocess

# Find staged .ipynb files
result = subprocess.run(
    ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
    capture_output=True, text=True,
)
staged = [f for f in result.stdout.splitlines() if f.endswith(".ipynb")]

if not staged:
    sys.exit(0)

modified = []
for path in staged:
    with open(path) as f:
        nb = json.load(f)

    changed = False
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            meta = cell.setdefault("metadata", {})
            tags = meta.get("tags", [])
            if "hide-input" not in tags:
                tags.append("hide-input")
                meta["tags"] = tags
                changed = True

    if changed:
        with open(path, "w") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
            f.write("\n")
        subprocess.run(["git", "add", path])
        modified.append(path)

if modified:
    print(f"[hide-input hook] Auto-tagged code cells in: {', '.join(modified)}")
