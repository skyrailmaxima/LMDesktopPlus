#!/usr/bin/env bash
# Validates .github/workflows/ci.yml: parses the YAML, checks the gated
# image-build + release jobs exist with the right triggers, and confirms every
# build script the workflow invokes is present + executable.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 - "$ROOT" <<'PY'
import sys, os
try:
    import yaml
except Exception:
    print("note: PyYAML not available; skipping CI workflow lint")
    sys.exit(0)

root = sys.argv[1]
wf = os.path.join(root, ".github", "workflows", "ci.yml")
with open(wf) as f:
    d = yaml.safe_load(f)

fail = []
def check(cond, msg):
    print(("OK  " if cond else "FAIL ") + msg)
    if not cond:
        fail.append(msg)

# 'on:' becomes the boolean True key under YAML 1.1.
on = d.get("on", d.get(True)) or {}
check("v*" in (on.get("push", {}) or {}).get("tags", []), "push triggers on v* tags")
wd = (on.get("workflow_dispatch") or {})
check("build_images" in (wd.get("inputs") or {}), "workflow_dispatch exposes build_images input")

jobs = d.get("jobs", {})
for j in ["test", "ui-screenshots", "mint-iso", "freebsd-image", "release"]:
    check(j in jobs, f"job present: {j}")

gate = "startsWith(github.ref, 'refs/tags/v')"
for j in ["mint-iso", "freebsd-image"]:
    cond = str(jobs.get(j, {}).get("if", ""))
    check(gate in cond and "build_images" in cond, f"{j} is gated on tag/dispatch")
check(gate in str(jobs.get("release", {}).get("if", "")), "release job gated on tag")
check(jobs.get("release", {}).get("permissions", {}).get("contents") == "write",
      "release job has contents:write")

# Every build script the workflow runs must exist + be executable.
def steps_text(job):
    return "\n".join(str(s.get("run", "")) + str(s.get("with", {}).get("run", ""))
                     for s in jobs.get(job, {}).get("steps", []))
all_text = "\n".join(steps_text(j) for j in jobs)
for rel in [
    "packaging/iso/mint/build-iso.sh",
    "packaging/freebsd/image/build-image.sh",
    "packaging/freebsd/poudriere/build-repo.sh",
    "packaging/build-deb.sh",
    "packaging/build-deb-metapackage.sh",
    "packaging/build-freebsd-ui.sh",
]:
    referenced = rel in all_text
    p = os.path.join(root, rel)
    check(referenced, f"workflow references {rel}")
    check(os.path.isfile(p) and os.access(p, os.X_OK), f"{rel} exists + executable")

if fail:
    print(f"\nci-workflow lint FAILED ({len(fail)} issue(s))", file=sys.stderr)
    sys.exit(1)
print("\nci-workflow lint OK")
PY
