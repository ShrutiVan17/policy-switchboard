# Technology choices and ZeroDrift alignment

Sources checked October 4, 2026. Separate publicly confirmed company information from this project's implementation and future plans.

## What ZeroDrift publicly confirms

Their [Anchor model page](https://zerodrift.com/model/anchor) describes a Gemma E4B-based enforcement model, a deterministic rules engine, customer policy LoRA adapters, verified rewrites, and L40S serving for the flagship model. Their larger model is described separately. These are first-party product descriptions, not independently verified implementation details.

The supplied hiring post specifically requests post-training, customer LoRA adapters, efficient evals and production deployment. It does not establish whether their internal stack uses FastAPI, PyTorch, PEFT, TRL, SQLite, PostgreSQL, vLLM or any frontend framework. Do not claim that it does.

## This project's choices

| Component | Choice | Why |
| --- | --- | --- |
| HTTP service | FastAPI with Pydantic, served by Uvicorn | Typed contracts, automatic OpenAPI, dependency-based authentication, Python integration |
| Web page | Plain HTML/CSS/JavaScript | Direct, understandable demo without a build toolchain |
| Policy checks | Python rules and Decimal amounts | Exact threshold handling and repeatable baseline decisions |
| Evidence | SQLite | Simple local persistence, scoped queries and immutable policy hashes |
| Training | PyTorch, Transformers, PEFT, TRL | An explicit LoRA SFT workflow with recorded model/data revisions |
| GPU memory option | QLoRA through bitsandbytes on supported environments | Optional quantized training; no hardware capability is assumed |
| Eval runner | Python, policy dependencies and exact-input/config cache | Inspectable case-level results and a conservative selective triage experiment |
| Quality | unittest, FastAPI TestClient, GitHub Actions | Verify failure behavior, boundaries, authentication and split integrity |
| Distribution | Dependency lockfile, Dockerfile, Windows launcher | Repeatable setup and a convenient local start path |

The relevant hiring evidence is the actual adapter training, case-level base/adapted comparisons, artifact checks and shadow-serving behavior. A reviewed benchmark and production measurements remain necessary before customer use.

## Model compatibility

The training script uses `AutoModelForCausalLM` and a checkpoint-provided chat template. It takes an explicit model identifier and immutable revision. It does not automatically choose or download an E4B model. Model-family loading requirements differ; a multimodal or otherwise incompatible checkpoint needs a verified loading path before training.

There is no access to ZeroDrift's proprietary Anchor weights. The project should train its own customer adapters against a licensed compatible instruction checkpoint and report that model honestly. Reusing a model family is less important than showing reproducible post-training and evaluations.

## Status you can defend in an interview

- Implemented: FastAPI playground, four enforcement outcomes, customer/version routing, evidence redaction, paired synthetic evaluations, selective triage and exact model/config cache.
- Executed locally: small-model LoRA training on a GTX 1650 Ti. Actual training manifests and completed evaluation reports are the source of truth for results.
- Implemented serving boundary: locked, artifact-checked adapter inference in shadow mode; model-generated customer delivery is disabled.
- Unverified: regulatory model quality, dollar cost, container execution and public production deployment. QLoRA was not used in the recorded local run.
- Remaining: shared enforcement checkpoint, independent reviewed benchmark, customer deployment and public hosting with proper identity, context retrieval and production storage.

The local demo is deliberately restricted to fictional support-policy patterns. Unknown or ambiguous messages are generally escalated; pattern matching is not a general semantic compliance engine.
