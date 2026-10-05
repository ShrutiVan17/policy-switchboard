# Run Policy Switchboard

## Working local application

Requires Python 3.11+. The recommended runtime uses FastAPI and Uvicorn. No external accounts or API subscriptions are required. A separate standard-library fallback requires no packages.

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock.txt
python -m switchboard.launch
```

Open http://127.0.0.1:8765. Interactive API docs are at http://127.0.0.1:8765/docs when FastAPI is installed. The interface executes actual local checks, saves tenant-scoped SQLite evidence, and computes evaluations. No trained model is active. For a no-install demonstration use `python -m switchboard.server` instead.

Demo API keys: `demo-harbor-key` and `demo-cedar-key`. The local-only UI can retrieve them from `/api/demo-config`. This is a loopback research demo, not production authentication. Setting environment keys does not make this public-deployment-ready. Do not expose it to an external network.

```powershell
$headers = @{ Authorization = 'Bearer demo-harbor-key' }
$body = @{ version = 'v2'; message = 'I can refund your $15 transfer fee now.'; context = @{ currency = 'USD'; fee_amount = 15; supervisor_approved = $false } } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/enforce' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
```

Authenticated keys determine tenant identity. A conflicting tenant is rejected. Unknown versions and malformed inputs fail closed. Approval and fee metadata are supplied by the caller for the demo; a production service would fetch these from a trusted source.

Other endpoints: `GET /api/health`, tenant-scoped `GET /api/evidence`, `POST /api/evaluate` with `{"mode":"full"}` or `{"mode":"triage"}`. Evaluations contain only public synthetic fixtures and run the complete fixture population, rather than customer logs.

## Verify and export

```powershell
python -m unittest discover -s tests -v
python -m switchboard.evals --output artifacts/evaluation.json
python -m switchboard.evals --mode triage --output artifacts/triage.json
python -m ml.build_dataset
```

The benchmark has 72 manually specified synthetic cases, 3 changed Harbor pairs and 21 invariant Harbor pairs. These counts are deliberately small. Matching them is a smoke check, not a production compliance claim. Runtime cost is unmeasured and shown as null. Repeated app evaluations use an in-memory exact-configuration cache; CLI evaluations start fresh. Cached calls are excluded from inference latency. Triage is only an early check; do not replace the complete release suite with it.

Evidence is written to `artifacts/evidence.sqlite`; secret findings are redacted in stored logs. Other matched passages may contain user content. Use fictional data only. Delete the local SQLite file when resetting this demo.

## Optional LoRA workflow (not executed on this machine)

Use a dedicated GPU environment, preferably Linux with Python 3.11. Check the selected checkpoint's license and model card. No model name is silently selected and no paid compute is provisioned.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r ml/requirements.txt
python -m pip freeze > artifacts/ml-environment-lock.txt
python -m ml.build_dataset
python -m ml.train_lora --model MODEL_ID --revision IMMUTABLE_40_CHARACTER_COMMIT --train data/harbor-v1-train.jsonl --validation data/harbor-v1-validation.jsonl --output models/harbor-v1 --qlora
```

Repeat for Harbor v2 and Cedar v1 with their corresponding data. `--qlora` is optional and requires a supported CUDA/bitsandbytes setup. Install ranges are a compatibility starting point, not a tested environment lock; freeze and verify the environment before publishing a result.

The generated data contains 92 train and 44 validation records per customer/version. It is unreviewed and small: expand and review it before serious training. Complete refund wording families are held out. The manually specified smoke benchmark is separate. This initial workflow trains customer adapters directly against your chosen instruction checkpoint. Training/merging a shared enforcement checkpoint is the next experiment described in the original blueprint; it has not been implemented as a second training stage.

Compare the prompted checkpoint against adapters on identical smoke cases:

```bash
python -m ml.evaluate_model --model MODEL_ID --revision IMMUTABLE_40_CHARACTER_COMMIT --output artifacts/prompted-model.json
python -m ml.evaluate_model --model MODEL_ID --revision IMMUTABLE_40_CHARACTER_COMMIT --registry ml/adapter-registry.example.json --output artifacts/lora-model.json
```

Training writes a run manifest. Evaluation rejects adapters trained against a different base revision. Each case activates exactly one tenant/version adapter. Invalid JSON is scored as an invalid output, rather than a successful escalation. The resulting report includes raw offline generations so a reviewer can inspect failures. No model-generated output is routed to the customer interface yet.

For a tiny checkpoint CPU smoke run, pass `--cpu` without `--qlora`. Training/evaluation scripts compile locally, but ML execution has not been verified because the dependencies and a trained checkpoint are absent.

Hugging Face API references used:

- https://huggingface.co/docs/trl/main/sft_trainer
- https://huggingface.co/docs/peft/quicktour

## Container

```bash
docker build -t policy-switchboard .
docker run --rm --network host -v "$PWD/artifacts:/app/artifacts" policy-switchboard
```

This container preserves the loopback-only server. Host networking is intended for Linux; Windows users can run the Python command directly. The Docker build is provided but has not been verified here.

## What is ready and what remains

Implemented: working replay UI, deterministic supported-domain engine, authenticated tenant routing for the local demo, redacted evidence, policy hashes, live evaluations, triage and exact-config cache, downloadable reports, family-split dataset generator, optional LoRA training and offline model evaluation scripts, and meaningful unit/API tests.

Not yet demonstrated: a trained LoRA artifact, model-vs-baseline results, GPU performance/cost, a public deployment, real regulatory interpretation, independent expert-reviewed benchmark, shared enforcement checkpoint training, shadow/canary promotion, or an inference backend serving trained models to the UI. These remain explicit follow-up stages, not portfolio claims.

See `README.md` for the stack summary and `docs/DESIGN.md` for the research question.
