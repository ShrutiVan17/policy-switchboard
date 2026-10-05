"""Build a source/demo bundle without runtime databases, caches or credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent
destination=ROOT.parent / "PolicySwitchboard.zip"
files=[]
for folder in ("switchboard","ml","web","tests","docs",".github"):
    files.extend(p for p in (ROOT/folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
for name in ("README.md","RUN.md","DEMO.md","Dockerfile",".gitignore","Start-PolicySwitchboard.cmd",
             "package_project.py","policies.example.json","cases.example.jsonl","requirements.txt","requirements-dev.txt","requirements.lock.txt"):
    files.append(ROOT/name)
for name in ("evaluation.json","triage.json","preview.png","lab-preview.png","baseline-model.json","lora-model.json",
             "baseline-model-holdout.json","lora-model-holdout.json","training-runs.json","ml-environment-lock.txt"):
    file=ROOT/"artifacts"/name
    if file.exists():files.append(file)
for file in (ROOT/"data").glob("*.json*"):
    files.append(file)
for file in (ROOT/"models").glob("*/adapter_*"):
    if file.is_file(): files.append(file)
for file in (ROOT/"models").glob("*/run_manifest.json"):
    files.append(file)
if (ROOT/'models/registry.json').exists(): files.append(ROOT/'models/registry.json')
with ZipFile(destination,"w",ZIP_DEFLATED) as archive:
    for file in sorted(set(files)):
        archive.write(file,Path("policy-switchboard")/file.relative_to(ROOT))
print(f"Packaged {len(files)} files: {destination}")
