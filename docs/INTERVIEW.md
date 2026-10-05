# Explain the project in an interview

## Current evidence to lead with

I repaired semantic gaps using staged customer LoRA adapters, checked them against an unchanged benchmark and a newly frozen test, and compared with a matched frozen-encoder/head-only control. LoRA scored 72/72 and 66/66; the control scored 67/72 and 62/66. No unsafe approvals were observed for LoRA on these small synthetic sets. The old challenge is now a development regression set, not an unseen test.

I also fixed inflated-summary display, dataset/manifest mismatches, policy-path validation and unsafe adapter replacement. Tests cover interrupted multi-customer promotion rollback. The project uses a CPU MiniLM classifier, not ZeroDrift's proprietary Gemma enforcement model, and does not generate customer rewrites. The gate allows shadow research only. [Architecture and audit](ARCHITECTURE_AUDIT.md).

The remaining sections describe the historical causal-model experiment and the broader design.

## The problem

A policy change must change some decisions without breaking unrelated behavior. A $15 refund should move from allowed to held when Harbor's limit changes from $20 to $10. A $5 refund should stay allowed. A different customer, Cedar, requires approval regardless of amount.

## What the project measures

Compare the same immutable open base model with customer/version-specific LoRA adapters. Measure decision accuracy, invalid JSON, unsafe allows, unnecessary holds, required-change pairs and invariant regressions. Inspect the raw offline outputs, not just the score. Evaluate entire held-out wording families separately from the small smoke suite.

## Training decisions

LoRA trains small low-rank updates while the original model stays frozen. The experiment targets linear modules with rank 16 and alpha 32. Completion-only loss trains the decision response rather than the system prompt. The generator separates wording families; training rejects overlap and refuses label truncation. Manifests record data hashes, model commit, policy hash, software versions, elapsed time and weight hashes.

The small 135M model fits the local 4 GB GPU. It is an experiment in the workflow, not a substitute for ZeroDrift's much larger enforcement model. Synthetic data and three adapters alone do not establish regulatory reliability.

## Deployment decision

Never silently promote a weak model. The public-facing experiment API is a local, authenticated shadow comparison. It switches adapters under a lock, checks tenant and artifact identity, and returns no delivered model text. Deterministic enforcement stays separate. The release gate independently recomputes all decisions and rejects incomplete reports, malformed outputs and regressions.

## Faster and cheaper evaluations

Use exact model/artifact/prompt caching for repeats. Use dependency-selected refund cases plus invariant sentinels during iteration, then run the full suite before considering a release. Keep cached and uncached latency separate. No invented dollar cost is reported.

## Be ready to answer

- Where does trusted supervisor approval come from in production? An authenticated support system, never the user's message or a public checkbox.
- Why not use a single accuracy score? A model that holds everything may avoid unsafe approvals while being useless to users.
- What happens if an adapter is assigned to the wrong customer? Loading rejects mismatched tenant/policy/base fingerprints; request authentication chooses the tenant.
- What if the model generates invalid JSON or an unsafe rewrite? Count the error and withhold delivery. Rewrite meaning requires independent review.
- What remains before a real customer pilot? Expert-reviewed representative data, adversarial testing, secure identity/context integration, a deployment target, privacy controls and monitored operations.

Use the actual numbers in the saved reports. Read and run the implementation before presenting it as your work; discuss its limitations directly.
