FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY switchboard ./switchboard
COPY ml ./ml
COPY web ./web
# Loopback binding is intentional. Run with host networking on Linux for a local demo.
CMD ["python", "-m", "switchboard.launch"]
