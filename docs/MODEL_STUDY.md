# Customer policy model study

This is the historical v5 study. The current v6 repairs, new test and architecture comparison are in [the architecture audit](ARCHITECTURE_AUDIT.md).

Three genuine LoRA adapters specialize a pinned MiniLM encoder for Harbor v1, Harbor v2 and Cedar v1. Each uses rank 8 query/value adapters and its own trained verdict head. Six explicit facts describe approval, currency, amount identity and policy limits. These facts are computed outside the network; scores measure the combined classifier, not learned arithmetic. The model emits four verdicts and generates no customer rewrites.

| Experiment | Smoke correct | Smoke unsafe allows | Frozen challenge correct | Challenge unsafe allows |
| --- | --- | --- | --- | --- |
| Previous evidence LoRA | 56/72 | 14 | Not measured | Not measured |
| Frozen encoder + trained head | 61/72 | 1 | 55/66 | 1 |
| Counterfactual customer LoRA | **70/72** | **0** | **59/66** | **1** |

All 3 required policy-change pairs are correct. Two unnecessary holds remain on the smoke suite. The challenge exposes refusal wording, alternate guarantee wording and one amount-less refund error. We retain those failures. The challenge was not used for training, checkpoint selection or subsequent tuning. The release gate independently validates its canonical inputs and predictions and rejects release. Zero unsafe approvals on the smoke suite is not a zero-risk claim.

Warm CPU inference p95 in the final run was 23.56 ms, including artifact checks. Checkpoint loading and HTTP overhead are separate. Smoke ECE was 0.0226; challenge ECE increased to 0.0850. Confidence is uncalibrated and cannot authorize delivery.

## Data and training

Each adapter uses 608 training and 224 monitored validation records. Identical refund messages are paired with different approval, amount-match, currency and missing-data facts. Other examples cover refusals, approval requests, neutral status, overrides, standalone/mixed secrets, unsupported claims and simple/complex guarantees. The builder never reads benchmark labels or calls the enforcement engine to generate target verdicts.

There is no exact message overlap between training, validation, the smoke suite or the challenge. Some semantic families are shared across splits; this is not an independent expert-reviewed benchmark. Validation scored 664/672, but it was monitored and used for checkpoint selection and is not a blind test.

Each model trains for 45 epochs, seed 42, batch size 32, with a penalty on pass probability for labeled violations. Selection prioritizes validation unsafe allows, then accuracy, then cross-entropy. Selected epochs: 43, 40 and 7. Keeping the final checkpoint merely to claim longer training would conceal overfitting. GPU training took about 55, 71 and 58 seconds, peaking at about 274 MB allocated memory. The head-only control uses the same data, head, loss and selection budget while freezing the encoder and zero-update LoRA weights. Cached frozen embeddings remove redundant computation. This ablation tests whether adaptation adds value beyond the head.

Base: `sentence-transformers/all-MiniLM-L6-v2`, immutable revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, Apache-2.0. Manifests record dataset, policy, model, config, head and adapter identities. Inference verifies artifacts, refreshes changed manifest versions and rejects nonfinite probabilities. Inference cannot download a model.

## Reproduce

Install a compatible PyTorch 2.7.1 build and `ml/requirements-tested.txt`:

```powershell
python -c "from ml.checkpoints import download; download('sentence-transformers/all-MiniLM-L6-v2','1110a243fdf4706b3f48f1d95db1a4f5529b4d41')"
python -m ml.challenge
python -m ml.improve_fast
python -m ml.improve_fast --head-only
python -m unittest discover -s tests -v
```

The local download contains trained weights. GitHub contains source, manifests and complete reports. The previous weight-upload approval is unresolved; no further weights were uploaded. Model CI reproduces a Harbor v2 adapter inside its temporary container and does not upload weights to the repository.

Build rules with `docker build --target service -t switchboard-service .`, or build the CPU model with `docker build --target model-service -t switchboard-model .`. The latter provisions the pinned base and trains from synthetic source data, then serves offline shadow inference. CI exercises trusted ticket context, model/rule verdicts, fingerprints, warm latency, forged approval rejection and tampered-weight rejection. Its actual run status is the evidence, not a claim of a real-client production installation.

Customer delivery remains disabled. Representative expert-reviewed data and client deployment remain necessary for production claims. Historical model failures remain available. Aborted Qwen runs, ONNX serving and vLLM serving are not claimed as completed work.
