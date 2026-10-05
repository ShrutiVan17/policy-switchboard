# What makes a decision reviewable

The project demonstrates customer-policy adaptation and release discipline. It does not certify regulatory compliance.

## Delivery boundary

`/api/enforce` uses the narrow, versioned rules engine. Passes and separately verified simple rewrites may return delivered text. Blocks, uncertain cases, and evidence-storage failures withhold delivery. Fee and approval metadata come from demo controls; a production integration must retrieve them from an authenticated system of record.

`/api/shadow` runs a real local customer adapter after validating its manifest. Every response has `delivered_output: null`. The app shows the AI verdict beside the rule verdict. A disagreement remains research evidence; it cannot override enforcement. Credentials detected by the rules never reach model inference.

## Artifact identity and tenant isolation

Bearer keys select the tenant; a conflicting request tenant is rejected. The model registry binds each tenant/policy pair to an adapter. Loading checks its tenant, policy hash, base checkpoint commit and saved-weight hash. A process-wide lock covers adapter switching and generation to prevent concurrent requests from using another tenant's adapter.

The local playground exposes fictional demo keys. It binds to loopback. These are not production authentication controls or public hosting instructions.

## Release gate

The gate recomputes decisions from all 72 canonical cases, ignoring a report's claimed accuracy. Missing or duplicate cases, altered inputs or labels, malformed JSON, unsafe allow decisions, unnecessary holds and incorrect decisions reject the candidate. Reports fingerprint weights, adapter configuration and training manifests. The app verifies local artifact fingerprints before showing shadow readiness.

Even a perfect score permits **shadow research only**. Independently reviewed data, semantic rewrite review, adversarial tests, representative customer traffic and operational validation are prerequisites for a production release. There is no button that promotes an unreviewed experiment into customer delivery.

## Evaluation boundaries

The 72-case smoke suite tests output handling and policy-change behavior; some short schema seeds overlap training examples, so it is not a wholly unseen accuracy benchmark. The separate 132-case validation corpus holds out complete refund wording families. Its thresholds and examples are synthetic, with no expert compliance review. Both reports count invalid JSON as wrong. Dollar costs are left unknown; measured wall time is not billed GPU time.

No prompt or result from a real customer is used in this project. SQLite evidence redacts matched secrets, but it is not a complete PII-removal system. Use fictional inputs only.

## Faster repeat evaluations

The model evaluator accepts `--mode triage` for dependency-selected refund cases and fixed invariant sentinels, and `--cache artifacts/model-cache-lora.json` to reuse exact predictions. Cache identity includes the immutable base revision, artifact fingerprints, complete prompt, parser revision and deterministic generation settings. Cached rows have `cache_hit: true` and zero current inference latency; uncached p95 excludes them. Partial reports cannot pass the release gate. This saves repeated inference without presenting cached time as a fresh model benchmark.

Evaluation batches contain one tenant and policy version. Cache identity includes the whole batch, precision and library versions. Reports label batch-completion latency explicitly. Serving uses single-request generation under its own lock; offline batch p95 is not a serving SLA.
