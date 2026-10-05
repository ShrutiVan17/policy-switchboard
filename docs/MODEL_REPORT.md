# Measured model experiment

This is the historical causal-model experiment. The current encoder LoRA reaches 70/72 on smoke and 59/66 on the frozen challenge, including one unsafe challenge approval. See [the current model study](MODEL_STUDY.md) for results, ablation and deployment evidence.

Generated from completed runs: 2026-10-05T03:48:17.201738+00:00

All inputs are fictional. Scores measure this experiment, not regulatory compliance.

| Run | Correct | Invalid JSON | Unsafe allows | Batch p95 uncached |
| --- | --- | --- | --- | --- |
| [baseline-model.json](../artifacts/baseline-model.json) | 0/72 | 72 | 0 | 35153.9 ms |
| [lora-model.json](../artifacts/lora-model.json) | 25/72 | 0 | 47 | 13100.9 ms |
| [baseline-model-holdout.json](../artifacts/baseline-model-holdout.json) | 0/132 | 132 | 0 | 55592.1 ms |
| [lora-model-holdout.json](../artifacts/lora-model-holdout.json) | 90/132 | 0 | 42 | 21372.9 ms |

## Training

| Adapter | Epochs | Training wall time | Hardware |
| --- | --- | --- | --- |
| cedar-v1 | 3.0 | 347.0 s | NVIDIA GeForce GTX 1650 Ti |
| harbor-v1 | 3.0 | 699.6 s | NVIDIA GeForce GTX 1650 Ti |
| harbor-v2 | 3.0 | 243.0 s | NVIDIA GeForce GTX 1650 Ti |

Weight, policy, dataset and software identities are in [training manifests](../artifacts/training-runs.json).

The smoke suite includes schema seeds overlapping training. The 132-case wording holdout excludes entire refund template families from training; labels remain synthetic and unreviewed.

The base is SmolLM2-135M-Instruct at immutable revision `02e84e7cc564d9c3ca090f978a4da4698ccaac29`. It is much smaller than the model described by ZeroDrift.

Gate results are in each smoke report. Incorrect or invalid decisions reject shadow readiness. Passing synthetic tests alone never authorizes customer delivery.

Offline inference uses homogeneous tenant/policy batches of up to 8. The reported p95 measures whole-batch completion, not individual interactive-request latency. Timings exclude model loading and presentation animation. Training wall time is measured elapsed time, including interruptions; it is not billed GPU time. Dollar costs are unknown.

## Release decision

rejected

47 incorrect decisions; 47 unsafe allow decisions

## Example errors

| Family | Customer/policy | Expected | Model |
| --- | --- | --- | --- |
| refund-2001 | harbor/v1 | escalate | pass |
| mismatch | harbor/v1 | escalate | pass |
| missing | harbor/v1 | escalate | pass |
| no-amount | harbor/v1 | escalate | pass |
| unsupported-paraphrase | harbor/v1 | escalate | pass |
| unknown | harbor/v1 | escalate | pass |
| guarantee | harbor/v1 | rewrite | pass |
| riskfree | harbor/v1 | rewrite | pass |
| complex-claim | harbor/v1 | escalate | pass |
| secret | harbor/v1 | block | pass |
| account | harbor/v1 | block | pass |
| mixed | harbor/v1 | block | pass |

## Failure analysis

The adapted model collapsed to a single decision class. Better JSON validity and low token-level validation loss did not establish policy discrimination. The release gate catches this through unsafe-allow counts and required-change pairs.

The next controlled experiment should emphasize verdict loss, balance decision families, standardize numeric representations, expand safety/unknown examples and compare a stronger checkpoint. These are proposed experiments, not completed results. A separate independently reviewed test set is still required.
