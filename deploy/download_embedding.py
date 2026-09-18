from pathlib import Path

from huggingface_hub import snapshot_download

target = Path(__file__).resolve().parents[1] / "data/local/models/bge-small-zh-v1.5"
snapshot_download(
    "BAAI/bge-small-zh-v1.5",
    revision="7999e1d3359715c523056ef9478215996d62a620",
    local_dir=target,
    allow_patterns=["*.json", "*.txt", "*.safetensors", "1_Pooling/*"],
)
print("Downloaded pinned 512-dimensional embedding model:", target)
