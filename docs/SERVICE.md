# Service deployment and specialist stack

The deployment target is a Python/CUDA policy service with tenant-specific PEFT adapters. The interface is a small demonstration client; ML correctness, isolation and deployment boundaries are the engineering focus.

## Why these components

| Component | Specific engineering purpose |
| --- | --- |
| PyTorch + CUDA | Actual local gradient updates and measured inference on the available GPU |
| Transformers + PEFT | Frozen base model plus separate low-rank policy adapters and immutable checkpoint identity |
| TRL with custom token-weighted loss | Give verdict errors more training influence than repeated JSON boilerplate |
| Balanced curriculum | Equal pass/rewrite/block/escalate training populations; distinct validation wording families |
| Counterfactual policy evaluations | Required-change pairs and invariant regressions across policy versions |
| Homogeneous policy batches | Improve throughput without mixing tenant adapters inside a batch |
| Exact evaluation cache | Hash model, adapters, prompts, precision, library versions and batch composition |
| Typed FastAPI boundary | Tenant authentication, context ownership, bounded requests and fail-closed delivery |
| Trusted context adapter | Fetch fee/approval facts by tenant-owned ticket; reject caller-forged approval |
| Content-addressed artifacts | Check model revision, policy, data, configuration and weight identities |
| Docker + GitHub Actions | Build and exercise the service in a clean Linux container |

These are tools and mechanisms selected for this role. Rarity alone is not a useful selection criterion. ZeroDrift's exact internal libraries are not established by its public model description.

## Run the service profile

Set distinct, private tenant keys of at least 32 characters. Never use the public CI fixtures for deployment.

```powershell
$env:SWITCHBOARD_MODE='service'
# Set HARBOR_API_KEY and CEDAR_API_KEY through your secret manager.
python -m switchboard.provision_context --tenant harbor --ticket demo-15 --amount 15
python -m switchboard.launch
```

The administrative context command seeds fictional support records. A real client integration must replace this adapter with its authenticated support system of record. No customer API can change approval facts.

Requests identify a tenant-owned ticket instead of asserting approval:

```json
{"message":"I can refund your $15 transfer fee now.","version":"v2","ticket_id":"demo-15"}
```

Service mode disables demo credential discovery and rejects caller-supplied business context. Context lookup is tenant-scoped; unavailable context withholds delivery. Trained model text remains in shadow mode until independent release approval.

## Container verification

The workflow builds the locked image, starts a service container, provisions a ticket, verifies a held refund and rejects forged approval. Its actual run status is the deployment evidence. This is a clean-container integration check, not a claim of a live client production installation.

For a local Linux deployment, build the Dockerfile and use host networking with configured private keys and persistent artifact/context storage. The default bind is loopback. A managed deployment must also configure ingress/TLS, secret management, backups, rate limits and monitoring for its environment.

## GPU serving path

The working local implementation uses a locked PEFT multi-adapter runtime. vLLM offers dedicated LoRA serving on supported Linux GPU environments: [official LoRA documentation](https://docs.vllm.ai/en/latest/features/lora/). This is a suitable scaling target, not a runtime executed on the current Windows machine. Choose it after validating hardware, adapter compatibility, policy routing and measured benefits.

## New training experiment

`python -m ml.run_balanced` builds a separate class-balanced curriculum, trains verdict-focused adapters and evaluates the untouched smoke suite. It preserves the first failed run. Results, not token-level training loss, determine whether the new candidate is useful. The synthetic data still requires expert review.
