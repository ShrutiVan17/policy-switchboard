# Run Policy Switchboard

Python 3.11+ runs the local rules service. The completed ML environment uses Windows, Python 3.13 and a GTX 1650 Ti (4 GB).

## Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock.txt
python -m switchboard.launch
```

Open http://127.0.0.1:8765. FastAPI documentation: http://127.0.0.1:8765/docs. The Windows launcher uses the local environment when installed. The standard-library fallback (`python -m switchboard.server`) runs the rules playground; the AI lab requires FastAPI.

This is a loopback-only fictional-data application. Demo keys are `demo-harbor-key` and `demo-cedar-key`; the interface deliberately retrieves them from `/api/demo-config`. Approval and fee metadata are demo inputs. A production integration must authenticate users and retrieve trusted context from a system of record.

## Verify

```powershell
python -m unittest discover -s tests -v
python -m switchboard.evals --output artifacts/evaluation.json
python -m switchboard.evals --mode triage --output artifacts/triage.json
```

The full rules suite has 72 synthetic fixtures; triage covers 48. Repeated browser evaluations reuse exact configuration matches. Cached latency is excluded from uncached p95. Evidence is tenant-scoped and secrets are redacted; this is not comprehensive PII removal.

## Reproduce the real LoRA experiment

Install the GPU packages in a suitable environment. The following combination was exercised locally; choose the correct PyTorch wheel for other hardware.

```powershell
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r ml/requirements-tested.txt
python -m ml.run_experiment --epochs 3
```

The command downloads the Apache-2.0 SmolLM2-135M-Instruct checkpoint at pinned revision `02e84e7cc564d9c3ca090f978a4da4698ccaac29`. It generates 92 training and 44 wording-family validation records per adapter, trains Harbor v1/v2 and Cedar v1, measures both the base and adapted model, and creates the model report. The model cache lives in `.cache/huggingface` by default. No paid services are invoked.

For a supported CPU environment use `--cpu`; expect substantially slower runs. Optional QLoRA remains an alternative in the lower-level trainer and was not used in the recorded local experiment.

To train one adapter:

```powershell
python -m ml.build_dataset
python -m ml.train_lora --model HuggingFaceTB/SmolLM2-135M-Instruct --revision 02e84e7cc564d9c3ca090f978a4da4698ccaac29 --tenant harbor --policy-version v1 --train data/harbor-v1-train.jsonl --validation data/harbor-v1-validation.jsonl --output models/harbor-v1 --epochs 3
```

Training rejects overlapping wording families and truncated labels. Manifests record model, data, policy, weights, software, seed, hardware and actual elapsed training time.

## Evaluate and save inference work

```powershell
python -m ml.evaluate_model --model HuggingFaceTB/SmolLM2-135M-Instruct --revision 02e84e7cc564d9c3ca090f978a4da4698ccaac29 --registry models/registry.json --output artifacts/lora-model.json --cache artifacts/model-cache-lora.json
```

Omit `--registry` for the base model. Add `--holdout` for the 132 held-out wording examples, or `--mode triage` for dependency-selected smoke cases. Partial reports cannot pass the full release gate. Cache identity includes model, weights, full prompt and generation settings; reports distinguish reused outputs from fresh inference.

The evaluator batches up to 8 cases from the same tenant/policy. `--batch-size 1` selects sequential evaluation. Batch p95 measures whole-batch completion, not interactive request latency. Cache identity also includes batch members, numeric precision and library versions. Cache files are saved after each completed batch so interrupted runs can resume. `python -m ml.run_experiment --evaluate-only` evaluates existing adapters without retraining.

`python -m ml.summarize_experiment` creates [the model report](docs/MODEL_REPORT.md) from completed runs. Raw outputs and invalid answers remain inspectable in JSON. The smoke suite contains overlapping schema seeds; use the separate wording holdout when assessing generalization, and remember its labels are still synthetic.

## API boundaries

- `POST /api/enforce`: tenant-authenticated rules enforcement and saved evidence.
- `POST /api/shadow`: real adapter inference, compared with the rules; always withholds model delivery.
- `GET /api/experiments`: measured reports, artifact checks and release-gate failures.
- `POST /api/evaluate`: full or selective rules evaluation.
- `GET /api/evidence`: evidence for the authenticated tenant.

The AI lab loads local trained weights. GitHub contains source, manifests and measured reports; the local project bundle includes adapter weights. Fresh clones can reproduce them with the experiment command. Missing or changed artifacts reject readiness. A single lock covers model adapter selection and inference. Malformed model answers never become successful escalations in scoring.

## Limits

Passing the synthetic gate allows shadow research only. Customer delivery requires independent reviewed labels, semantic rewrite review, representative traffic and operational validation. No public production deployment, shared enforcement pretraining stage, billed GPU cost or regulatory certification is claimed. See [trust boundaries](docs/TRUST.md).

The Dockerfile is provided but container execution is unverified. It preserves the loopback service; host networking is intended for Linux. Windows users should use the Python launcher.
