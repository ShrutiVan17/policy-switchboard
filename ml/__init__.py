"""Optional ML workflows require separate dependencies and compute."""
"""Keep optional model downloads inside the project by default."""
import os
from pathlib import Path

os.environ.setdefault('HF_HOME',str(Path(__file__).resolve().parents[1]/'.cache/huggingface'))
os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT','60')
