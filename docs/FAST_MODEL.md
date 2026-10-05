# Fast evidence classifier

This records the historical v3 experiment. The improved model, control comparison, challenge and reproduction commands are in [the current model study](MODEL_STUDY.md).

The AI lab now runs a bounded CPU classifier instead of generating up to 220 tokens. The first request loads a locally provisioned checkpoint; subsequent requests use a locked in-process cache. The browser times out after 15 seconds. Inference cannot download models.

Three genuine customer/version LoRA adapters were trained on `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` (Apache-2.0). Query/value projections use rank 8 LoRA. A trained head combines normalized, attention-masked embeddings with six explicit approval, currency and amount facts. Structural facts are computed outside the neural model; reported quality measures the combined system, not learned arithmetic. The classifier produces no rewrites.

Unchanged smoke suite: **56/72 correct, 14 unsafe allows, 2 unnecessary holds, zero invalid verdicts**. The release gate rejects it. Warm single-request CPU p95: **15 ms** in the offline evaluation; an actual API request took 29 ms, and a browser comparison took 25 ms. Cold loading and HTTP overhead are separate.

Monitored synthetic validation: **132/144**, with **18 messages also occurring verbatim in training**. This is not a fully unseen test. Validation was observed each epoch. Neither score proves independent compliance accuracy. Customer delivery stays disabled; deterministic rules, secret pre-filtering and trusted ticket metadata remain the delivery boundary.

Each adapter uses 144 balanced synthetic records, 30 fixed epochs and seed 42. Harbor v2 trained in 26.75 seconds using about 168 MB peak allocated GPU memory. Manifests capture dataset, policy and artifact hashes, base revision, hardware, training duration and validation history. Inference verifies adapter, head and config identities before loading. Historical causal-model failures remain visible.

## Reproduce

Install a compatible PyTorch 2.7.1 build and `ml/requirements-tested.txt`, then:

```powershell
python -c "from ml.checkpoints import download; download('sentence-transformers/all-MiniLM-L6-v2','1110a243fdf4706b3f48f1d95db1a4f5529b4d41')"
python -m ml.build_qwen
python -m ml.train_evidence --model sentence-transformers/all-MiniLM-L6-v2 --revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 --tenant harbor --policy-version v2 --train data-v3/harbor-v2-train.jsonl --validation data-v3/harbor-v2-validation.jsonl --output models/evidence-harbor-v2
```

Repeat for Harbor v1 and Cedar v1, then `python -m ml.evaluate_evidence`. The historical builder filename refers to its original prompt experiment; it also creates the classifier data. Published adapters require the pinned base checkpoint and optional ML packages. Docker CI currently verifies the rules service, not model serving. Aborted Qwen training, ONNX deployment and vLLM deployment are not claimed as completed work.
