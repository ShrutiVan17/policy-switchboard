# Interactive public hosting

The README is documentation and an animated preview. It is not the running application. The website needs a Python server for typed requests, rule checks and live model comparisons. `127.0.0.1:8765` is accessible only on the machine running it.

## Full hosted app

Build the `model-service` Docker target. It provisions a pinned CPU checkpoint and reproduces a Harbor v2 adapter from synthetic source data. This avoids publishing local model weights. No GPU is required for serving this compact classifier.

Configure:

```text
SWITCHBOARD_MODE=demo
SWITCHBOARD_HOST=0.0.0.0
SWITCHBOARD_PUBLIC_ORIGIN=https://YOUR_ASSIGNED_DOMAIN
```

The launcher reads the hosting platform's `PORT`. Use the exact assigned HTTPS origin; cross-origin requests remain denied. Public demo keys and supervisor approval controls are fictional demonstration inputs. Public-demo inputs are never written to shared evidence storage or exposed through history. Private `service` mode retains its trusted-ticket and evidence requirements.

The UI compares a live model only for Harbor v2. Offline results for all three adapters must be labeled as recorded study evidence; the Docker image reproduces one adapter and does not contain a full live three-adapter deployment. Customer-facing model delivery remains disabled.

## Hosting choice

A full Python/ML app needs a hosting account and may incur resource charges. The connected Railway account is available, but deployment needs an approved plan/budget. A free static playground is a different build: rules run locally in the browser and ML results are recorded, without live neural inference. Choose this explicitly rather than representing it as the full model service.

Before sharing a public link, verify health, same-origin browser interactions, refund/approval examples, privacy blocking, model availability and visitor-history isolation on the actual assigned domain. A deployment has not been completed until those checks pass.
