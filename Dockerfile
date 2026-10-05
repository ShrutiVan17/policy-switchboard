FROM python:3.13-slim AS service
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY switchboard ./switchboard
COPY ml ./ml
COPY web ./web
# Loopback binding is intentional. Run with host networking on Linux for a local demo.
CMD ["python", "-m", "switchboard.launch"]

# Reproduce a synthetic-data adapter inside the image; no uploaded weights needed.
FROM service AS model-service
RUN pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r ml/requirements-serving.txt
ENV HF_HUB_DISABLE_TELEMETRY=1
RUN python -c "from ml.checkpoints import download; download('sentence-transformers/all-MiniLM-L6-v2','1110a243fdf4706b3f48f1d95db1a4f5529b4d41')"
RUN python -c "from ml.build_repaired import build; from pathlib import Path; build(Path('data-v6'))"
RUN python -m ml.train_evidence --model sentence-transformers/all-MiniLM-L6-v2 --revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 --tenant harbor --policy-version v2 --train data-v6/harbor-v2-train.jsonl --validation data-v6/harbor-v2-validation.jsonl --output models/evidence-harbor-v2 --epochs 45 --batch-size 32 --unsafe-penalty 1 --select-best-validation
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
